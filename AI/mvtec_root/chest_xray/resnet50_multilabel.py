#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ResNet101 기반 멀티레이블 흉부 X-ray 분류 스크립트 (개선 버전).

주요 개선 사항:
- ResNet101 사용
- Attention mechanism (CBAM)
- 클래스 불균형 처리 (Undersampling)
- Early stopping
- 클래스별 최적 임계값 탐색
- 의료 영상 사전학습 모델 옵션

CheXpert 형식의 CSV(archive/train.csv, archive/valid.csv)를 사용해
각 이미지의 Path와 질병 라벨을 불러와 학습/평가합니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from torchvision.models import ResNet101_Weights, resnet101
from tqdm import tqdm
from PIL import Image


CHEXPERT_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Enlarged Cardiomediastinum",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "No Finding",
    "Pleural Effusion",
    "Pleural Other",
    "Pneumonia",
    "Pneumothorax",
    "Support Devices",
]


class CBAM(nn.Module):
    """Convolutional Block Attention Module"""
    def __init__(self, channels, reduction=16):
        super(CBAM, self).__init__()
        self.channel_attention = ChannelAttention(channels, reduction)
        self.spatial_attention = SpatialAttention()
    
    def forward(self, x):
        x = self.channel_attention(x) * x
        x = self.spatial_attention(x) * x
        return x


class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False)
        )
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        b, c, _, _ = x.size()
        avg_out = self.fc(self.avg_pool(x).view(b, c))
        max_out = self.fc(self.max_pool(x).view(b, c))
        out = self.sigmoid(avg_out + max_out).view(b, c, 1, 1)
        return out


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super(SpatialAttention, self).__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size//2, bias=False)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        out = torch.cat([avg_out, max_out], dim=1)
        out = self.conv(out)
        return self.sigmoid(out)


class ResNet101WithAttention(nn.Module):
    """ResNet101 with CBAM Attention"""
    def __init__(self, num_classes: int, freeze_backbone: bool = False, use_attention: bool = True):
        super(ResNet101WithAttention, self).__init__()
        weights = ResNet101_Weights.IMAGENET1K_V2
        self.backbone = resnet101(weights=weights)
        
        # Remove the original fc layer
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()
        
        # Add attention before global pooling
        self.use_attention = use_attention
        if use_attention:
            self.attention = CBAM(2048, reduction=16)
        
        # Classification head
        self.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(in_features, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(512, num_classes),
        )
        
        if freeze_backbone:
            for name, param in self.backbone.named_parameters():
                if "fc" not in name:
                    param.requires_grad = False
    
    def forward(self, x):
        x = self.backbone.conv1(x)
        x = self.backbone.bn1(x)
        x = self.backbone.relu(x)
        x = self.backbone.maxpool(x)
        
        x = self.backbone.layer1(x)
        x = self.backbone.layer2(x)
        x = self.backbone.layer3(x)
        x = self.backbone.layer4(x)
        
        # Apply attention
        if self.use_attention:
            x = self.attention(x)
        
        x = self.backbone.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ResNet101 Multi-Label Classification with Attention")
    parser.add_argument("--image_root", type=str, default="./archive_pa", help="PA 전용 ROI 마스킹 이미지 경로")
    parser.add_argument("--train_csv", type=str, default="./archive_pa/train.csv")
    parser.add_argument("--valid_csv", type=str, default="./archive_pa/valid.csv")
    parser.add_argument("--labels", type=str, nargs="+", default=CHEXPERT_LABELS, help="사용할 라벨 목록")
    parser.add_argument("--img_size", type=int, default=320)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=50, help="최대 에폭 수 (Early stopping 적용)")
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--weight_decay", type=float, default=1e-5)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=None, help="고정 임계값 (None이면 클래스별 최적화)")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--use_amp", action="store_true", help="Mixed Precision(AMP) 사용")
    parser.add_argument("--freeze_backbone", action="store_true", help="ResNet 백본 고정 여부")
    parser.add_argument("--use_attention", action="store_true", default=True, help="CBAM Attention 사용")
    parser.add_argument("--no_attention", dest="use_attention", action="store_false", help="Attention 비활성화")
    
    # Undersampling 옵션
    parser.add_argument("--use_undersampling", action="store_true", help="클래스 불균형 해소를 위한 Undersampling 사용")
    parser.add_argument("--max_samples_per_class", type=int, default=None, help="클래스당 최대 샘플 수 (None이면 자동 계산)")
    
    # Early stopping 옵션
    parser.add_argument("--early_stopping_patience", type=int, default=10, help="Early stopping patience")
    parser.add_argument("--early_stopping_min_delta", type=float, default=1e-4, help="Early stopping 최소 개선량")
    
    # 프로젝트 루트 기준으로 절대 경로 계산
    script_dir = Path(__file__).parent  # mvtec_root/chest_xray/
    project_root = script_dir.parent.parent  # 프로젝트 루트
    parser.add_argument("--checkpoint_path", type=str, default=str(project_root / "checkpoints" / "resnet101_multilabel_best.pt"))
    parser.add_argument("--history_path", type=str, default=str(project_root / "classification_results" / "resnet101_multilabel" / "history.json"))
    parser.add_argument("--thresholds_path", type=str, default=str(project_root / "classification_results" / "resnet101_multilabel" / "optimal_thresholds.json"))
    
    parser.add_argument("--uncertain_policy", choices=["zeros", "ones"], default="zeros",
                        help="-1(uncertain)을 0으로 볼지(zeros) 1로 볼지(ones) 설정")
    parser.add_argument("--pos_weight_clip", type=float, default=10.0, help="pos_weight 상한")
    return parser.parse_args()


