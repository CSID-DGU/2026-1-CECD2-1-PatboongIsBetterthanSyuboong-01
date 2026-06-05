#!/usr/bin/env python3
"""
Autoencoder evaluation script.

Reads `outs_ae/ae_scores.json` (output of AE inference),
computes confusion matrix, PR/ROC metrics, score distribution,
and writes a timestamped evaluation report.
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

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (10, 8)
plt.rcParams["font.size"] = 10

SCORES_PATH = Path("outs_ae/ae_scores.json")
OUTPUT_DIR = Path("eval_ae")


def parse_eval_args():
    parser = argparse.ArgumentParser(description="Evaluate AE anomaly scores")
    parser.add_argument("--scores_path", type=str, default=str(SCORES_PATH),
                        help="Path to AE score json (default: outs_ae/ae_scores.json)")
    parser.add_argument("--output_dir", type=str, default=str(OUTPUT_DIR),
                        help="Directory to store evaluation outputs (default: eval_ae)")
    parser.add_argument("--target_fpr", type=float, default=0.05,
                        help="Target false positive rate for thresholding (default: 0.05)")
    parser.add_argument("--disable_fpr_threshold", action="store_true",
                        help="Disable FPR-based thresholding and use best F1 instead")
    return parser.parse_args()


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


def load_scores(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Load AE scores JSON."""
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
    """Search threshold (200 steps) maximizing F1 score."""
    thresholds = np.linspace(scores.min(), scores.max(), num=200)
    best = None
    for thresh in thresholds:
        metrics = confusion_at_threshold(y_true, scores, thresh)
        if best is None or metrics.f1 > best.f1:
            best = metrics
    return best


def threshold_for_target_fpr(y_true: np.ndarray, scores: np.ndarray, target_fpr: float) -> Tuple[Metrics | None, float]:
    """Find threshold satisfying target FPR with highest recall."""
    thresholds = np.linspace(scores.min(), scores.max(), num=400)
    best = None
    best_fpr = None
    for thresh in thresholds:
        metrics = confusion_at_threshold(y_true, scores, thresh)
        negatives = metrics.fp + metrics.tn
        current_fpr = (metrics.fp / negatives) if negatives > 0 else 0.0
        if current_fpr <= target_fpr:
            if best is None or metrics.recall > best.recall:
                best = metrics
                best_fpr = current_fpr
    return best, (best_fpr if best_fpr is not None else float("nan"))


