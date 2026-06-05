#!/usr/bin/env python3
"""
SimSID inference evaluation script.

Reads `outs_simsid/scores_test.json`, computes metrics/plots,
and saves them under `eval_simsid/<timestamp>/`.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (10, 8)
plt.rcParams["font.size"] = 10


@dataclass
class Metrics:
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    tn: int
    fn: int
    threshold: float


def compute_fpr(metrics: Metrics) -> float:
    denom = metrics.fp + metrics.tn
    return metrics.fp / denom if denom else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SimSID scores.")
    parser.add_argument(
        "--scores_path",
        type=Path,
        default=Path("outs_simsid/scores_test.json"),
        help="Path to SimSID scores JSON.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("eval_simsid"),
        help="Base directory for evaluation outputs.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=20,
        help="Histogram bins for score distribution.",
    )
    parser.add_argument(
        "--target_fpr",
        type=float,
        default=0.05,
        help="Target false positive rate for threshold selection.",
    )
    return parser.parse_args()


def load_scores(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"Score file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    y_true = np.array([0 if item["label"] == 0 else 1 for item in data], dtype=int)
    scores = np.array([float(item["score"]) for item in data], dtype=float)
    return y_true, scores


def confusion_at_threshold(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> Metrics:
    y_pred = (scores >= threshold).astype(int)
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0

    return Metrics(precision, recall, f1, accuracy, tp, fp, tn, fn, threshold)


def find_best_threshold(y_true: np.ndarray, scores: np.ndarray) -> Metrics:
    thresholds = np.linspace(scores.min(), scores.max(), num=200)
    best = None
    for thresh in thresholds:
        metrics = confusion_at_threshold(y_true, scores, thresh)
        if best is None or metrics.f1 > best.f1:
            best = metrics
    return best


def threshold_at_fpr(y_true: np.ndarray, scores: np.ndarray, target_fpr: float) -> Metrics:
    thresholds = np.linspace(scores.max(), scores.min(), num=500)
    fallback = None
    for thresh in thresholds:
        metrics = confusion_at_threshold(y_true, scores, thresh)
        fpr = compute_fpr(metrics)
        if fallback is None:
            fallback = metrics
        if fpr <= target_fpr:
            return metrics
    return fallback if fallback else confusion_at_threshold(y_true, scores, thresholds[-1])


def precision_recall_curve(y_true: np.ndarray, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(scores)[::-1]
    y_true_sorted = y_true[order]
    scores_sorted = scores[order]

    tp = 0
    fp = 0
    precisions = []
    recalls = []
    thresholds = []
    positives = y_true.sum()
    positives = positives if positives > 0 else 1

    for i, label in enumerate(y_true_sorted):
        if label == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp)
        recall = tp / positives
        precisions.append(precision)
        recalls.append(recall)
        thresholds.append(scores_sorted[i])

    return np.array(recalls), np.array(precisions), np.array(thresholds)


def roc_curve(y_true: np.ndarray, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(scores)[::-1]
    y_true_sorted = y_true[order]
    scores_sorted = scores[order]

    tp = 0
    fp = 0
    tpr = []
    fpr = []
    thresholds = []
    positives = y_true.sum()
    negatives = len(y_true) - positives
    positives = positives if positives > 0 else 1
    negatives = negatives if negatives > 0 else 1

    for i, label in enumerate(y_true_sorted):
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr.append(tp / positives)
        fpr.append(fp / negatives)
        thresholds.append(scores_sorted[i])

    return np.array(fpr), np.array(tpr), np.array(thresholds)


def trapezoidal_auc(x: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    return float(np.trapezoid(y, x))


def plot_confusion_matrix(metrics: Metrics, output_path: Path) -> None:
    cm = np.array([[metrics.tn, metrics.fp], [metrics.fn, metrics.tp]])
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        ax=ax,
        xticklabels=["Normal", "Abnormal"],
        yticklabels=["Normal", "Abnormal"],
        cbar_kws={"label": "Count"},
    )
    ax.set_xlabel("Predicted", fontsize=12, fontweight="bold")
    ax.set_ylabel("Actual", fontsize=12, fontweight="bold")
    ax.set_title(f"Confusion Matrix (Threshold={metrics.threshold:.4f})", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_pr_curve(recall: np.ndarray, precision: np.ndarray, auc: float, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(recall, precision, linewidth=2, label=f"PR Curve (AUC={auc:.4f})")
    ax.axhline(y=0.5, color="r", linestyle="--", alpha=0.5, label="Baseline (0.5)")
    ax.set_xlabel("Recall", fontsize=12, fontweight="bold")
    ax.set_ylabel("Precision", fontsize=12, fontweight="bold")
    ax.set_title("Precision-Recall Curve", fontsize=14, fontweight="bold")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_roc_curve(fpr: np.ndarray, tpr: np.ndarray, auc: float, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(fpr, tpr, linewidth=2, label=f"ROC Curve (AUC={auc:.4f})")
    ax.plot([0, 1], [0, 1], "r--", alpha=0.5, label="Random (AUC=0.5)")
    ax.set_xlabel("False Positive Rate", fontsize=12, fontweight="bold")
    ax.set_ylabel("True Positive Rate", fontsize=12, fontweight="bold")
    ax.set_title("ROC Curve", fontsize=14, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_score_distribution(y_true: np.ndarray, scores: np.ndarray, best_threshold: float, output_path: Path, bins: int) -> None:
    normal_scores = scores[y_true == 0]
    abnormal_scores = scores[y_true == 1]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(normal_scores, bins=bins, alpha=0.6, label="Normal", color="blue", edgecolor="black")
    ax.hist(abnormal_scores, bins=bins, alpha=0.6, label="Abnormal", color="red", edgecolor="black")
    ax.axvline(x=best_threshold, color="green", linestyle="--", linewidth=2, label=f"Best Threshold ({best_threshold:.4f})")
    ax.set_xlabel("Anomaly Score", fontsize=12, fontweight="bold")
    ax.set_ylabel("Frequency", fontsize=12, fontweight="bold")
    ax.set_title("Score Distribution", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_args()
    y_true, scores = load_scores(args.scores_path)

    best_metrics = find_best_threshold(y_true, scores)
    fpr_metrics = threshold_at_fpr(y_true, scores, args.target_fpr)
    pr_recall, pr_precision, _ = precision_recall_curve(y_true, scores)
    roc_fpr, roc_tpr, _ = roc_curve(y_true, scores)
    pr_auc = trapezoidal_auc(pr_recall, pr_precision)
    roc_auc = trapezoidal_auc(roc_fpr, roc_tpr)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = args.output_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / f"eval_{timestamp}.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"SimSID Evaluation Report - {timestamp}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Samples: total={len(scores)}, normal={(y_true == 0).sum()}, abnormal={(y_true == 1).sum()}\n\n")
        f.write(f"Threshold (Target FPR={args.target_fpr:.2%}):\n")
        f.write(f"  threshold      : {fpr_metrics.threshold:.6f}\n")
        f.write(f"  precision      : {fpr_metrics.precision:.4f}\n")
        f.write(f"  recall         : {fpr_metrics.recall:.4f}\n")
        f.write(f"  F1             : {fpr_metrics.f1:.4f}\n")
        f.write(f"  accuracy       : {fpr_metrics.accuracy:.4f}\n")
        f.write(f"  FPR            : {compute_fpr(fpr_metrics):.4f}\n")
        f.write(f"  confusion      : TP={fpr_metrics.tp}, FP={fpr_metrics.fp}, TN={fpr_metrics.tn}, FN={fpr_metrics.fn}\n\n")

        f.write("Best Threshold (max F1):\n")
        f.write(f"  threshold      : {best_metrics.threshold:.6f}\n")
        f.write(f"  precision      : {best_metrics.precision:.4f}\n")
        f.write(f"  recall         : {best_metrics.recall:.4f}\n")
        f.write(f"  F1             : {best_metrics.f1:.4f}\n")
        f.write(f"  accuracy       : {best_metrics.accuracy:.4f}\n")
        f.write(f"  confusion      : TP={best_metrics.tp}, FP={best_metrics.fp}, TN={best_metrics.tn}, FN={best_metrics.fn}\n\n")

        f.write("Precision-Recall Curve Summary:\n")
        f.write(f"  PR AUC         : {pr_auc:.4f}\n\n")

        f.write("ROC Curve Summary:\n")
        f.write(f"  ROC AUC        : {roc_auc:.4f}\n\n")

    plot_confusion_matrix(fpr_metrics, output_dir / f"confusion_matrix_{timestamp}.png")
    plot_pr_curve(pr_recall, pr_precision, pr_auc, output_dir / f"pr_curve_{timestamp}.png")
    plot_roc_curve(roc_fpr, roc_tpr, roc_auc, output_dir / f"roc_curve_{timestamp}.png")
    plot_score_distribution(y_true, scores, fpr_metrics.threshold, output_dir / f"score_distribution_{timestamp}.png", bins=args.bins)

    print(f"[INFO] Evaluation report saved to {report_path}")
    print(f"[INFO] All visualizations saved under {output_dir}")


if __name__ == "__main__":
    main()

