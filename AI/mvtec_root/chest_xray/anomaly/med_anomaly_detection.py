#!/usr/bin/env python3
"""
이미지(의료영상 JPG/PNG) 이상탐지 통합 예제
- 학습: 정상 이미지만 사용 (비지도/원클래스)
- 추론: 질병/결함 이미지에 대해 anomaly score와 heatmap 생성

포함 기능
1) Autoencoder: 복원 오차 기반 히트맵 (|x - x'|)
2) Feature-Distance: 사전학습 백본(ResNet50/WideResNet50_2) 특징거리 기반 히트맵 (간소화 PatchCore)
3) MVTec AD 형식 변환: 임의의 폴더 구조를 MVTec 표준 구조로 변환
4) 의료 친화 증강: 수평플립/소각도 회전/가벼운 이동·스케일/쉬어, CLAHE, 미세 가우시안 노이즈

데이터 폴더 구조 (MVTec 형식)
 mvtec_root/
   chest_xray/                 # --category 값
     train/
       good/                   # 정상(학습)
     test/
       good/                   # (선택)
       pneumonia/              # 결함(이상) 타입 예시
     ground_truth/
       pneumonia/              # 픽셀 GT 마스크(있으면 사용, 없으면 없어도 됨)

사용 예시
# 0) 기존 데이터 → MVTec 변환
python med_anomaly_detection.py --mode convert_to_mvtec \
  --data_root ./my_med_images --mvtec_out ./mvtec_medical --category chest_xray

# 1) Autoencoder 학습 (증강/CLAHE/노이즈 옵션)
python med_anomaly_detection.py --mode train_autoencoder \
  --data_root ./mvtec_medical/chest_xray --epochs 30 --batch_size 16 --img_size 256 \
  --aug --clahe --noise_sigma 0.01

# 2) Autoencoder 추론 + 복원오차 히트맵 저장
python med_anomaly_detection.py --mode infer_autoencoder \
  --data_root ./mvtec_medical/chest_xray --checkpoint ./checkpoints/ae_best.pt --out_dir ./outs_ae --clahe

# 3) Feature-Distance 갤러리 구축(정상 train으로)
python med_anomaly_detection.py --mode build_gallery \
  --data_root ./mvtec_medical/chest_xray --out_dir ./outs_fd --backbone wideresnet50 \
  --feat_layers layer2 layer3 --clahe --gallery_aug

# 4) Feature-Distance 추론 + 히트맵 저장
python med_anomaly_detection.py --mode infer_feature \
  --data_root ./mvtec_medical/chest_xray --gallery_path ./outs_fd/gallery.pt --out_dir ./outs_fd --clahe

필요 패키지: torch torchvision numpy pillow matplotlib tqdm scikit-image
"""

import os
import json
import random
from pathlib import Path
import argparse

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import transforms, datasets, models

from tqdm import tqdm
import matplotlib.pyplot as plt

# 선택: scikit-image (CLAHE)
try:
    from skimage import exposure as sk_exposure
except Exception:
    sk_exposure = None

# ------------------------------
# 유틸
# ------------------------------

