#!/usr/bin/env python3
"""
추론 모듈
"""

import os
import json
import numpy as np
import torch
import torch.nn.functional as F
from tqdm import tqdm

from .model import SimpleAE, ImageAnomalyDual
from .environment import get_dataloaders, get_limited_test_loader, get_balanced_test_loader
from .utils import (ensure_dir, save_image, overlay_heatmap_on_image,
                    minmax_norm, percentile_norm, enhance_heatmap_contrast,
                    enhance_heatmap_with_threshold, compute_robust_score)


def infer_autoencoder(args):
    """Autoencoder 추론
    Args:
        args: 명령행 인자 객체
    """
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 테스트 데이터로 균형 잡힌 로더 사용
    test_loader = get_balanced_test_loader(args.data_root, args.img_size,
                                           args.num_workers, args.clahe,
                                           match_abnormal_to_normal=True)
    
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model = SimpleAE(in_ch=1).to(device)
    model.load_state_dict(ckpt['model'])
    model.eval()
    ensure_dir(args.out_dir)

    all_scores = []
    with torch.no_grad():
        for i, (x, y) in enumerate(tqdm(test_loader, desc='[AE Infer]')):
            x = x.to(device)
            xrec, _ = model(x)  # z는 반환하지 않으므로 제외
            err = torch.abs(xrec - x)
            score_img = err.mean().item()
            all_scores.append({'idx': i, 'label': int(y.item()), 'score': score_img})

            err_map = err[0, 0].cpu().numpy()
            # Percentile 정규화로 강한 부분만 강조 (99.5th percentile)
            err_map = percentile_norm(err_map, low_percentile=0.0, high_percentile=99.5)
            # 대비를 높여서 상위 2%만 강조하도록, 나머지 경우는 약하게 표시
            err_map_enhanced = enhance_heatmap_contrast(err_map, threshold_percentile=98.0, 
                                                        gamma=0.2, suppress_low=0.01, enhance_high=True)
            
            img_np = minmax_norm(x[0, 0].cpu().numpy())
            # 오버레이 히트맵을 합성 사용 (임계값은 0.3, alpha 0.7로 설정)
            overlay = overlay_heatmap_on_image(img_np, err_map_enhanced, alpha=0.7, threshold=0.3, use_hot_cmap=True)

            # Score를 포함한 파일명으로 저장 (경우에 따라 z-score도 함께 저장)
            prefix = f"{i:05d}_label{int(y.item())}_score{score_img:.2e}"
            save_image(img_np, os.path.join(args.out_dir, f"{prefix}_input.png"))
            save_image(xrec[0, 0].cpu().numpy(), os.path.join(args.out_dir, f"{prefix}_recon.png"))
            # Error 히트맵을 컬러맵으로 저장
            save_image(err_map_enhanced, os.path.join(args.out_dir, f"{prefix}_err.png"), use_colormap=True, cmap_name='hot')
            save_image(overlay, os.path.join(args.out_dir, f"{prefix}_overlay.png"))

    with open(os.path.join(args.out_dir, 'ae_scores.json'), 'w') as f:
        json.dump(all_scores, f, indent=2)
    print(f"Saved results to {args.out_dir}")


