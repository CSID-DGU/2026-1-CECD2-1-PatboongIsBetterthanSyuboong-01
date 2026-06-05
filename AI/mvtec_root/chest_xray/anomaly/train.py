#!/usr/bin/env python3
"""
학습 모듈
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

from .model import SimpleAE, ImageAnomalyDual
from .environment import get_dataloaders, get_balanced_train_loader
from .utils import seed_everything, ensure_dir


def to_minus_one_one(tensor: torch.Tensor) -> torch.Tensor:
    """0~1 범위를 -1~1 범위로 정규화"""
    return tensor * 2.0 - 1.0


def to_zero_one(tensor: torch.Tensor) -> torch.Tensor:
    """-1~1 범위를 0~1 범위로 역정규화"""
    return torch.clamp((tensor + 1.0) * 0.5, 0.0, 1.0)


def ssim_loss(x: torch.Tensor, y: torch.Tensor, window_size: int = 7) -> torch.Tensor:
    """간단한 SSIM 손실 구현 (1-SSIM)/2"""
    C1 = 0.01 ** 2
    C2 = 0.03 ** 2
    padding = window_size // 2

    mu_x = F.avg_pool2d(x, window_size, stride=1, padding=padding)
    mu_y = F.avg_pool2d(y, window_size, stride=1, padding=padding)

    sigma_x = F.avg_pool2d(x * x, window_size, stride=1, padding=padding) - mu_x ** 2
    sigma_y = F.avg_pool2d(y * y, window_size, stride=1, padding=padding) - mu_y ** 2
    sigma_xy = F.avg_pool2d(x * y, window_size, stride=1, padding=padding) - mu_x * mu_y

    numerator = (2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)
    denominator = (mu_x ** 2 + mu_y ** 2 + C1) * (sigma_x + sigma_y + C2)
    ssim_map = numerator / (denominator + 1e-8)
    return torch.clamp((1.0 - ssim_map) * 0.5, 0.0, 1.0).mean()


def configure_augmentations(args):
    """자동 증강 설정"""
    auto_aug_enabled = not getattr(args, 'disable_auto_aug', False)
    use_aug = args.aug or auto_aug_enabled
    use_clahe = args.clahe or auto_aug_enabled
    noise_sigma = args.noise_sigma
    if auto_aug_enabled:
        noise_sigma = max(noise_sigma, 0.02)
    return use_aug, use_clahe, noise_sigma, auto_aug_enabled


def compute_recon_loss(x: torch.Tensor, xrec: torch.Tensor, recon_loss_fn=None) -> torch.Tensor:
    """재구성 손실: (L1/Huber) + SSIM"""
    if recon_loss_fn is not None:
        base_loss = recon_loss_fn(xrec, x)
    else:
        base_loss = F.l1_loss(xrec, x)
    x_norm = to_minus_one_one(x)
    xrec_norm = to_minus_one_one(xrec)
    ssim = ssim_loss(xrec_norm, x_norm)
    return 0.7 * base_loss + 0.3 * ssim


class HuberLoss(nn.Module):
    """Huber Loss - outlier에 robust한 loss function"""
    def __init__(self, delta=1.0):
        super().__init__()
        self.delta = delta
    
    def forward(self, pred, target):
        error = pred - target
        abs_error = torch.abs(error)
        quadratic = torch.clamp(abs_error, max=self.delta)
        linear = abs_error - quadratic
        return torch.mean(0.5 * quadratic ** 2 + self.delta * linear)


class RobustScoreLoss(nn.Module):
    """Outlier에 robust한 스코어 loss"""
    def __init__(self, percentile=95.0):
        super().__init__()
        self.percentile = percentile
    
    def forward(self, score):
        # 상위 percentile만 사용하여 outlier의 영향을 줄임
        B = score.shape[0]
        score_flat = score.view(B, -1)  # [B, H*W]
        
        # 각 배치별로 상위 percentile 값만 사용
        percentile_val = torch.quantile(score_flat, self.percentile / 100.0, dim=1, keepdim=True)  # [B, 1]
        mask = score_flat >= percentile_val
        masked_scores = score_flat * mask.float()
        
        # Masked 평균 (outlier 제외)
        return masked_scores.sum(dim=1).mean() / (mask.sum(dim=1).float().mean() + 1e-8)


def stability_penalty(map_tensor: torch.Tensor, target: float = 0.15) -> torch.Tensor:
    """스코어 분포의 평균/분산을 안정화하기 위한 패널티
    target을 0.15로 증가하여 스코어가 0으로 수렴하지 않도록 함
    """
    B = map_tensor.shape[0]
    flat = map_tensor.view(B, -1)
    mean = flat.mean(dim=1)
    std = flat.std(dim=1)
    # ?ㅼ퐫?닿? ?덈Т ?묒븘吏吏 ?딅룄濡?penalty ?섏젙
    penalty = torch.mean(torch.abs(mean - target) + 0.5 * std)
    return penalty


def create_pseudo_anomaly(x: torch.Tensor, method: str = 'cutpaste') -> torch.Tensor:
    """?뺤긽 ?대?吏?먯꽌 pseudo anomaly ?앹꽦
    Args:
        x: ?뺤긽 ?대?吏 [B, C, H, W]
        method: 'cutpaste', 'random_erase', 'blur' 以??섎굹
    Returns:
        pseudo_anomaly: 蹂?뺣맂 ?대?吏 [B, C, H, W]
    """
    B, C, H, W = x.shape
    x_pseudo = x.clone()
    
    if method == 'cutpaste':
        # CutPaste: ?대?吏 ?쇰?瑜??섎씪???ㅻⅨ ?꾩튂??遺숈씠湲?
        for b in range(B):
            # ?섎씪???곸뿭 ?ш린 (?대?吏??5-15%)
            cut_h = int(H * (0.05 + torch.rand(1).item() * 0.1))
            cut_w = int(W * (0.05 + torch.rand(1).item() * 0.1))
            # ?섎씪???꾩튂
            cut_y = int(torch.rand(1).item() * (H - cut_h))
            cut_x = int(torch.rand(1).item() * (W - cut_w))
            # 遺숈씪 ?꾩튂
            paste_y = int(torch.rand(1).item() * (H - cut_h))
            paste_x = int(torch.rand(1).item() * (W - cut_w))
            
            # ?섎씪??遺遺꾩쓣 ?ㅻⅨ ?꾩튂??遺숈씠湲?
            cut_patch = x_pseudo[b:b+1, :, cut_y:cut_y+cut_h, cut_x:cut_x+cut_w]
            x_pseudo[b:b+1, :, paste_y:paste_y+cut_h, paste_x:paste_x+cut_w] = cut_patch
    
    elif method == 'random_erase':
        # RandomErasing: ?대?吏 ?쇰?瑜?0?쇰줈 吏?곌린
        for b in range(B):
            erase_h = int(H * (0.1 + torch.rand(1).item() * 0.2))
            erase_w = int(W * (0.1 + torch.rand(1).item() * 0.2))
            erase_y = int(torch.rand(1).item() * (H - erase_h))
            erase_x = int(torch.rand(1).item() * (W - erase_w))
            x_pseudo[b:b+1, :, erase_y:erase_y+erase_h, erase_x:erase_x+erase_w] = 0.0
    
    elif method == 'blur':
        # 媛뺥븳 釉붾윭 ?곸슜
        from torchvision.transforms import GaussianBlur
        blur = GaussianBlur(kernel_size=15, sigma=(5.0, 10.0))
        x_pseudo = blur(x_pseudo)
    
    return x_pseudo


def train_autoencoder(args):
    """Autoencoder 학습
    Args:
        args: 명령행 인자 객체
    """
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    seed_everything(args.seed)
    # Autoencoder 학습용 증강 설정 사용
    use_aug, use_clahe, noise_sigma, auto_aug_enabled = configure_augmentations(args)
    train_loader, _ = get_dataloaders(args.data_root, args.img_size, args.batch_size,
                                       args.num_workers, augment=use_aug, use_clahe=use_clahe,
                                       noise_sigma=noise_sigma)
    if auto_aug_enabled:
        print(f"[AE] Auto augmentation enabled (aug={use_aug}, clahe={use_clahe}, noise_sigma={noise_sigma:.3f})")
    # latent_ch를 명시적으로 256으로 설정 (이미지 해상도 256x256에 맞춤)
    latent_ch = getattr(args, 'latent_ch', 256)
    model = SimpleAE(in_ch=1, latent_ch=latent_ch).to(device)
    optim_ = torch.optim.Adam(model.parameters(), lr=args.lr)
    best_loss = 1e9
    ensure_dir(args.checkpoint_dir)
    ckpt_path = os.path.join(args.checkpoint_dir, 'ae_best.pt')

    model.train()
    for epoch in range(1, args.epochs + 1):
        running = 0.0
        pbar = tqdm(train_loader, desc=f"[AE][Ep {epoch}/{args.epochs}]")
        for x, _ in pbar:
            x = x.to(device)
            xrec, _ = model(x)  # z는 반환하지 않으므로 제외
            # target_score와 stability_penalty 제거, 복원 오차만 최소화
            loss = compute_recon_loss(x, xrec)
            optim_.zero_grad()
            loss.backward()
            optim_.step()
            running += loss.item() * x.size(0)
            pbar.set_postfix(loss=float(loss.item()))
        epoch_loss = running / len(train_loader.dataset)
        print(f"Epoch {epoch} MAE: {epoch_loss:.6f}")
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            # latent_ch를 args에 명시적으로 추가
            save_args = vars(args).copy()
            save_args['latent_ch'] = latent_ch
            torch.save({'model': model.state_dict(), 'args': save_args, 'epoch': epoch}, ckpt_path)
            print(f"  -> Saved best to {ckpt_path} (latent_ch={latent_ch})")


def train_dual_anomaly(args):
    """ImageAnomalyDual 모델 학습 (SimpleAE pre-trained 가중치 사용)
    Args:
        args: 명령행 인자 객체
    """
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    seed_everything(args.seed)
    # Dual Branch???뺤긽 ?곗씠?곕쭔 ?ъ슜 (AE? ?숈씪)
    use_aug, use_clahe, noise_sigma, auto_aug_enabled = configure_augmentations(args)
    train_loader, _ = get_dataloaders(args.data_root, args.img_size, args.batch_size,
                                      args.num_workers, augment=use_aug, use_clahe=use_clahe,
                                      noise_sigma=noise_sigma)
    if auto_aug_enabled:
        print(f"[Dual] Auto augmentation enabled (aug={use_aug}, clahe={use_clahe}, noise_sigma={noise_sigma:.3f})")
    
    # SimpleAE pre-trained 媛以묒튂 濡쒕뱶 (?덈뒗 寃쎌슦) - latent_ch ?뺤씤
    ae_ckpt_path = os.path.join(args.checkpoint_dir, 'ae_best.pt')
    # 중요: latent_ch는 명시적으로 256으로 설정 (이미지 해상도 256x256에 맞춤)
    # 체크포인트의 latent_ch를 따르지 않고 항상 args.latent_ch 또는 기본값 256 사용
    latent_ch = getattr(args, 'latent_ch', 256)
    print(f"[Dual] Using latent_ch={latent_ch} (이미지 해상도 256x256에 맞춤)")
    
    # AE 체크포인트 확인 및 로드 (latent_ch가 일치하는 경우만)
    load_ae_weights = False
    ae_ckpt = None
    if os.path.exists(ae_ckpt_path):
        print(f"Checking pre-trained SimpleAE from {ae_ckpt_path}")
        ae_ckpt = torch.load(ae_ckpt_path, map_location=device, weights_only=False)
        # 체크포인트의 latent_ch 확인
        ckpt_latent_ch = None
        if 'args' in ae_ckpt and 'latent_ch' in ae_ckpt['args']:
            ckpt_latent_ch = ae_ckpt['args']['latent_ch']
        else:
            state_dict = ae_ckpt['model']
            if 'enc.14.weight' in state_dict:
                ckpt_latent_ch = state_dict['enc.14.weight'].shape[0]
        
        if ckpt_latent_ch is not None:
            if ckpt_latent_ch == latent_ch:
                print(f"  -> Checkpoint latent_ch={ckpt_latent_ch} matches, will load weights")
                load_ae_weights = True
            else:
                print(f"  -> Warning: Checkpoint has latent_ch={ckpt_latent_ch}, but using latent_ch={latent_ch}")
                print(f"  -> Skipping AE weight loading (크기 불일치). AE를 latent_ch={latent_ch}로 새로 학습하세요.")
        else:
            print(f"  -> Could not determine checkpoint latent_ch, skipping AE weight loading")
    
    # Fusion 모듈 선택 (기본값)
    use_fusion = getattr(args, 'use_fusion', False)
    model = ImageAnomalyDual(in_ch=1, latent_ch=latent_ch, use_fusion=use_fusion).to(device)
    if not use_fusion:
        print("  -> Fusion module disabled (using ADRM output directly)")
    
    # SimpleAE pre-trained 媛以묒튂 濡쒕뱶
    # AE 가중치 로드 (latent_ch가 일치하는 경우만)
    if load_ae_weights and ae_ckpt is not None:
        model.ae.load_state_dict(ae_ckpt['model'])
        print(f"  -> Pre-trained AE weights loaded (latent_ch={latent_ch})")
    else:
        print(f"  -> Training AE from scratch (latent_ch={latent_ch})")
        # AE 遺遺꾩? 怨좎젙?섍퀬 ?섎㉧吏留??숈뒿 (?좏깮??
    # AE 가중치 고정 옵션
    if args.freeze_ae:
        for param in model.ae.parameters():
            param.requires_grad = False
        print("  -> AE weights frozen")
    
    optim_ = torch.optim.Adam(model.parameters(), lr=args.lr)
    best_loss = 1e9
    ensure_dir(args.checkpoint_dir)
    ckpt_path = os.path.join(args.checkpoint_dir, 'dual_best.pt')
    
    # Robust loss functions
    use_robust_loss = getattr(args, 'use_robust_loss', True)
    consistency_weight = getattr(args, 'consistency_weight', 0.1)  # 기본값 0.1로 변경
    stability_weight = getattr(args, 'stability_weight', 0.0)  # 기본값 0으로 변경(비활성화꾪솢?깊솕)
    margin = getattr(args, 'margin', 0.1)  # margin-based 손실의 margin
    pseudo_anomaly_ratio = getattr(args, 'pseudo_anomaly_ratio', 0.5)  # 諛곗튂??紐?%瑜?pseudo anomaly濡?
    
    if use_robust_loss:
        recon_loss_fn = HuberLoss(delta=0.1)  # Reconstruction에 Huber loss 사용
        print("  -> Using robust loss functions (Huber)")
    else:
        recon_loss_fn = None
        print("  -> Using standard loss functions")
    if consistency_weight > 0:
        print(f"  -> Consistency weight: {consistency_weight}")
    if stability_weight > 0:
        print(f"  -> Stability weight: {stability_weight} (권장: 0 또는 <=0.02)")
    print(f"  -> Margin-based loss margin: {margin}")
    print(f"  -> Pseudo anomaly ratio: {pseudo_anomaly_ratio}")

    model.train()
    for epoch in range(1, args.epochs + 1):
        running_recon = 0.0
        running_score = 0.0
        pbar = tqdm(train_loader, desc=f"[Dual][Ep {epoch}/{args.epochs}]")
        for x, _ in pbar:
            x = x.to(device)
            B = x.size(0)
            
            # 諛곗튂???쇰?瑜?pseudo anomaly濡?蹂??
            n_pseudo = max(1, int(B * pseudo_anomaly_ratio))
            pseudo_indices = torch.randperm(B)[:n_pseudo]
            x_pseudo = x.clone()
            for idx in pseudo_indices:
                # CutPaste, RandomErasing, blur 중 하나 선택
                method = ['cutpaste', 'random_erase', 'blur'][torch.randint(0, 3, (1,)).item()]
                x_pseudo[idx:idx+1] = create_pseudo_anomaly(x[idx:idx+1], method=method)
            
            # ?뺤긽 ?대?吏?????forward
            xrec, score, s_recon, s_feat, r = model(x)
            
            # Reconstruction loss (?뺤긽 ?대?吏????蹂듭썝?섏뼱????
            if use_robust_loss and recon_loss_fn is not None:
                base_recon = recon_loss_fn(xrec, x)
            else:
                base_recon = F.l1_loss(xrec, x)
            ssim_term = ssim_loss(to_minus_one_one(xrec), to_minus_one_one(x))
            loss_recon = 0.7 * base_recon + 0.3 * ssim_term
            
            # Pseudo anomaly?????forward
            xrec_pseudo, score_pseudo, s_recon_pseudo, s_feat_pseudo, r_pseudo = model(x_pseudo)
            
            # Margin-based score loss: 정상은 작게, pseudo anomaly는 크게
            flat_pos = score.view(B, -1)
            k = max(1, int(flat_pos.size(1) * 0.02))  # 상위 2% 평균
            pos = flat_pos.topk(k, dim=1)[0].mean()  # 정상 이미지의 상위 k% 평균

            flat_neg = score_pseudo.view(B, -1)
            neg = flat_neg.topk(k, dim=1)[0].mean()  # pseudo anomaly의 상위 k% 평균

            loss_score = F.relu(margin + pos - neg)  # margin-based 손실 함수
            
            # Combined loss
            stability_term = 0.0
            if stability_weight > 0 and epoch > getattr(args, 'stability_warmup', 5):
                stability_term = stability_penalty(score.clamp(min=0.0, max=1.0), getattr(args, 'stability_target', 0.15))
            consistency_term = 0.0
            if consistency_weight > 0:
                consistency_term = F.l1_loss(s_feat, s_recon.detach())
            loss = (
                loss_recon
                + 0.5 * loss_score  # Score loss 가중치
                + stability_weight * stability_term
                + consistency_weight * consistency_term
            )
            
            optim_.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # gradient clipping
            optim_.step()
            
            running_recon += loss_recon.item() * x.size(0)
            running_score += loss_score.item() * x.size(0)
            pbar.set_postfix(recon=float(loss_recon.item()), score=float(loss_score.item()), 
                           pos=float(pos.item()), neg=float(neg.item()))
        
        epoch_loss_recon = running_recon / len(train_loader.dataset)
        epoch_loss_score = running_score / len(train_loader.dataset)
        print(f"Epoch {epoch} Recon: {epoch_loss_recon:.6f}, Score: {epoch_loss_score:.6f}")
        
        total_loss = epoch_loss_recon + 0.5 * epoch_loss_score
        if total_loss < best_loss:
            best_loss = total_loss
            # latent_ch를 args에 명시적으로 추가
            save_args = vars(args).copy()
            save_args['latent_ch'] = latent_ch
            torch.save({'model': model.state_dict(), 'args': save_args, 'epoch': epoch}, ckpt_path)
            print(f"  -> Saved best to {ckpt_path} (latent_ch={latent_ch})")


def train_dual_anomaly_staged(args):
    """단계별 학습: 1) AE만 학습, 2) AE 고정 + Attention 학습, 3) 전체 fine-tuning
    Args:
        args: 명령행 인자 객체
    """
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    seed_everything(args.seed)
    
    # Dual Branch???뺤긽 ?곗씠?곕쭔 ?ъ슜 (AE? ?숈씪)
    use_aug, use_clahe, noise_sigma, auto_aug_enabled = configure_augmentations(args)
    train_loader, _ = get_dataloaders(args.data_root, args.img_size, args.batch_size,
                                      args.num_workers, augment=use_aug, use_clahe=use_clahe,
                                      noise_sigma=noise_sigma)
    if auto_aug_enabled:
        print(f"[Dual-Staged] Auto augmentation enabled (aug={use_aug}, clahe={use_clahe}, noise_sigma={noise_sigma:.3f})")
    
    # SimpleAE pre-trained 媛以묒튂 濡쒕뱶 (?덈뒗 寃쎌슦) - latent_ch ?뺤씤
    ae_ckpt_path = os.path.join(args.checkpoint_dir, 'ae_best.pt')
    # 중요: latent_ch는 명시적으로 256으로 설정 (이미지 해상도 256x256에 맞춤)
    # 체크포인트의 latent_ch를 따르지 않고 항상 args.latent_ch 또는 기본값 256 사용
    latent_ch = getattr(args, 'latent_ch', 256)
    print(f"[Dual-Staged] Using latent_ch={latent_ch} (이미지 해상도 256x256에 맞춤)")
    
    if os.path.exists(ae_ckpt_path):
        ae_ckpt = torch.load(ae_ckpt_path, map_location=device, weights_only=False)
        # 체크포인트의 latent_ch는 참고용으로만 확인 (사용하지 않음)
        ckpt_latent_ch = None
        if 'args' in ae_ckpt and 'latent_ch' in ae_ckpt['args']:
            ckpt_latent_ch = ae_ckpt['args']['latent_ch']
        else:
            state_dict = ae_ckpt['model']
            if 'enc.14.weight' in state_dict:
                ckpt_latent_ch = state_dict['enc.14.weight'].shape[0]
        
        if ckpt_latent_ch is not None and ckpt_latent_ch != latent_ch:
            print(f"  -> Warning: Checkpoint has latent_ch={ckpt_latent_ch}, but using latent_ch={latent_ch} (이미지 해상도에 맞춤)")
    
    use_fusion = getattr(args, 'use_fusion', False)
    model = ImageAnomalyDual(in_ch=1, latent_ch=latent_ch, use_fusion=use_fusion).to(device)
    
    ensure_dir(args.checkpoint_dir)
    
    # ========== Stage 1: AE留??숈뒿 ==========
    print("\n" + "="*60)
    print("Stage 1: Autoencoder ?숈뒿")
    print("="*60)
    
    # SimpleAE pre-trained 媛以묒튂 濡쒕뱶 ?먮뒗 ?숈뒿
    ae_ckpt_path = os.path.join(args.checkpoint_dir, 'ae_best.pt')
    load_ae_weights = False
    ae_ckpt = None
    if os.path.exists(ae_ckpt_path):
        print(f"Checking pre-trained SimpleAE from {ae_ckpt_path}")
        ae_ckpt = torch.load(ae_ckpt_path, map_location=device, weights_only=False)
        # 체크포인트의 latent_ch 확인
        ckpt_latent_ch = None
        if 'args' in ae_ckpt and 'latent_ch' in ae_ckpt['args']:
            ckpt_latent_ch = ae_ckpt['args']['latent_ch']
        else:
            state_dict = ae_ckpt['model']
            if 'enc.14.weight' in state_dict:
                ckpt_latent_ch = state_dict['enc.14.weight'].shape[0]
        
        if ckpt_latent_ch is not None:
            if ckpt_latent_ch == latent_ch:
                print(f"  -> Checkpoint latent_ch={ckpt_latent_ch} matches, will load weights")
                load_ae_weights = True
            else:
                print(f"  -> Warning: Checkpoint has latent_ch={ckpt_latent_ch}, but using latent_ch={latent_ch}")
                print(f"  -> Skipping AE weight loading (크기 불일치). AE를 latent_ch={latent_ch}로 새로 학습하세요.")
        else:
            print(f"  -> Could not determine checkpoint latent_ch, skipping AE weight loading")
    
    if load_ae_weights and ae_ckpt is not None:
        model.ae.load_state_dict(ae_ckpt['model'])
        print(f"  -> Pre-trained AE weights loaded (latent_ch={latent_ch})")
    else:
        print(f"  -> Training AE from scratch (latent_ch={latent_ch})")
        # AE 학습
        ae_params = list(model.ae.parameters())
        optim_ae = torch.optim.Adam(ae_params, lr=args.lr)
        best_ae_loss = 1e9
        
        recon_loss_fn = HuberLoss(delta=0.1) if getattr(args, 'use_robust_loss', True) else None
        
        model.train()
        for epoch in range(1, args.epochs + 1):
            running = 0.0
            pbar = tqdm(train_loader, desc=f"[AE Stage1][Ep {epoch}/{args.epochs}]")
            for x, _ in pbar:
                x = x.to(device)
                xrec, _ = model.ae(x)
                
                if recon_loss_fn is not None:
                    base_loss = recon_loss_fn(xrec, x)
                else:
                    base_loss = F.l1_loss(xrec, x)
                ssim_term = ssim_loss(to_minus_one_one(xrec), to_minus_one_one(x))
                loss = 0.7 * base_loss + 0.3 * ssim_term
                
                if args.stability_weight > 0 and epoch > getattr(args, 'stability_warmup', 5):
                    residual = torch.abs(xrec - x)
                    stab = stability_penalty(residual, args.stability_target)
                    loss = loss + args.stability_weight * stab
                
                optim_ae.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(ae_params, max_norm=1.0)
                optim_ae.step()
                running += loss.item() * x.size(0)
                pbar.set_postfix(loss=float(loss.item()))
            
            epoch_loss = running / len(train_loader.dataset)
            print(f"Epoch {epoch} MAE: {epoch_loss:.6f}")
            if epoch_loss < best_ae_loss:
                best_ae_loss = epoch_loss
                # latent_ch를 args에 명시적으로 추가
                save_args = vars(args).copy()
                save_args['latent_ch'] = latent_ch
                torch.save({'model': model.ae.state_dict(), 'args': save_args, 'epoch': epoch}, ae_ckpt_path)
                print(f"  -> Saved best AE to {ae_ckpt_path} (latent_ch={latent_ch})")
    
    # ========== Stage 2: AE 고정 + Attention branch 학습 ==========
    print("\n" + "="*60)
    print("Stage 2: AE 고정, Attention branch 학습")
    print("="*60)
    
    # AE 怨좎젙
    for param in model.ae.parameters():
        param.requires_grad = False
    print("  -> AE weights frozen")
    
    # Attention branch留??숈뒿
    att_params = list(model.att.parameters()) + list(model.head_score.parameters())
    optim_att = torch.optim.Adam(att_params, lr=args.lr * 0.5)  # ???묒? learning rate
    
    best_att_loss = 1e9
    att_ckpt_path = os.path.join(args.checkpoint_dir, 'dual_att_best.pt')
    
    model.train()
    for epoch in range(1, args.epochs // 2 + 1):  # ?덈컲 ?먰룷?щ쭔
        running = 0.0
        pbar = tqdm(train_loader, desc=f"[Att Stage2][Ep {epoch}/{args.epochs//2}]")
        for x, _ in pbar:
            x = x.to(device)
            with torch.no_grad():
                xrec, z = model.ae(x)
            
            # Attention branch留?forward
            z_map, cam_w, sam_w = model.att(z)
            s_feat_lat = model.head_score(z_map)
            
            # Feature score loss (?뺤긽 ?곗씠?곕뒗 ??? ?ㅼ퐫??
            target_score = 0.15
            loss = F.mse_loss(s_feat_lat.mean(), torch.tensor(target_score, device=device))
            
            if args.stability_weight > 0 and epoch > getattr(args, 'stability_warmup', 5):
                stab = stability_penalty(s_feat_lat, args.stability_target)
                loss = loss + args.stability_weight * stab
            
            optim_att.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(att_params, max_norm=0.5)
            optim_att.step()
            running += loss.item() * x.size(0)
            pbar.set_postfix(loss=float(loss.item()))
        
        epoch_loss = running / len(train_loader.dataset)
        print(f"Epoch {epoch} Att Loss: {epoch_loss:.6f}")
        if epoch_loss < best_att_loss:
            best_att_loss = epoch_loss
            torch.save({
                'att': model.att.state_dict(),
                'head_score': model.head_score.state_dict(),
                'args': vars(args),
                'epoch': epoch
            }, att_ckpt_path)
            print(f"  -> Saved best Attention to {att_ckpt_path}")
    
    # ========== Stage 3: ?꾩껜 紐⑤뜽 fine-tuning ==========
    print("\n" + "="*60)
    print("Stage 3: ?꾩껜 紐⑤뜽 fine-tuning")
    print("="*60)
    
    # 紐⑤뱺 ?뚮씪誘명꽣 ?숈뒿 媛?ν븯?꾨줉
    for param in model.parameters():
        param.requires_grad = True
    
    # Alpha/Beta head에 다른 learning rate
    alpha_beta_params = list(model.head_alpha.parameters()) + list(model.head_beta.parameters())
    other_params = [p for p in model.parameters() if p not in set(alpha_beta_params)]
    
    optim_ = torch.optim.Adam([
        {'params': other_params, 'lr': args.lr * 0.1},  # 기본 파라미터는 낮은 LR
        {'params': alpha_beta_params, 'lr': args.lr}      # Alpha/Beta는 높은 LR
    ])
    
    best_loss = 1e9
    ckpt_path = os.path.join(args.checkpoint_dir, 'dual_best.pt')
    
    use_robust_loss = getattr(args, 'use_robust_loss', True)
    consistency_weight = getattr(args, 'consistency_weight', 0.0)
    
    if use_robust_loss:
        recon_loss_fn = HuberLoss(delta=0.1)
        score_loss_fn = RobustScoreLoss(percentile=95.0)
        print("  -> Using robust loss functions (Huber + RobustScore)")
    else:
        recon_loss_fn = None
        score_loss_fn = None
    
    model.train()
    for epoch in range(1, args.epochs + 1):
        running_recon = 0.0
        running_score = 0.0
        pbar = tqdm(train_loader, desc=f"[Dual Stage3][Ep {epoch}/{args.epochs}]")
        for x, _ in pbar:
            x = x.to(device)
            xrec, score, s_recon, s_feat, r = model(x)
            
            # Reconstruction loss
            if use_robust_loss and recon_loss_fn is not None:
                base_recon = recon_loss_fn(xrec, x)
            else:
                base_recon = F.l1_loss(xrec, x)
            ssim_term = ssim_loss(to_minus_one_one(xrec), to_minus_one_one(x))
            loss_recon = 0.7 * base_recon + 0.3 * ssim_term
            
            # Score loss (紐⑺몴 ?ㅼ퐫?대줈 ?섎졃)
            target_score = 0.15
            if use_robust_loss and score_loss_fn is not None:
                robust_loss = score_loss_fn(score)
                target_loss = F.mse_loss(score.mean(), torch.tensor(target_score, device=device))
                loss_score = 0.5 * robust_loss + 0.5 * target_loss
            else:
                loss_score = F.mse_loss(score.mean(), torch.tensor(target_score, device=device))
            
            # Combined loss
            stability_term = 0.0
            if args.stability_weight > 0 and epoch > getattr(args, 'stability_warmup', 5):
                stability_term = stability_penalty(score.clamp(min=0.0, max=1.0), args.stability_target)
            consistency_term = 0.0
            if consistency_weight > 0:
                consistency_term = F.l1_loss(s_feat, s_recon.detach())
            
            loss = (
                loss_recon
                + 0.5 * loss_score
                + args.stability_weight * stability_term
                + consistency_weight * consistency_term
            )
            
            optim_.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)  # ??媛뺥븳 clipping
            optim_.step()
            
            running_recon += loss_recon.item() * x.size(0)
            running_score += loss_score.item() * x.size(0)
            pbar.set_postfix(recon=float(loss_recon.item()), score=float(loss_score.item()))
        
        epoch_loss_recon = running_recon / len(train_loader.dataset)
        epoch_loss_score = running_score / len(train_loader.dataset)
        print(f"Epoch {epoch} Recon: {epoch_loss_recon:.6f}, Score: {epoch_loss_score:.6f}")
        
        total_loss = epoch_loss_recon + 0.5 * epoch_loss_score
        if total_loss < best_loss:
            best_loss = total_loss
            # latent_ch를 args에 명시적으로 추가
            save_args = vars(args).copy()
            save_args['latent_ch'] = latent_ch
            torch.save({'model': model.state_dict(), 'args': save_args, 'epoch': epoch}, ckpt_path)
            print(f"  -> Saved best to {ckpt_path} (latent_ch={latent_ch})")