def seed_everything(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_image(array: np.ndarray, path: str):
    arr = np.clip(array, 0, 1)
    img = Image.fromarray((arr * 255).astype(np.uint8))
    img.save(path)


def overlay_heatmap_on_image(img: np.ndarray, heat: np.ndarray, alpha: float = 0.6, 
                            threshold: float = 0.5, use_hot_cmap: bool = True):
    """이미지에 히트맵 오버레이 - 이상 영역 강조 개선
    
    Args:
        img: [H,W] 또는 [H,W,3] 형태의 이미지 (0~1 정규화)
        heat: [H,W] 형태의 히트맵 (0~1 정규화)
        alpha: 오버레이 투명도 (기본값: 0.6, 높을수록 히트맵이 더 진하게)
        threshold: 이 값 이상인 히트맵 영역만 강조 (기본값: 0.5)
        use_hot_cmap: True면 'hot' 컬러맵, False면 'jet' 컬러맵 사용
    Returns:
        오버레이된 이미지 배열
    """
    if img.ndim == 2:
        img3 = np.stack([img, img, img], axis=-1)
    else:
        img3 = img
    
    # 컬러맵 선택 (hot이 이상 영역 강조에 더 적합)
    cmap_name = 'hot' if use_hot_cmap else 'jet'
    cmap = plt.get_cmap(cmap_name)
    
    # 임계값 이상인 영역만 히트맵 강조 (가중치 적용)
    heat_enhanced = heat.copy()
    mask = heat >= threshold
    heat_enhanced[mask] = np.power(heat_enhanced[mask], 0.7)  # 감마 보정으로 강조
    heat_enhanced[~mask] = heat_enhanced[~mask] * 0.3  # 임계값 미만은 약하게
    
    heat_color = cmap(heat_enhanced)[..., :3]
    
    # 가중치 기반 오버레이 (임계값 이상 영역은 더 진하게)
    weight = np.ones_like(heat) * alpha
    weight[mask] = alpha * 1.2  # 임계값 이상 영역은 더 진하게
    weight = np.clip(weight, 0, 1)
    
    out = (1 - weight[..., None]) * img3 + weight[..., None] * heat_color
    return np.clip(out, 0, 1)


def minmax_norm(x: np.ndarray, eps: float = 1e-8):
    m, M = x.min(), x.max()
    return (x - m) / (M - m + eps)


def percentile_norm(x: np.ndarray, low_percentile: float = 0.0, high_percentile: float = 100.0, eps: float = 1e-8):
    """Percentile 기반 정규화 - 이상 영역 강조에 유용
    
    Args:
        x: 정규화할 배열
        low_percentile: 하한 percentile (기본값: 0.0)
        high_percentile: 상한 percentile (기본값: 100.0)
        eps: 안정성을 위한 작은 값
    Returns:
        정규화된 배열 (0~1 범위)
    """
    p_low = np.percentile(x, low_percentile)
    p_high = np.percentile(x, high_percentile)
    x_clipped = np.clip(x, p_low, p_high)
    if p_high - p_low < eps:
        return np.zeros_like(x)
    return (x_clipped - p_low) / (p_high - p_low + eps)

# ------------------------------
# 데이터 + 변환/증강
# ------------------------------

class CLAHETransform:
    def __init__(self, clip_limit=0.01):
        self.clip_limit = clip_limit
    def __call__(self, img: Image.Image):
        arr = np.array(img).astype(np.float32)
        if arr.ndim == 3:
            arr = arr[..., 0]
        arr = arr / 255.0
        if sk_exposure is not None:
            arr = sk_exposure.equalize_adapthist(arr, clip_limit=self.clip_limit)
        arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        return Image.fromarray(arr)

class GaussianNoiseTransform:
    def __init__(self, sigma=0.01):
        self.sigma = sigma
    def __call__(self, tensor: torch.Tensor):
        return torch.clamp(tensor + torch.randn_like(tensor) * self.sigma, 0.0, 1.0)


def build_transforms(img_size: int = 256, grayscale: bool = True, augment: bool = False, use_clahe: bool = False, noise_sigma: float = 0.0):
    # Train
    t_train: list = []
    if grayscale:
        t_train.append(transforms.Grayscale(num_output_channels=1))
    if use_clahe:
        t_train.append(CLAHETransform(clip_limit=0.01))
    t_train.append(transforms.Resize((img_size, img_size)))
    if augment:
        t_train.extend([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=5, fill=0),
            transforms.RandomAffine(degrees=0, translate=(0.02, 0.02), scale=(0.98, 1.02), shear=1.5, fill=0),
        ])
    t_train.append(transforms.ToTensor())
    if noise_sigma > 0.0:
        t_train.append(GaussianNoiseTransform(sigma=noise_sigma))

    # Test
    t_test: list = []
    if grayscale:
        t_test.append(transforms.Grayscale(num_output_channels=1))
    if use_clahe:
        t_test.append(CLAHETransform(clip_limit=0.01))
    t_test.extend([transforms.Resize((img_size, img_size)), transforms.ToTensor()])

    return transforms.Compose(t_train), transforms.Compose(t_test)