def infer_dual_anomaly(args):
    """ImageAnomalyDual 모델 추론
    Args:
        args: 명령행 인자 객체
    """
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 테스트 데이터로 균형 잡힌 로더 사용 (match_abnormal_to_normal=True)
    test_loader = get_balanced_test_loader(args.data_root, args.img_size,
                                           args.num_workers, args.clahe,
                                           match_abnormal_to_normal=True)
    
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    state_dict = ckpt['model']
    
    # latent_ch는 명시적으로 256으로 설정 (이미지 해상도 256x256에 맞춤)
    # 체크포인트의 latent_ch를 따르지 않고 항상 args.latent_ch 또는 기본값 256 사용
    latent_ch = getattr(args, 'latent_ch', 256)
    
    # 체크포인트의 latent_ch 확인 (참고용)
    ckpt_latent_ch = None
    if 'args' in ckpt and 'latent_ch' in ckpt['args']:
        ckpt_latent_ch = ckpt['args']['latent_ch']
    else:
        # 체크포인트의 마지막 레이어 크기로 추정
        if 'ae.enc.14.weight' in state_dict:
            ckpt_latent_ch = state_dict['ae.enc.14.weight'].shape[0]
        elif 'enc.14.weight' in state_dict:
            ckpt_latent_ch = state_dict['enc.14.weight'].shape[0]
    
    if ckpt_latent_ch is not None and ckpt_latent_ch != latent_ch:
        print(f"[WARN] Checkpoint has latent_ch={ckpt_latent_ch}, but using latent_ch={latent_ch} (이미지 해상도에 맞춤)")
        print(f"[WARN] 체크포인트를 latent_ch={latent_ch}로 새로 학습하세요.")
    else:
        print(f"[INFO] Using latent_ch={latent_ch} (이미지 해상도 256x256에 맞춤)")
    
    # Fusion 모듈 확인
    has_fusion = any('fusion.' in key for key in state_dict.keys())
    if 'args' in ckpt and 'use_fusion' in ckpt['args']:
        use_fusion = ckpt['args']['use_fusion']
    else:
        use_fusion = has_fusion
    
    model = ImageAnomalyDual(in_ch=1, latent_ch=latent_ch, use_fusion=use_fusion).to(device)
    
    # Fusion 모듈이 없는 경우 fusion 파라미터 필터링
    if not use_fusion and has_fusion:
        filtered_state_dict = {k: v for k, v in state_dict.items() if 'fusion.' not in k}
        model.load_state_dict(filtered_state_dict, strict=False)
        print(f"[INFO] Fusion 모듈 제외하고 체크포인트 로드 (전체 {len(state_dict)}개 중 {len(filtered_state_dict)}개 사용)")
    else:
        model.load_state_dict(state_dict, strict=False)
    model.eval()
    ensure_dir(args.out_dir)

    # 이전 결과에서 threshold 로드 (없으면 사용 안 함)
    threshold = None
    eval_json_path = getattr(args, 'eval_json_path', None) or 'evaluation_results/evaluation_results.json'
    if os.path.exists(eval_json_path):
        try:
            with open(eval_json_path, 'r') as f:
                eval_data = json.load(f)
                threshold = eval_data.get('binary_classification', {}).get('threshold')
                if threshold is not None:
                    print(f"[INFO] 모델 threshold 사용: {threshold:.6e}")
        except Exception as e:
            print(f"[WARN] threshold 로드 실패: {e}, percentile 정규화 사용")
    
    # threshold가 없으면 처음 몇 개에서 자동으로 threshold 계산 (상위 1% 평균으로 설정)
    if threshold is None:
        # 처음 몇 개를 로드하여 자동으로 threshold 설정
        temp_scores = []
        with torch.no_grad():
            for i, (x, y) in enumerate(test_loader):
                if i >= 10:  # 처음 10개만
                    break
                x = x.to(device)
                xrec, score, _, _, _ = model(x)
                score_np = score[0, 0].cpu().numpy()
                flat = score_np.reshape(-1)
                k = max(1, int(0.02 * flat.size))
                score_img = float(np.mean(np.sort(flat)[-k:]))
                temp_scores.append(score_img)
        # 정상 데이터의 평균값을 자동으로 threshold로 사용
        if len(temp_scores) > 0:
            threshold = np.median(temp_scores) * 1.5  # 중앙값의 1.5배
            print(f"[INFO] 자동 threshold 사용: {threshold:.6e}")

    # Validation-normal score 통계 로드 (없으면 사용 안 함)
    val_stats_path = args.val_stats_path if hasattr(args, 'val_stats_path') and args.val_stats_path else None
    if val_stats_path is None:
        # 기본 경로 확인
        default_path = os.path.join(args.checkpoint_dir, 'val_normal_stats.json')
        if os.path.exists(default_path):
            val_stats_path = default_path
    val_mean = None
    val_std = None
    if val_stats_path is not None and os.path.exists(val_stats_path):
        try:
            with open(val_stats_path, 'r') as f:
                val_stats = json.load(f)
                val_mean = val_stats.get('mean')
                val_std = val_stats.get('std')
                if val_mean is not None and val_std is not None:
                    print(f"[INFO] Validation-normal 통계 사용: mean={val_mean:.6e}, std={val_std:.6e}")
        except Exception as e:
            print(f"[WARN] Validation 통계 로드 실패: {e}, raw score 사용")
    
    all_scores = []
    all_raw_scores = []  # z-score 계산을 위한 raw score 저장
    with torch.no_grad():
        for i, (x, y) in enumerate(tqdm(test_loader, desc='[Dual Infer]')):
            x = x.to(device)
            xrec, score, s_recon, s_feat, r = model(x)
            
            # 이미지별로 상위 k% 평균으로 집계(per-image min-max 제거)
            score_np = score[0, 0].detach().cpu().numpy()
            flat = score_np.ravel()
            k = max(1, int(len(flat) * 0.02))  # 상위 2% 평균
            score_img_raw = float(np.mean(np.sort(flat)[-k:]))
            all_raw_scores.append(score_img_raw)
            
            # z-score 표준화(validation 통계가 있으면 사용)
            if val_mean is not None and val_std is not None and val_std > 0:
                score_img = (score_img_raw - val_mean) / val_std
            else:
                score_img = score_img_raw  # 통계가 없으면 raw score 사용
            
            all_scores.append({'idx': i, 'label': int(y.item()), 'score': score_img, 'score_raw': score_img_raw})

            # 히트맵 생성 - raw score 사용 (per-image min-max 제거)
            if threshold is not None:
                # threshold를 raw score 기준으로 변환(z-score인 경우)
                if val_mean is not None and val_std is not None and val_std > 0:
                    threshold_raw = threshold * val_std + val_mean
                else:
                    threshold_raw = threshold
                score_map_enhanced = enhance_heatmap_with_threshold(
                    score_np, threshold_raw, 
                    gamma=0.3, 
                    suppress_factor=0.02,
                    show_below_threshold=True,
                    below_threshold_max=0.4
                )
            else:
                # threshold가 없으면 percentile 정규화 사용 (fallback)
                score_map_enhanced = enhance_heatmap_contrast(score_np, threshold_percentile=98.0, 
                                                              gamma=0.2, suppress_low=0.01, enhance_high=True)
            
            # s_recon (복원 오차): 기본 값 사용, threshold 기준
            s_recon_np = s_recon[0, 0].cpu().numpy()
            # s_recon을 0~1 범위로 변환하여 threshold를 적용하여 변환
            if threshold is not None:
                # s_recon의 값 범위를 고려하여 threshold 설정
                s_recon_threshold = np.percentile(s_recon_np, 95)  # s_recon의 대부분을 고려하여 95th 사용
                s_recon_enhanced = enhance_heatmap_with_threshold(s_recon_np, s_recon_threshold,
                                                                  gamma=0.4, suppress_factor=0.01)
            else:
                s_recon_normed = percentile_norm(s_recon_np, low_percentile=0.0, high_percentile=99.9)
                s_recon_enhanced = enhance_heatmap_contrast(s_recon_normed, threshold_percentile=99.0, 
                                                            gamma=0.3, suppress_low=0.005, enhance_high=False)
            
            # s_feat (특징 영역): 기본 값 사용, threshold 기준 (동일한 threshold로 강조)
            s_feat_np = s_feat[0, 0].cpu().numpy()
            # s_feat를 고려하여 상위만 강조하도록 threshold 사용
            if threshold is not None:
                # s_feat의 값 범위를 고려하여 threshold 설정 (상위만 설정)
                s_feat_threshold = np.percentile(s_feat_np, 90)  # s_feat의 상위만 고려하여 90th 사용
                s_feat_enhanced = enhance_heatmap_with_threshold(s_feat_np, s_feat_threshold,
                                                                 gamma=0.2, suppress_factor=0.02)
            else:
                s_feat_normed = percentile_norm(s_feat_np, low_percentile=0.0, high_percentile=97.0)
                s_feat_enhanced = enhance_heatmap_contrast(s_feat_normed, threshold_percentile=95.0, 
                                                           gamma=0.2, suppress_low=0.01, enhance_high=True)
            
            img_np = minmax_norm(x[0, 0].cpu().numpy())
            # threshold 기준 오버레이 (threshold 이하 값도 표시)
            overlay = overlay_heatmap_on_image(
                img_np, score_map_enhanced, 
                alpha=0.7, 
                threshold=0.5, 
                use_hot_cmap=True,
                show_below_threshold=True  # threshold 이하 값도 표시
            )

            # Score를 포함한 파일명으로 저장 (경우에 따라 z-score도 함께 저장)
            prefix = f"{i:05d}_label{int(y.item())}_score{score_img:.2e}"
            save_image(img_np, os.path.join(args.out_dir, f"{prefix}_input.png"))
            save_image(xrec[0, 0].cpu().numpy(), os.path.join(args.out_dir, f"{prefix}_recon.png"))
            # Score 히트맵을 컬러맵으로 저장(임계값 기준 컬러맵으로 변환)
            save_image(score_map_enhanced, os.path.join(args.out_dir, f"{prefix}_score.png"), use_colormap=True, cmap_name='hot')
            # s_recon과 s_feat도 컬러맵으로 저장(정상 범위 컬러맵 적용)
            save_image(s_recon_enhanced, os.path.join(args.out_dir, f"{prefix}_s_recon.png"), use_colormap=True, cmap_name='hot')
            save_image(s_feat_enhanced, os.path.join(args.out_dir, f"{prefix}_s_feat.png"), use_colormap=True, cmap_name='hot')
            save_image(overlay, os.path.join(args.out_dir, f"{prefix}_overlay.png"))

    with open(os.path.join(args.out_dir, 'dual_scores.json'), 'w') as f:
        json.dump(all_scores, f, indent=2)
    
    # Raw score 통계 저장(validation 통계 계산용)
    if len(all_raw_scores) > 0:
        raw_stats = {
            'mean': float(np.mean(all_raw_scores)),
            'std': float(np.std(all_raw_scores)),
            'min': float(np.min(all_raw_scores)),
            'max': float(np.max(all_raw_scores)),
            'p99_5': float(np.percentile(all_raw_scores, 99.5)),
            'p95': float(np.percentile(all_raw_scores, 95)),
        }
        with open(os.path.join(args.out_dir, 'raw_score_stats.json'), 'w') as f:
            json.dump(raw_stats, f, indent=2)
        print(f"[INFO] Raw score 통계 저장: mean={raw_stats['mean']:.6e}, std={raw_stats['std']:.6e}")
    
    print(f"Saved results to {args.out_dir}")

