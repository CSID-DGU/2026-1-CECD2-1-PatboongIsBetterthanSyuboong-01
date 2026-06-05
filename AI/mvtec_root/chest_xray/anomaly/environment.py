#!/usr/bin/env python3
"""
데이터 변환 및 환경 설정 모듈
"""

import os
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch.utils.data import DataLoader
from torchvision import transforms, datasets

# 선택: scikit-image (CLAHE)
try:
    from skimage import exposure as sk_exposure
except Exception:
    sk_exposure = None


class CLAHETransform:
    """CLAHE (Contrast Limited Adaptive Histogram Equalization) 변환"""
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
    """가우시안 노이즈 추가 변환"""
    def __init__(self, sigma=0.01):
        self.sigma = sigma
    
    def __call__(self, tensor: torch.Tensor):
        return torch.clamp(tensor + torch.randn_like(tensor) * self.sigma, 0.0, 1.0)


def build_transforms(img_size: int = 256, grayscale: bool = True, augment: bool = False,
                     use_clahe: bool = False, noise_sigma: float = 0.0):
    """데이터 변환 파이프라인 구축
    Args:
        img_size: 이미지 크기
        grayscale: 그레이스케일 변환 여부
        augment: 데이터 증강 사용 여부
        use_clahe: CLAHE 사용 여부
        noise_sigma: 가우시안 노이즈 표준편차
    Returns:
        (train_transform, test_transform) 튜플
    """
    # Train 변환
    t_train: list = []
    if grayscale:
        t_train.append(transforms.Grayscale(num_output_channels=1))
    if use_clahe:
        t_train.append(CLAHETransform(clip_limit=0.01))
    if augment:
        # 약한 증강: Flip/Rotate/CLAHE 정도로 "정상 패턴"을 더 날카롭게 학습
        t_train.append(transforms.Resize((img_size, img_size)))
        t_train.extend([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomApply([transforms.RandomRotation(degrees=5, fill=0)], p=0.5),
        ])
    else:
        t_train.append(transforms.Resize((img_size, img_size)))
    t_train.append(transforms.ToTensor())
    if noise_sigma > 0.0:
        t_train.append(GaussianNoiseTransform(sigma=noise_sigma))
    # RandomErasing 제거 (약한 증강 정책)

    # Test 변환
    t_test: list = []
    if grayscale:
        t_test.append(transforms.Grayscale(num_output_channels=1))
    if use_clahe:
        t_test.append(CLAHETransform(clip_limit=0.01))
    t_test.extend([transforms.Resize((img_size, img_size)), transforms.ToTensor()])

    return transforms.Compose(t_train), transforms.Compose(t_test)


def get_dataloaders(data_root: str, img_size: int, batch_size: int, num_workers: int = 4,
                    augment: bool = False, use_clahe: bool = False, noise_sigma: float = 0.0):
    """데이터 로더 생성
    Args:
        data_root: 데이터 루트 디렉토리
        img_size: 이미지 크기
        batch_size: 배치 크기
        num_workers: 워커 수
        augment: 증강 사용 여부
        use_clahe: CLAHE 사용 여부
        noise_sigma: 노이즈 표준편차
    Returns:
        (train_loader, test_loader) 튜플
    """
    # GPU가 있을 때만 pin_memory 사용 (경고 방지)
    pin_memory = torch.cuda.is_available()
    
    train_tf, test_tf = build_transforms(img_size, grayscale=True, augment=augment,
                                         use_clahe=use_clahe, noise_sigma=noise_sigma)
    train_dir = os.path.join(data_root, 'train')
    test_dir = os.path.join(data_root, 'test')
    train_ds = datasets.ImageFolder(train_dir, transform=train_tf)  # train/good 만 존재 가정
    test_ds = datasets.ImageFolder(test_dir, transform=test_tf)   # test/good + test/<defect>
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, pin_memory=pin_memory)
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False,
                             num_workers=num_workers, pin_memory=pin_memory)
    return train_loader, test_loader