def get_dataloaders(data_root: str, img_size: int, batch_size: int, num_workers: int = 4, augment: bool = False, use_clahe: bool = False, noise_sigma: float = 0.0):
    train_tf, test_tf = build_transforms(img_size, grayscale=True, augment=augment, use_clahe=use_clahe, noise_sigma=noise_sigma)
    train_dir = os.path.join(data_root, 'train')
    test_dir = os.path.join(data_root, 'test')
    train_ds = datasets.ImageFolder(train_dir, transform=train_tf)  # train/good 만 존재 가정
    test_ds  = datasets.ImageFolder(test_dir, transform=test_tf)   # test/good + test/<defect>
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=num_workers, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=1,           shuffle=False, num_workers=num_workers, pin_memory=True)
    return train_loader, test_loader


def convert_to_mvtec(src_root: str, dst_root: str, category: str):
    """임의의 (train/test/normal/anomaly/ground_truth) 구조를 MVTec 형식으로 변환.
    src_root/
      train/normal/
      test/normal/                    (선택)
      test/anomaly/<defect>/...       (옵션1)
      test/<defect>/(images|masks)/   (옵션2)
      test/ground_truth/<defect>/...  (옵션3)
    -> dst_root/<category>/{train,groud_truth,test}/...
    """
    import shutil
    src = Path(src_root)
    cat = Path(dst_root) / category
    tr_good = cat / 'train' / 'good'
    te_good = cat / 'test' / 'good'
    gt_dir  = cat / 'ground_truth'
    for p in [tr_good, te_good, gt_dir]:
        p.mkdir(parents=True, exist_ok=True)

    def copy_all(s: Path, d: Path):
        if not s.exists():
            return
        d.mkdir(parents=True, exist_ok=True)
        for fp in sorted(s.rglob('*')):
            if fp.is_file():
                shutil.copy2(fp, d / fp.name)

    # train/good & test/good
    copy_all(src / 'train' / 'normal', tr_good)
    copy_all(src / 'test'  / 'normal', te_good)

    test_root = src / 'test'
    anomaly_parent = test_root / 'anomaly'
    if anomaly_parent.exists():
        defect_dirs = [d for d in anomaly_parent.iterdir() if d.is_dir()]
    else:
        defect_dirs = [d for d in test_root.iterdir() if d.is_dir() and d.name not in ['normal', 'ground_truth']]

    for d in defect_dirs:
        defect = d.name
        img_dir = d / 'images' if (d / 'images').exists() else d
        mask_dir = d / 'masks'
        alt_mask_dir = test_root / 'ground_truth' / defect
        dst_img = cat / 'test' / defect
        dst_gt  = cat / 'ground_truth' / defect
        copy_all(img_dir, dst_img)
        if mask_dir.exists():
            copy_all(mask_dir, dst_gt)
        elif alt_mask_dir.exists():
            copy_all(alt_mask_dir, dst_gt)

    print(f'[convert_to_mvtec] Converted to {cat}')

# ------------------------------
# 1) Autoencoder
# ------------------------------

class SimpleAE(nn.Module):
    def __init__(self, in_ch: int = 1, latent_ch: int = 128):
        super().__init__()
        self.enc = nn.Sequential(
            nn.Conv2d(in_ch, 32, 3, 2, 1), nn.ReLU(True),
            nn.Conv2d(32, 64, 3, 2, 1), nn.ReLU(True),
            nn.Conv2d(64, 128, 3, 2, 1), nn.ReLU(True),
            nn.Conv2d(128, latent_ch, 3, 2, 1), nn.ReLU(True),
        )
        self.dec = nn.Sequential(
            nn.ConvTranspose2d(latent_ch, 128, 4, 2, 1), nn.ReLU(True),
            nn.ConvTranspose2d(128, 64, 4, 2, 1), nn.ReLU(True),
            nn.ConvTranspose2d(64, 32, 4, 2, 1), nn.ReLU(True),
            nn.ConvTranspose2d(32, in_ch, 4, 2, 1), nn.Sigmoid(),
        )
    def forward(self, x):
        z = self.enc(x)
        xrec = self.dec(z)
        return xrec