class CheXpertMultiLabelDataset(Dataset):
    """CheXpert CSV를 읽어 이미지와 multi-hot 라벨을 반환."""

    def __init__(
        self,
        csv_path: Path,
        image_root: Path,
        label_names: Sequence[str],
        transform=None,
        uncertain_policy: str = "zeros",
    ):
        self.csv_path = csv_path
        self.image_root = image_root
        self.label_names = list(label_names)
        self.transform = transform
        self.uncertain_policy = uncertain_policy

        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV 경로를 찾을 수 없습니다: {self.csv_path}")
        if not self.image_root.exists():
            raise FileNotFoundError(f"이미지 루트 경로를 찾을 수 없습니다: {self.image_root}")

        self.samples: List[Path] = []
        self.targets: List[List[float]] = []

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing_cols = [c for c in ["Path", *self.label_names] if c not in reader.fieldnames]
            if missing_cols:
                raise ValueError(f"CSV에 필요한 열이 없습니다: {missing_cols}")

            skipped = 0
            for row in reader:
                rel_path = row["Path"].strip()
                # CheXpert-v1.0-small/train/... 또는 CheXpert-v1.0-small/valid/... 형식 처리
                if "CheXpert-v1.0-small/" in rel_path:
                    rel_path = rel_path.replace("CheXpert-v1.0-small/", "")
                elif rel_path.startswith("train/") or rel_path.startswith("valid/"):
                    pass  # 이미 올바른 형식
                else:
                    # 다른 prefix가 있을 수 있으므로 마지막 train/ 또는 valid/ 이후 부분만 사용
                    parts = Path(rel_path).parts
                    if "train" in parts:
                        idx = parts.index("train")
                        rel_path = str(Path(*parts[idx:]))
                    elif "valid" in parts:
                        idx = parts.index("valid")
                        rel_path = str(Path(*parts[idx:]))
                
                img_path = Path(rel_path)
                if not img_path.is_absolute():
                    img_path = (self.image_root / rel_path).resolve()
                if not img_path.exists():
                    skipped += 1
                    continue

                labels = []
                for name in self.label_names:
                    raw = row.get(name, "")
                    if raw == "" or raw is None:
                        value = 0.0
                    else:
                        value = float(raw)
                        if value < 0:
                            value = 1.0 if self.uncertain_policy == "ones" else 0.0
                        else:
                            value = 1.0 if value > 0 else 0.0
                    labels.append(value)

                self.samples.append(img_path)
                self.targets.append(labels)

        if not self.samples:
            raise RuntimeError(f"CSV에서 유효한 샘플을 찾지 못했습니다: {self.csv_path}")

        print(f"[DATA] {self.csv_path.name}: {len(self.samples):,}개 로드 (누락 {skipped}개)")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        img_path = self.samples[idx]
        labels = torch.tensor(self.targets[idx], dtype=torch.float32)
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            if self.transform:
                img = self.transform(img)
        return img, labels