def get_balanced_train_loader(data_root: str, img_size: int, batch_size: int, num_workers: int = 4,
                              augment: bool = False, use_clahe: bool = False, noise_sigma: float = 0.0,
                              max_samples_per_class: int = None):
    """균형잡힌 학습 데이터 로더 생성
    Args:
        data_root: 데이터 루트 디렉토리
        img_size: 이미지 크기
        batch_size: 배치 크기
        num_workers: 워커 수
        augment: 증강 사용 여부
        use_clahe: CLAHE 사용 여부
        noise_sigma: 노이즈 표준편차
        max_samples_per_class: 클래스별 최대 샘플 수 (None이면 정상 데이터 수에 맞춤)
    Returns:
        train_loader
    """
    from torch.utils.data import ConcatDataset, Subset
    import random
    
    pin_memory = torch.cuda.is_available()
    train_tf, _ = build_transforms(img_size, grayscale=True, augment=augment,
                                   use_clahe=use_clahe, noise_sigma=noise_sigma)
    
    # 정상 데이터 (train/good)
    train_dir = os.path.join(data_root, 'train')
    train_ds = datasets.ImageFolder(train_dir, transform=train_tf)
    normal_indices = list(range(len(train_ds)))
    normal_count = len(normal_indices)
    
    # 이상 데이터 (test에서 가져옴)
    test_dir = os.path.join(data_root, 'test')
    test_ds = datasets.ImageFolder(test_dir, transform=train_tf)
    
    # 클래스별 인덱스 수집 (label 0 = good 제외)
    abnormal_indices_by_class = {}
    for idx, (path, label) in enumerate(test_ds.samples):
        if label != 0:  # good 제외
            if label not in abnormal_indices_by_class:
                abnormal_indices_by_class[label] = []
            abnormal_indices_by_class[label].append(idx)
    
    # 각 이상 클래스에서 균형있게 샘플링
    max_samples = max_samples_per_class if max_samples_per_class else normal_count
    random.seed(42)
    selected_abnormal_indices = []
    for label, indices in abnormal_indices_by_class.items():
        if len(indices) > max_samples:
            selected = random.sample(indices, max_samples)
        else:
            selected = indices
        selected_abnormal_indices.extend(selected)
    
    # 정상과 이상 합치기
    normal_subset = Subset(train_ds, normal_indices)
    abnormal_subset = Subset(test_ds, selected_abnormal_indices)
    balanced_ds = ConcatDataset([normal_subset, abnormal_subset])
    
    train_loader = DataLoader(balanced_ds, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, pin_memory=pin_memory)
    
    print(f"[Balanced Train Loader] 정상: {normal_count}개, 이상: {len(selected_abnormal_indices)}개")
    print(f"  총 {len(balanced_ds)}개 샘플 사용")
    
    return train_loader


def get_balanced_test_loader(data_root: str, img_size: int, num_workers: int = 4,
                             use_clahe: bool = False, max_samples_per_class: int = None,
                             match_abnormal_to_normal: bool = True):
    """균형잡힌 평가 데이터 로더 생성
    Args:
        data_root: 데이터 루트 디렉토리
        img_size: 이미지 크기
        num_workers: 워커 수
        use_clahe: CLAHE 사용 여부
        max_samples_per_class: 클래스별 최대 샘플 수 (None이면 정상 데이터 수에 맞춤)
        match_abnormal_to_normal: 이상 데이터 총합을 정상 수와 동일하게 맞출지 여부
    Returns:
        test_loader
    """
    from torch.utils.data import Subset
    import random
    
    pin_memory = torch.cuda.is_available()
    _, test_tf = build_transforms(img_size, grayscale=True, augment=False,
                                  use_clahe=use_clahe, noise_sigma=0.0)
    test_dir = os.path.join(data_root, 'test')
    test_ds = datasets.ImageFolder(test_dir, transform=test_tf)
    
    # 클래스별 인덱스 수집
    class_indices = {}
    for idx, (path, label) in enumerate(test_ds.samples):
        if label not in class_indices:
            class_indices[label] = []
        class_indices[label].append(idx)
    
    # 정상/이상 통계
    normal_indices = class_indices.get(0, [])
    normal_count = len(normal_indices)
    abnormal_labels = [label for label in class_indices if label != 0]
    total_abnormal = sum(len(class_indices[label]) for label in abnormal_labels)
    
    random.seed(42)
    selected_indices = []
    
    if match_abnormal_to_normal and normal_count > 0 and total_abnormal > 0:
        # 정상 수와 동일하도록 이상 클래스 총합을 조정 (양측 모두 target_total 사용)
        target_total = min(normal_count, total_abnormal)
        
        # 정상 샘플 선택 (필요 시 다운샘플링)
        if len(normal_indices) > target_total:
            normal_selected = sorted(random.sample(normal_indices, target_total))
        else:
            normal_selected = sorted(normal_indices)
        
        # 이상 샘플 비율 할당 (클래스 크기 비율 기반)
        quotas = {}
        raw_allocs = {}
        for label in abnormal_labels:
            class_size = len(class_indices[label])
            proportion = class_size / total_abnormal
            raw_target = proportion * target_total
            alloc = min(class_size, int(raw_target))
            quotas[label] = alloc
            raw_allocs[label] = raw_target
        
        allocated = sum(quotas.values())
        remainder = max(0, target_total - allocated)
        if remainder > 0:
            # 소수점 잔여치가 큰 클래스부터 하나씩 추가
            frac_ranking = sorted(
                abnormal_labels,
                key=lambda lbl: (raw_allocs[lbl] - int(raw_allocs[lbl]), len(class_indices[lbl])),
                reverse=True
            )
            for label in frac_ranking:
                if remainder == 0:
                    break
                if quotas[label] < len(class_indices[label]):
                    quotas[label] += 1
                    remainder -= 1
        
        # 이상 샘플 선택
        for label in abnormal_labels:
            count = quotas[label]
            if count == 0:
                continue
            indices = class_indices[label]
            if len(indices) > count:
                selected = random.sample(indices, count)
            else:
                selected = indices
            selected_indices.extend(selected)
        
        selected_indices.extend(normal_selected)
        selected_indices.sort()
        
        balanced_ds = Subset(test_ds, selected_indices)
        test_loader = DataLoader(balanced_ds, batch_size=1, shuffle=False,
                                 num_workers=num_workers, pin_memory=pin_memory)
        
        print("[Balanced Test Loader] match_abnormal_to_normal 활성화")
        print(f"  정상 {len(normal_selected)}개 vs 이상 {len(selected_indices) - len(normal_selected)}개 (총 {len(selected_indices)}개)")
        for label in sorted(class_indices.keys()):
            class_name = test_ds.classes[label]
            if label == 0:
                actual = len(normal_selected)
            else:
                actual = quotas.get(label, 0)
            print(f"    {class_name}: {actual}개")
        
        return test_loader
    
    # match 옵션이 아니거나 적용 불가 시: 기존 per-class 제한 방식
    max_samples = max_samples_per_class if max_samples_per_class else normal_count
    selected_indices = []
    random.seed(42)
    for label, indices in class_indices.items():
        if len(indices) > max_samples:
            selected = random.sample(indices, max_samples)
        else:
            selected = indices
        selected_indices.extend(selected)
    
    selected_indices.sort()
    balanced_ds = Subset(test_ds, selected_indices)
    
    test_loader = DataLoader(balanced_ds, batch_size=1, shuffle=False,
                             num_workers=num_workers, pin_memory=pin_memory)
    
    print(f"[Balanced Test Loader] 각 클래스별 최대 {max_samples}개로 제한")
    print(f"  총 {len(selected_indices)}개 샘플 사용")
    for label in sorted(class_indices.keys()):
        class_name = test_ds.classes[label]
        actual_count = min(len(class_indices[label]), max_samples)
        print(f"    {class_name}: {actual_count}개")
    
    return test_loader