def train_autoencoder(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    seed_everything(args.seed)
    train_loader, _ = get_dataloaders(args.data_root, args.img_size, args.batch_size, args.num_workers, augment=args.aug, use_clahe=args.clahe, noise_sigma=args.noise_sigma)
    model = SimpleAE(in_ch=1).to(device)
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
            xrec = model(x)
            loss = F.l1_loss(xrec, x)
            optim_.zero_grad(); loss.backward(); optim_.step()
            running += loss.item() * x.size(0)
            pbar.set_postfix(loss=float(loss.item()))
        epoch_loss = running / len(train_loader.dataset)
        print(f"Epoch {epoch} MAE: {epoch_loss:.6f}")
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            torch.save({'model': model.state_dict(), 'args': vars(args), 'epoch': epoch}, ckpt_path)
            print(f"  -> Saved best to {ckpt_path}")


def infer_autoencoder(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    _, test_loader = get_dataloaders(args.data_root, args.img_size, batch_size=1, num_workers=args.num_workers, augment=False, use_clahe=args.clahe, noise_sigma=0.0)
    ckpt = torch.load(args.checkpoint, map_location=device)
    model = SimpleAE(in_ch=1).to(device)
    model.load_state_dict(ckpt['model'])
    model.eval()
    ensure_dir(args.out_dir)

    all_scores = []
    with torch.no_grad():
        for i, (x, y) in enumerate(tqdm(test_loader, desc='[AE Infer]')):
            x = x.to(device)
            xrec = model(x)
            err = torch.abs(xrec - x)
            score_img = err.mean().item()
            all_scores.append({'idx': i, 'label': int(y.item()), 'score': score_img})

            err_map = err[0, 0].cpu().numpy()
            # Percentile 기반 정규화로 이상 영역 강조 (상위 5% 강조)
            err_map = percentile_norm(err_map, low_percentile=0.0, high_percentile=95.0)
            img_np = minmax_norm(x[0, 0].cpu().numpy())
            # 개선된 오버레이 함수 사용 (임계값 0.7, hot 컬러맵)
            overlay = overlay_heatmap_on_image(img_np, err_map, alpha=0.6, threshold=0.7, use_hot_cmap=True)

            prefix = f"{i:05d}_label{int(y.item())}_score{score_img:.4f}"
            save_image(img_np, os.path.join(args.out_dir, f"{prefix}_input.png"))
            save_image(xrec[0, 0].cpu().numpy(), os.path.join(args.out_dir, f"{prefix}_recon.png"))
            save_image(err_map, os.path.join(args.out_dir, f"{prefix}_err.png"))
            save_image(overlay, os.path.join(args.out_dir, f"{prefix}_overlay.png"))

    with open(os.path.join(args.out_dir, 'ae_scores.json'), 'w') as f:
        json.dump(all_scores, f, indent=2)
    print(f"Saved results to {args.out_dir}")

# ------------------------------
# 2) Feature-distance (간소 PatchCore)
# ------------------------------

class FeatureExtractor(nn.Module):
    def __init__(self, backbone: str = 'wideresnet50', layers=('layer2', 'layer3'), pretrained=True):
        super().__init__()
        if backbone.lower() in ['resnet50', 'rn50']:
            m = models.resnet50(weights=models.ResNet50_Weights.DEFAULT if pretrained else None)
        else:
            m = models.wide_resnet50_2(weights=models.Wide_ResNet50_2_Weights.DEFAULT if pretrained else None)
        self.backbone = m
        self.layers = layers
        self._features = {}
        self._register_hooks()
    def _register_hooks(self):
        def save_output(name):
            def fn(_, __, out):
                self._features[name] = out
            return fn
        for name in self.layers:
            getattr(self.backbone, name).register_forward_hook(save_output(name))
    def forward(self, x):
        _ = self.backbone(x)
        return [self._features[name] for name in self.layers]


def build_gallery(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    train_loader, _ = get_dataloaders(args.data_root, args.img_size, args.batch_size, args.num_workers, augment=args.gallery_aug, use_clahe=args.clahe, noise_sigma=0.0)
    to3 = lambda t: t.repeat(1, 3, 1, 1)
    extractor = FeatureExtractor(backbone=args.backbone, layers=tuple(args.feat_layers)).to(device)
    extractor.eval()

    gallery = []
    with torch.no_grad():
        for x, _ in tqdm(train_loader, desc='[Build Gallery]'):
            x = to3(x.to(device))
            feats = extractor(x)  # list of [B,C,H,W]
            target_hw = feats[0].shape[-2:]
            ups = [F.interpolate(f, size=target_hw, mode='bilinear', align_corners=False) for f in feats]
            fcat = torch.cat(ups, dim=1)  # [B, Csum, H, W]
            fcat = F.normalize(fcat, p=2, dim=1)
            B, C, H, W = fcat.shape
            fvec = fcat.permute(0, 2, 3, 1).reshape(B * H * W, C)
            gallery.append(fvec.cpu())
    gallery = torch.cat(gallery, dim=0)

    n = gallery.size(0)
    keep = min(args.gallery_max, n)
    idx = torch.randperm(n)[:keep]
    gallery_small = gallery[idx]

    ensure_dir(args.out_dir)
    torch.save({'gallery': gallery_small, 'args': vars(args)}, os.path.join(args.out_dir, 'gallery.pt'))
    print(f"Saved gallery with {keep} vectors to {os.path.join(args.out_dir, 'gallery.pt')}")


def cosine_distance(a: torch.Tensor, b: torch.Tensor):
    a = F.normalize(a, p=2, dim=1)
    b = F.normalize(b, p=2, dim=1)
    return 1 - a @ b.t()


def infer_feature_distance(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    _, test_loader = get_dataloaders(args.data_root, args.img_size, batch_size=1, num_workers=args.num_workers, augment=False, use_clahe=args.clahe, noise_sigma=0.0)
    ck = torch.load(args.gallery_path, map_location='cpu')
    gallery = ck['gallery'].to(device)  # [G,C]

    to3 = lambda t: t.repeat(1, 3, 1, 1)
    extractor = FeatureExtractor(backbone=args.backbone, layers=tuple(args.feat_layers)).to(device)
    extractor.eval()

    ensure_dir(args.out_dir)
    results = []

    with torch.no_grad():
        for i, (x, y) in enumerate(tqdm(test_loader, desc='[FD Infer]')):
            x3 = to3(x.to(device))
            feats = extractor(x3)
            target_hw = feats[0].shape[-2:]
            ups = [F.interpolate(f, size=target_hw, mode='bilinear', align_corners=False) for f in feats]
            fcat = torch.cat(ups, dim=1)  # [1, Csum, H, W]
            fcat = F.normalize(fcat, p=2, dim=1)
            _, C, H, W = fcat.shape
            fvec = fcat.permute(0, 2, 3, 1).reshape(H * W, C)

            # 최근접 거리(코사인) - 메모리 절약을 위한 청크 처리
            chunk = 8192
            mins = []
            for st in range(0, fvec.size(0), chunk):
                ed = min(st + chunk, fvec.size(0))
                d = cosine_distance(fvec[st:ed], gallery)  # [chunk, G]
                mins.append(d.min(dim=1).values)
            dmin = torch.cat(mins, dim=0)  # [HW]

            heat = dmin.reshape(H, W).cpu().numpy()
            # Percentile 기반 정규화로 이상 영역 강조 (상위 5% 강조)
            heat = percentile_norm(heat, low_percentile=0.0, high_percentile=95.0)
            if (H, W) != (args.img_size, args.img_size):
                heat_t = torch.tensor(heat)[None, None]
                heat = F.interpolate(heat_t, size=(args.img_size, args.img_size), mode='bilinear', align_corners=False)[0, 0].cpu().numpy()
                # 보간 후 다시 정규화
                heat = percentile_norm(heat, low_percentile=0.0, high_percentile=95.0)

            img_np = minmax_norm(x[0, 0].cpu().numpy())
            # 개선된 오버레이 함수 사용 (임계값 0.7, hot 컬러맵)
            overlay = overlay_heatmap_on_image(img_np, heat, alpha=0.6, threshold=0.7, use_hot_cmap=True)

            # 이미지 레벨 스코어: 상위 1% 평균
            flat = heat.reshape(-1)
            k = max(1, int(0.01 * flat.size))
            score = float(np.mean(np.sort(flat)[-k:]))
            results.append({'idx': i, 'label': int(y.item()), 'score': score})

            prefix = f"{i:05d}_label{int(y.item())}_score{score:.4f}"
            save_image(img_np, os.path.join(args.out_dir, f"{prefix}_input.png"))
            save_image(heat,   os.path.join(args.out_dir, f"{prefix}_fd_heat.png"))
            save_image(overlay,os.path.join(args.out_dir, f"{prefix}_fd_overlay.png"))

    with open(os.path.join(args.out_dir, 'fd_scores.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved FD results to {args.out_dir}")

# ------------------------------
# 메인
# ------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', type=str, required=True,
                   choices=['convert_to_mvtec', 'train_autoencoder', 'infer_autoencoder', 'build_gallery', 'infer_feature'])
    p.add_argument('--data_root', type=str, required=True, help='(convert: src_root / train,infer: mvtec 카테고리 루트)')
    p.add_argument('--img_size', type=int, default=256)
    p.add_argument('--batch_size', type=int, default=16)
    p.add_argument('--num_workers', type=int, default=4)
    p.add_argument('--seed', type=int, default=42)
    # 증강 옵션
    p.add_argument('--aug', action='store_true', help='학습 시 데이터 증강 사용 (AE)')
    p.add_argument('--gallery_aug', action='store_true', help='갤러리 구축 시 약한 증강 사용 (FD)')
    p.add_argument('--clahe', action='store_true', help='CLAHE 대비 보정 사용')
    p.add_argument('--noise_sigma', type=float, default=0.0, help='ToTensor 이후 가우시안 노이즈 표준편차')
    # AE
    p.add_argument('--epochs', type=int, default=30)
    p.add_argument('--lr', type=float, default=1e-3)
    p.add_argument('--checkpoint_dir', type=str, default='./checkpoints')
    p.add_argument('--checkpoint', type=str, help='AE 추론용 체크포인트 경로')
    # Feature Distance
    p.add_argument('--backbone', type=str, default='wideresnet50', choices=['wideresnet50', 'resnet50'])
    p.add_argument('--feat_layers', nargs='+', default=['layer2', 'layer3'])
    p.add_argument('--gallery_max', type=int, default=20000, help='갤러리에 보관할 특징 벡터 수 상한')
    p.add_argument('--gallery_path', type=str, help='저장된 gallery.pt 경로')
    # Convert -> MVTec
    p.add_argument('--mvtec_out', type=str, help='MVTec 형식 출력 루트 (convert 모드에서 필수)')
    p.add_argument('--category', type=str, default='medical', help='카테고리명 (하위 폴더)')
    # Output
    p.add_argument('--out_dir', type=str, default='./outs')
    return p.parse_args()


def main():
    args = parse_args()
    if args.mode == 'convert_to_mvtec':
        assert args.mvtec_out, '--mvtec_out required'
        convert_to_mvtec(args.data_root, args.mvtec_out, args.category)
    elif args.mode == 'train_autoencoder':
        train_autoencoder(args)
    elif args.mode == 'infer_autoencoder':
        assert args.checkpoint, '--checkpoint required'
        ensure_dir(args.out_dir)
        infer_autoencoder(args)
    elif args.mode == 'build_gallery':
        ensure_dir(args.out_dir)
        build_gallery(args)
    elif args.mode == 'infer_feature':
        assert args.gallery_path, '--gallery_path required'
        ensure_dir(args.out_dir)
        infer_feature_distance(args)

if __name__ == '__main__':
    main()