def precision_recall_curve(y_true: np.ndarray, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Manual precision-recall curve."""
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
    """Manual ROC curve."""
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
    """Compute AUC via trapezoidal rule."""
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    return float(np.trapezoid(y, x))


def score_distribution(scores: np.ndarray, bins: int = 20) -> Tuple[np.ndarray, np.ndarray]:
    hist, bin_edges = np.histogram(scores, bins=bins)
    return hist, bin_edges


def plot_confusion_matrix(metrics: Metrics, output_path: Path, title_note: str = "") -> None:
    """Plot confusion matrix heatmap."""
    cm = np.array([[metrics.tn, metrics.fp], [metrics.fn, metrics.tp]])
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                xticklabels=["Normal", "Abnormal"],
                yticklabels=["Normal", "Abnormal"],
                cbar_kws={"label": "Count"})
    ax.set_xlabel("Predicted", fontsize=12, fontweight="bold")
    ax.set_ylabel("Actual", fontsize=12, fontweight="bold")
    title = "Confusion Matrix"
    if title_note:
        title += f" [{title_note}]"
    title += f" (Threshold={metrics.threshold:.4f})"
    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_pr_curve(recall: np.ndarray, precision: np.ndarray, auc: float, 
                  best_threshold: float, output_path: Path) -> None:
    """Plot Precision-Recall curve."""
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


def plot_roc_curve(fpr: np.ndarray, tpr: np.ndarray, auc: float, 
                   output_path: Path) -> None:
    """Plot ROC curve."""
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


def plot_score_distribution(y_true: np.ndarray, scores: np.ndarray, 
                           best_threshold: float, output_path: Path,
                           threshold_label: str = "Best") -> None:
    """Plot score distribution histogram."""
    normal_scores = scores[y_true == 0]
    abnormal_scores = scores[y_true == 1]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(normal_scores, bins=30, alpha=0.6, label="Normal", color="blue", edgecolor="black")
    ax.hist(abnormal_scores, bins=30, alpha=0.6, label="Abnormal", color="red", edgecolor="black")
    ax.axvline(x=best_threshold, color="green", linestyle="--", linewidth=2, 
               label=f"{threshold_label} Threshold ({best_threshold:.4f})")
    ax.set_xlabel("Anomaly Score", fontsize=12, fontweight="bold")
    ax.set_ylabel("Frequency", fontsize=12, fontweight="bold")
    ax.set_title("Score Distribution", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_eval_args()
    scores_path = Path(args.scores_path)
    output_dir = Path(args.output_dir)

    y_true, scores = load_scores(scores_path)

    best_metrics = find_best_threshold(y_true, scores)
    pr_recall, pr_precision, pr_thresholds = precision_recall_curve(y_true, scores)
    roc_fpr, roc_tpr, roc_thresholds = roc_curve(y_true, scores)
    pr_auc = trapezoidal_auc(pr_recall, pr_precision)
    roc_auc = trapezoidal_auc(roc_fpr, roc_tpr)
    hist_counts, hist_edges = score_distribution(scores, bins=20)

    fpr_metrics = None
    achieved_fpr = float("nan")
    if not args.disable_fpr_threshold:
        fpr_metrics, achieved_fpr = threshold_for_target_fpr(y_true, scores, args.target_fpr)
        if fpr_metrics is None:
            print(f"[WARN] Unable to satisfy target FPR {args.target_fpr:.3f}; falling back to best F1 threshold.")

    active_metrics = fpr_metrics if fpr_metrics is not None else best_metrics
    active_label = "FPR" if fpr_metrics is not None else "F1"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp_dir = output_dir / timestamp
    timestamp_dir.mkdir(parents=True, exist_ok=True)
    report_path = timestamp_dir / f"eval_{timestamp}.txt"

    with report_path.open("w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"Autoencoder Evaluation Report - {timestamp}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Samples: total={len(scores)}, normal={(y_true == 0).sum()}, abnormal={(y_true == 1).sum()}\n\n")

        if fpr_metrics is not None:
            fpr_value = achieved_fpr if not np.isnan(achieved_fpr) else 0.0
            f.write(f"Target FPR Threshold (<= {args.target_fpr:.3f}):\n")
            f.write(f"  threshold      : {fpr_metrics.threshold:.6f}\n")
            f.write(f"  achieved FPR   : {fpr_value:.4f}\n")
            f.write(f"  precision      : {fpr_metrics.precision:.4f}\n")
            f.write(f"  recall         : {fpr_metrics.recall:.4f}\n")
            f.write(f"  F1             : {fpr_metrics.f1:.4f}\n")
            f.write(f"  accuracy       : {fpr_metrics.accuracy:.4f}\n")
            f.write(f"  confusion      : TP={fpr_metrics.tp}, FP={fpr_metrics.fp}, "
                    f"TN={fpr_metrics.tn}, FN={fpr_metrics.fn}\n\n")

        f.write("Best Threshold (max F1):\n")
        f.write(f"  threshold      : {best_metrics.threshold:.6f}\n")
        f.write(f"  precision      : {best_metrics.precision:.4f}\n")
        f.write(f"  recall         : {best_metrics.recall:.4f}\n")
        f.write(f"  F1             : {best_metrics.f1:.4f}\n")
        f.write(f"  accuracy       : {best_metrics.accuracy:.4f}\n")
        f.write(f"  confusion      : TP={best_metrics.tp}, FP={best_metrics.fp}, "
                f"TN={best_metrics.tn}, FN={best_metrics.fn}\n\n")

        f.write("Precision-Recall Curve Summary:\n")
        f.write(f"  points         : {len(pr_thresholds)}\n")
        f.write(f"  PR AUC         : {pr_auc:.4f}\n")
        f.write(f"  precision @50% : {float(pr_precision[len(pr_precision)//2]):.4f}\n")
        f.write(f"  recall @50%    : {float(pr_recall[len(pr_recall)//2]):.4f}\n\n")

        f.write("ROC Curve Summary:\n")
        f.write(f"  points         : {len(roc_thresholds)}\n")
        f.write(f"  ROC AUC        : {roc_auc:.4f}\n")
        f.write(f"  TPR @50%       : {float(roc_tpr[len(roc_tpr)//2]):.4f}\n")
        f.write(f"  FPR @50%       : {float(roc_fpr[len(roc_fpr)//2]):.4f}\n\n")

        f.write("Score Distribution (20 bins):\n")
        for count, left, right in zip(hist_counts, hist_edges[:-1], hist_edges[1:]):
            f.write(f"  [{left:.4f}, {right:.4f}): {count}\n")
        f.write("\n")

        f.write("Percentiles:\n")
        for p in [5, 25, 50, 75, 90, 95, 99]:
            f.write(f"  p{p:02d}: {np.percentile(scores, p):.6f}\n")
        f.write("\n")

    print(f"[INFO] Evaluation report saved to {report_path}")

    # Generate visualizations
    print("[INFO] Generating visualizations...")
    plot_confusion_matrix(active_metrics, timestamp_dir / f"confusion_matrix_{timestamp}.png", title_note=active_label)
    print(f"[INFO] Confusion matrix saved to {timestamp_dir / f'confusion_matrix_{timestamp}.png'}")
    
    plot_pr_curve(pr_recall, pr_precision, pr_auc, active_metrics.threshold, 
                  timestamp_dir / f"pr_curve_{timestamp}.png")
    print(f"[INFO] PR curve saved to {timestamp_dir / f'pr_curve_{timestamp}.png'}")
    
    plot_roc_curve(roc_fpr, roc_tpr, roc_auc, timestamp_dir / f"roc_curve_{timestamp}.png")
    print(f"[INFO] ROC curve saved to {timestamp_dir / f'roc_curve_{timestamp}.png'}")
    
    plot_score_distribution(y_true, scores, active_metrics.threshold, 
                           timestamp_dir / f"score_distribution_{timestamp}.png",
                           threshold_label=active_label)
    print(f"[INFO] Score distribution saved to {timestamp_dir / f'score_distribution_{timestamp}.png'}")
    
    print(f"[INFO] All evaluation results saved to {timestamp_dir}")


if __name__ == "__main__":
    main()