def apply_undersampling(dataset: CheXpertMultiLabelDataset, max_samples: Optional[int] = None) -> Subset:
    """클래스 불균형 해소를 위한 Undersampling"""
    print("[UNDERSAMPLING] 시작...")
    
    # 먼저 전체 클래스 카운트를 한 번만 계산 (성능 최적화)
    print("[UNDERSAMPLING] 클래스 분포 계산 중...")
    all_positive_classes = []
    for target in dataset.targets:
        positive_indices = [i for i, v in enumerate(target) if v > 0.5]
        all_positive_classes.extend(positive_indices)
    
    class_counts = Counter(all_positive_classes)
    print(f"[UNDERSAMPLING] 클래스별 양성 샘플 수: {dict(class_counts)}")
    
    # 각 샘플의 주요 클래스 인덱스 계산
    print("[UNDERSAMPLING] 각 샘플의 주요 클래스 식별 중...")
    sample_classes = []
    total = len(dataset.targets)
    for idx, target in enumerate(dataset.targets):
        if (idx + 1) % 10000 == 0:
            print(f"[UNDERSAMPLING] 진행 중: {idx + 1:,}/{total:,} ({100*(idx+1)/total:.1f}%)")
        
        positive_indices = [i for i, v in enumerate(target) if v > 0.5]
        if positive_indices:
            # 여러 클래스가 있으면 가장 희귀한 클래스를 선택
            primary_class = min(positive_indices, key=lambda x: class_counts.get(x, float('inf')))
        else:
            primary_class = -1  # No Finding
        sample_classes.append(primary_class)
    
    # 클래스별 샘플 인덱스 그룹화
    print("[UNDERSAMPLING] 클래스별 샘플 그룹화 중...")
    class_indices = defaultdict(list)
    for idx, cls in enumerate(sample_classes):
        class_indices[cls].append(idx)
    
    # 클래스별 샘플 수 출력
    print(f"[UNDERSAMPLING] 클래스별 샘플 수:")
    for cls, indices in sorted(class_indices.items()):
        print(f"  클래스 {cls}: {len(indices):,}개")
    
    # 클래스별 샘플 수 계산
    if max_samples is None:
        # 가장 적은 클래스의 샘플 수를 기준으로 설정 (단, 너무 작으면 중간값 사용)
        class_sizes = [len(indices) for indices in class_indices.values() if len(indices) > 0]
        if class_sizes:
            median_size = int(np.median(class_sizes))
            max_samples = min(median_size * 2, max(class_sizes))  # 중간값의 2배, 또는 최대값 중 작은 값
    
    # 각 클래스에서 샘플링
    print(f"[UNDERSAMPLING] 클래스당 최대 {max_samples:,}개로 샘플링 중...")
    selected_indices = []
    for cls, indices in class_indices.items():
        if len(indices) > max_samples:
            selected = random.sample(indices, max_samples)
        else:
            selected = indices
        selected_indices.extend(selected)
    
    print(f"[UNDERSAMPLING] 완료! 원본: {len(dataset):,}개 → 샘플링 후: {len(selected_indices):,}개")
    print(f"[UNDERSAMPLING] 클래스당 최대 샘플 수: {max_samples:,}")
    
    return Subset(dataset, selected_indices)


def build_transforms(img_size: int = 320):
    weights = ResNet101_Weights.IMAGENET1K_V2
    mean = weights.meta.get("mean", [0.485, 0.456, 0.406])
    std = weights.meta.get("std", [0.229, 0.224, 0.225])

    train_tf = transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(degrees=7),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    eval_tf = transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    return train_tf, eval_tf, weights