def get_limited_test_loader(data_root: str, img_size: int, num_workers: int = 4,
                            use_clahe: bool = False, limit_per_class: int = 100):
    """테스트 데이터 로더 생성 (각 클래스별로 제한된 수만 사용)
    Args:
        data_root: 데이터 루트 디렉토리
        img_size: 이미지 크기
        num_workers: 워커 수
        use_clahe: CLAHE 사용 여부
        limit_per_class: 각 클래스별 최대 샘플 수
    Returns:
        test_loader
    """
    from torch.utils.data import Subset
    import random
    
    pin_memory = torch.cuda.is_available()
    _, test_tf = build_transforms(img_size, grayscale=True, augment=False,
                                  use_clahe=use_clahe, noise_sigma=0.0)
    test_dir = os.path.join(data_root, 'test')
    test_ds = datasets.ImageFolder(test_dir, transform=test_tf)
    
    # 각 클래스별로 샘플 제한
    class_indices = {}
    for idx, (path, label) in enumerate(test_ds.samples):
        if label not in class_indices:
            class_indices[label] = []
        class_indices[label].append(idx)
    
    # 각 클래스에서 limit_per_class개만 랜덤 선택
    selected_indices = []
    random.seed(42)  # 재현성을 위한 시드
    for label, indices in class_indices.items():
        if len(indices) > limit_per_class:
            selected = random.sample(indices, limit_per_class)
        else:
            selected = indices
        selected_indices.extend(selected)
    
    # 인덱스 정렬 (원래 순서 유지)
    selected_indices.sort()
    limited_ds = Subset(test_ds, selected_indices)
    
    test_loader = DataLoader(limited_ds, batch_size=1, shuffle=False,
                             num_workers=num_workers, pin_memory=pin_memory)
    
    print(f"[Limited Test Loader] 각 클래스별 {limit_per_class}개로 제한")
    print(f"  총 {len(selected_indices)}개 샘플 사용")
    for label, count in sorted(class_indices.items()):
        class_name = test_ds.classes[label]
        actual_count = min(len(class_indices[label]), limit_per_class)
        print(f"    {class_name}: {actual_count}개")
    
    return test_loader


def convert_to_mvtec(src_root: str, dst_root: str, category: str):
    """임의의 폴더 구조를 MVTec 형식으로 변환
    Args:
        src_root: 소스 루트 디렉토리
        dst_root: 대상 루트 디렉토리
        category: 카테고리명
    """
    src = Path(src_root)
    cat = Path(dst_root) / category
    tr_good = cat / 'train' / 'good'
    te_good = cat / 'test' / 'good'
    gt_dir = cat / 'ground_truth'
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
    copy_all(src / 'test' / 'normal', te_good)

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
        dst_gt = cat / 'ground_truth' / defect
        copy_all(img_dir, dst_img)
        if mask_dir.exists():
            copy_all(mask_dir, dst_gt)
        elif alt_mask_dir.exists():
            copy_all(alt_mask_dir, dst_gt)

    print(f'[convert_to_mvtec] Converted to {cat}')