def compute_pos_weight(targets: List[List[float]], max_value: float = 10.0) -> torch.Tensor:
    arr = torch.tensor(targets)
    pos_counts = arr.sum(dim=0)
    neg_counts = arr.shape[0] - pos_counts
    pos_weight = neg_counts / (pos_counts + 1e-6)
    pos_weight = pos_weight.clamp(max=max_value)
    return pos_weight


def find_optimal_thresholds(probs: np.ndarray, labels: np.ndarray, num_classes: int) -> np.ndarray:
    """클래스별 최적 임계값 찾기 (F1-score 최대화)"""
    thresholds = np.zeros(num_classes)
    
    print("[THRESHOLD OPTIMIZATION] 클래스별 최적 임계값 탐색 중...")
    for i in range(num_classes):
        best_f1 = 0.0
        best_thresh = 0.5
        
        # 양성 샘플이 없는 경우
        if labels[:, i].sum() == 0:
            thresholds[i] = 0.5
            continue
        
        # 0.01 단위로 임계값 탐색
        for thresh in np.arange(0.1, 0.9, 0.01):
            preds = (probs[:, i] >= thresh).astype(np.float32)
            try:
                f1 = f1_score(labels[:, i], preds, zero_division=0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_thresh = thresh
            except:
                pass
        
        thresholds[i] = best_thresh
        print(f"  클래스 {i}: 최적 임계값 = {best_thresh:.3f}, F1 = {best_f1:.3f}")
    
    return thresholds


def prepare_dataloaders(args: argparse.Namespace):
    train_tf, eval_tf, _ = build_transforms(args.img_size)
    image_root = Path(args.image_root).resolve()
    train_csv = Path(args.train_csv).resolve()
    valid_csv = Path(args.valid_csv).resolve()

    train_dataset = CheXpertMultiLabelDataset(
        train_csv,
        image_root,
        args.labels,
        transform=train_tf,
        uncertain_policy=args.uncertain_policy,
    )
    valid_dataset = CheXpertMultiLabelDataset(
        valid_csv,
        image_root,
        args.labels,
        transform=eval_tf,
        uncertain_policy=args.uncertain_policy,
    )

    # Undersampling 적용
    if args.use_undersampling:
        print("[PREPARE] Undersampling 적용 중...")
        train_dataset = apply_undersampling(train_dataset, args.max_samples_per_class)
        # Subset에서 targets 접근
        if isinstance(train_dataset, Subset):
            print("[PREPARE] Undersampling된 데이터셋에서 pos_weight 계산 중...")
            # Subset의 원본 데이터셋에서 targets 가져오기
            original_targets = train_dataset.dataset.targets
            sampled_targets = [original_targets[i] for i in train_dataset.indices]
            pos_weight = compute_pos_weight(sampled_targets, max_value=args.pos_weight_clip)
        else:
            pos_weight = compute_pos_weight(train_dataset.targets, max_value=args.pos_weight_clip)
    else:
        print("[PREPARE] pos_weight 계산 중...")
        pos_weight = compute_pos_weight(train_dataset.targets, max_value=args.pos_weight_clip)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=max(args.num_workers, 0),
        pin_memory=True,
    )
    valid_loader = DataLoader(
        valid_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=max(args.num_workers, 0),
        pin_memory=True,
    )

    print(f"[INFO] pos_weight: {pos_weight.tolist()}")

    return {
        "train_loader": train_loader,
        "valid_loader": valid_loader,
        "train_dataset": train_dataset,
        "valid_dataset": valid_dataset,
        "pos_weight": pos_weight,
    }


def train_one_epoch(model, loader, criterion, optimizer, device, scaler=None):
    model.train()
    running_loss = 0.0
    running_acc = 0.0
    total = 0

    pbar = tqdm(loader, desc="Train", leave=False)
    for images, labels in pbar:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        if scaler:
            with torch.cuda.amp.autocast():
                outputs = model(images)
                loss = criterion(outputs, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

        running_loss += loss.item() * images.size(0)
        preds = torch.sigmoid(outputs) >= 0.5
        batch_acc = (preds == labels.bool()).float().mean(dim=1).mean()
        running_acc += batch_acc.item() * images.size(0)
        total += images.size(0)

        pbar.set_postfix(loss=f"{loss.item():4f}", acc=f"{batch_acc.item():.3f}")

    return running_loss / total, running_acc / total


def evaluate(
    model, 
    loader, 
    criterion, 
    device, 
    threshold: Optional[float] = None,
    optimal_thresholds: Optional[np.ndarray] = None,
    return_probs_labels: bool = False
):
    model.eval()
    running_loss = 0.0
    total = 0
    all_probs: List[np.ndarray] = []
    all_labels: List[np.ndarray] = []

    with torch.no_grad():
        for images, labels in tqdm(loader, desc="Valid", leave=False):
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            outputs = model(images)
            loss = criterion(outputs, labels)

            probs = torch.sigmoid(outputs)
            running_loss += loss.item() * images.size(0)
            total += images.size(0)

            all_probs.append(probs.detach().cpu().numpy())
            all_labels.append(labels.cpu().numpy())

    probs_np = np.concatenate(all_probs, axis=0)
    labels_np = np.concatenate(all_labels, axis=0)

    # 임계값 적용
    if optimal_thresholds is not None:
        # 클래스별 최적 임계값 사용
        preds_np = (probs_np >= optimal_thresholds).astype(np.float32)
    elif threshold is not None:
        preds_np = (probs_np >= threshold).astype(np.float32)
    else:
        preds_np = (probs_np >= 0.5).astype(np.float32)

    sample_acc = (preds_np == labels_np).mean(axis=1).mean()

    micro_f1 = f1_score(labels_np, preds_np, average="micro", zero_division=0)
    macro_f1 = f1_score(labels_np, preds_np, average="macro", zero_division=0)

    try:
        macro_auc = roc_auc_score(labels_np, probs_np, average="macro")
    except ValueError:
        macro_auc = float("nan")

    try:
        macro_ap = average_precision_score(labels_np, probs_np, average="macro")
    except ValueError:
        macro_ap = float("nan")

    metrics = {
        "val_loss": running_loss / total,
        "sample_acc": sample_acc,
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "macro_auc": macro_auc,
        "macro_ap": macro_ap,
    }
    
    if return_probs_labels:
        return metrics, probs_np, labels_np
    return metrics


def save_checkpoint(model, optimizer, epoch, metrics: Dict[str, float], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "metrics": metrics,
        },
        path,
    )
    print(f"[INFO] 체크포인트 저장: {path}")


def save_history(history: List[Dict[str, float]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"[INFO] 히스토리 저장: {path}")


def save_thresholds(thresholds: np.ndarray, label_names: List[str], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    thresholds_dict = {name: float(thresh) for name, thresh in zip(label_names, thresholds)}
    with path.open("w", encoding="utf-8") as f:
        json.dump(thresholds_dict, f, indent=2, ensure_ascii=False)
    print(f"[INFO] 최적 임계값 저장: {path}")


def main():
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    loaders = prepare_dataloaders(args)

    model = ResNet101WithAttention(
        len(args.labels), 
        freeze_backbone=args.freeze_backbone,
        use_attention=args.use_attention
    ).to(device)

    criterion = nn.BCEWithLogitsLoss(pos_weight=loaders["pos_weight"].to(device))
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=args.learning_rate * 0.1
    )
    scaler = torch.cuda.amp.GradScaler() if (args.use_amp and device.type == "cuda") else None

    checkpoint_path = Path(args.checkpoint_path)
    history_path = Path(args.history_path)
    thresholds_path = Path(args.thresholds_path)

    best_f1 = -float("inf")
    best_epoch = 0
    history: List[Dict[str, float]] = []
    
    # Early stopping
    early_stopping_counter = 0
    early_stopping_patience = args.early_stopping_patience
    early_stopping_min_delta = args.early_stopping_min_delta
    
    # 최적 임계값 (학습 중에는 고정 임계값 사용, 마지막에 최적화)
    optimal_thresholds = None
    if args.threshold is not None:
        optimal_thresholds = np.full(len(args.labels), args.threshold)
    else:
        optimal_thresholds = None  # 학습 중에는 0.5 사용, 마지막에 최적화

    print("=" * 72)
    print("ResNet101 멀티레이블 분류 학습 시작 (개선 버전)")
    print(f"Train CSV : {Path(args.train_csv).resolve()}")
    print(f"Valid CSV : {Path(args.valid_csv).resolve()}")
    print(f"Device    : {device}")
    print(f"Labels    : {len(args.labels)}개")
    print(f"Attention : {'사용' if args.use_attention else '비사용'}")
    print(f"Undersampling : {'사용' if args.use_undersampling else '비사용'}")
    print(f"Early Stopping : Patience={early_stopping_patience}")
    print("=" * 72)

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_one_epoch(
            model,
            loaders["train_loader"],
            criterion,
            optimizer,
            device,
            scaler,
        )
        
        # 평가 (고정 임계값 0.5 사용, 학습 중에는 최적 임계값 미사용)
        eval_threshold = args.threshold if args.threshold is not None else 0.5
        metrics = evaluate(
            model,
            loaders["valid_loader"],
            criterion,
            device,
            threshold=eval_threshold,
        )
        scheduler.step()

        log = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_sample_acc": train_acc,
            **metrics,
            "lr": scheduler.get_last_lr()[0],
        }
        history.append(log)

        is_best = metrics["macro_f1"] > best_f1 + early_stopping_min_delta
        print(
            f"[Epoch {epoch}/{args.epochs}] "
            f"TrainLoss {train_loss:.4f} | TrainAcc {train_acc:.3f} | "
            f"ValLoss {metrics['val_loss']:.4f} | MicroF1 {metrics['micro_f1']:.3f} | MacroF1 {metrics['macro_f1']:.3f}"
        )
        
        if is_best:
            best_f1 = metrics["macro_f1"]
            best_epoch = epoch
            early_stopping_counter = 0
            save_checkpoint(
                model,
                optimizer,
                epoch,
                metrics,
                checkpoint_path,
            )
        else:
            early_stopping_counter += 1
        
        # Early stopping 체크
        if early_stopping_counter >= early_stopping_patience:
            print(f"\n[EARLY STOPPING] {early_stopping_patience} 에폭 동안 개선 없음. 학습 중단.")
            print(f"[EARLY STOPPING] 최고 성능: Epoch {best_epoch}, Macro F1: {best_f1:.4f}")
            break

    # 최종 최적 임계값 찾기
    if args.threshold is None:
        print("\n[THRESHOLD OPTIMIZATION] 최적 임계값 탐색 중...")
        _, probs_np, labels_np = evaluate(
            model,
            loaders["valid_loader"],
            criterion,
            device,
            return_probs_labels=True,
        )
        optimal_thresholds = find_optimal_thresholds(probs_np, labels_np, len(args.labels))
        save_thresholds(optimal_thresholds, args.labels, thresholds_path)
        
        # 최적 임계값으로 재평가
        print("\n[FINAL EVALUATION] 최적 임계값으로 재평가 중...")
        final_metrics = evaluate(
            model,
            loaders["valid_loader"],
            criterion,
            device,
            optimal_thresholds=optimal_thresholds,
        )
        print(f"[FINAL] Macro F1: {final_metrics['macro_f1']:.4f}")
        print(f"[FINAL] Micro F1: {final_metrics['micro_f1']:.4f}")
        print(f"[FINAL] Sample Acc: {final_metrics['sample_acc']:.4f}")

    save_history(history, history_path)
    print("=" * 72)
    print(f"학습 완료! 최고 Macro F1: {best_f1:.4f} (Epoch {best_epoch})")
    print("=" * 72)


if __name__ == "__main__":
    main()
