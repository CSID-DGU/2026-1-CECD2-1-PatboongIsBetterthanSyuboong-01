#!/usr/bin/env python3
"""
모델 평가 모듈
추론 결과 JSON 파일을 읽어서 실제 라벨과 비교하여 성능을 평가합니다.
"""

import os
import json
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    roc_auc_score, average_precision_score, roc_curve, precision_recall_curve,
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from pathlib import Path
import seaborn as sns


def convert_to_python_type(obj):
    """NumPy 타입을 Python 기본 타입으로 변환 (재귀적)"""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_python_type(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_python_type(item) for item in obj]
    elif isinstance(obj, (bool, str, type(None))):
        return obj
    else:
        # 기타 타입은 그대로 반환 (이미 Python 기본 타입인 경우)
        return obj


def load_scores(json_path):
    """JSON 파일에서 score와 label 로드"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    scores = [item['score'] for item in data]
    labels = [item['label'] for item in data]
    
    return np.array(scores), np.array(labels)


def evaluate_binary(y_true, y_scores, threshold=None, use_fixed_threshold=True):
    """이진 분류 평가 (정상=0 vs 이상=1 이상)
    Args:
        threshold: 고정 threshold (None이면 validation-normal의 p99.5 또는 mean+3σ 사용)
        use_fixed_threshold: True면 고정 threshold 사용, False면 F1-max threshold 탐색
    """
    # 라벨을 이진으로 변환: 0 = 정상, 1 이상 = 이상
    y_true_binary = (y_true > 0).astype(int)
    
    # 고정 threshold 사용 (validation-normal 기준)
    if threshold is None and use_fixed_threshold:
        # 정상 샘플의 통계로 threshold 계산
        normal_scores = y_scores[y_true_binary == 0]
        if len(normal_scores) > 0:
            # p99.5 또는 mean+3σ 중 큰 값 사용
            p99_5 = np.percentile(normal_scores, 99.5)
            mean_3sigma = np.mean(normal_scores) + 3 * np.std(normal_scores)
            threshold = max(p99_5, mean_3sigma)
            print(f"[INFO] Validation-normal 기준 threshold: p99.5={p99_5:.6e}, mean+3σ={mean_3sigma:.6e}, 사용={threshold:.6e}")
        else:
            # 정상 샘플이 없으면 F1-max 사용
            fpr, tpr, thresholds = roc_curve(y_true_binary, y_scores)
            j_scores = tpr - fpr
            optimal_idx = np.argmax(j_scores)
            threshold = thresholds[optimal_idx]
            print(f"[WARN] 정상 샘플이 없어 F1-max threshold 사용: {threshold:.6e}")
    elif threshold is None:
        # F1-max threshold 탐색 (기존 방식)
        fpr, tpr, thresholds = roc_curve(y_true_binary, y_scores)
        j_scores = tpr - fpr
        optimal_idx = np.argmax(j_scores)
        threshold = thresholds[optimal_idx]
    
    # 이진 예측
    y_pred_binary = (y_scores >= threshold).astype(int)
    
    # 메트릭 계산
    metrics = {
        'roc_auc': roc_auc_score(y_true_binary, y_scores),
        'pr_auc': average_precision_score(y_true_binary, y_scores),
        'accuracy': accuracy_score(y_true_binary, y_pred_binary),
        'precision': precision_score(y_true_binary, y_pred_binary, zero_division=0),
        'recall': recall_score(y_true_binary, y_pred_binary, zero_division=0),
        'f1': f1_score(y_true_binary, y_pred_binary, zero_division=0),
        'threshold': float(threshold)
    }
    
    # Confusion matrix
    cm = confusion_matrix(y_true_binary, y_pred_binary)
    metrics['confusion_matrix'] = cm.tolist()
    tn, fp, fn, tp = cm.ravel()
    metrics['tn'] = int(tn)
    metrics['fp'] = int(fp)
    metrics['fn'] = int(fn)
    metrics['tp'] = int(tp)
    
    # 모든 값을 Python 기본 타입으로 변환
    metrics = convert_to_python_type(metrics)
    
    return metrics, float(threshold)


def evaluate_multiclass(y_true, y_scores, class_names=None):
    """다중 클래스 평가 (각 질병별)"""
    unique_labels = np.unique(y_true)
    n_classes = len(unique_labels)
    
    if class_names is None:
        class_names = [f'class_{i}' for i in unique_labels]
    else:
        # class_names가 딕셔너리인 경우
        if isinstance(class_names, dict):
            class_names = [class_names.get(i, f'class_{i}') for i in unique_labels]
    
    results = {}
    
    # 각 클래스별 이진 분류 평가 (One-vs-Rest)
    for i, label in enumerate(unique_labels):
        y_true_ovr = (y_true == label).astype(int)
        
        # 해당 클래스에 대한 ROC-AUC 계산
        if len(np.unique(y_true_ovr)) > 1:  # 양성/음성 모두 있는 경우만
            try:
                roc_auc = roc_auc_score(y_true_ovr, y_scores)
                pr_auc = average_precision_score(y_true_ovr, y_scores)
            except ValueError:
                roc_auc = np.nan
                pr_auc = np.nan
        else:
            roc_auc = np.nan
            pr_auc = np.nan
        
        # 최적 threshold로 이진 예측
        fpr, tpr, thresholds = roc_curve(y_true_ovr, y_scores)
        if len(thresholds) > 0:
            j_scores = tpr - fpr
            optimal_idx = np.argmax(j_scores)
            threshold = thresholds[optimal_idx]
            y_pred_ovr = (y_scores >= threshold).astype(int)
            
            precision = precision_score(y_true_ovr, y_pred_ovr, zero_division=0)
            recall = recall_score(y_true_ovr, y_pred_ovr, zero_division=0)
            f1 = f1_score(y_true_ovr, y_pred_ovr, zero_division=0)
        else:
            threshold = np.nan
            precision = np.nan
            recall = np.nan
            f1 = np.nan
        
        results[class_names[i]] = {
            'label': int(label),
            'roc_auc': float(roc_auc) if not np.isnan(roc_auc) else None,
            'pr_auc': float(pr_auc) if not np.isnan(pr_auc) else None,
            'precision': float(precision) if not np.isnan(precision) else None,
            'recall': float(recall) if not np.isnan(recall) else None,
            'f1': float(f1) if not np.isnan(f1) else None,
            'threshold': float(threshold) if not np.isnan(threshold) else None,
            'n_samples': int(np.sum(y_true == label))
        }
    
    # 모든 값을 Python 기본 타입으로 변환
    results = convert_to_python_type(results)
    
    return results


def plot_roc_curve(y_true, y_scores, save_path):
    """ROC 곡선 그리기"""
    y_true_binary = (y_true > 0).astype(int)
    fpr, tpr, _ = roc_curve(y_true_binary, y_scores)
    roc_auc = roc_auc_score(y_true_binary, y_scores)
    
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic (ROC) Curve')
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_pr_curve(y_true, y_scores, save_path):
    """Precision-Recall 곡선 그리기"""
    y_true_binary = (y_true > 0).astype(int)
    precision, recall, _ = precision_recall_curve(y_true_binary, y_scores)
    pr_auc = average_precision_score(y_true_binary, y_scores)
    
    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, color='darkorange', lw=2, label=f'PR curve (AUC = {pr_auc:.3f})')
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve')
    plt.legend(loc="lower left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_confusion_matrix(y_true, y_pred, save_path, class_names=None):
    """Confusion Matrix 그리기"""
    if class_names is None:
        class_names = ['Normal', 'Anomaly']
    
    cm = confusion_matrix(y_true, y_pred)
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=class_names, yticklabels=class_names)
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.title('Confusion Matrix')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_score_distribution(y_true, y_scores, save_path, class_names=None):
    """Score 분포 히스토그램 그리기"""
    if class_names is None:
        class_names = ['Normal', 'Anomaly']
    
    y_true_binary = (y_true > 0).astype(int)
    normal_scores = y_scores[y_true_binary == 0]
    anomaly_scores = y_scores[y_true_binary == 1]
    
    plt.figure(figsize=(10, 6))
    plt.hist(normal_scores, bins=50, alpha=0.7, label=class_names[0], color='blue', density=True)
    plt.hist(anomaly_scores, bins=50, alpha=0.7, label=class_names[1], color='red', density=True)
    plt.xlabel('Anomaly Score')
    plt.ylabel('Density')
    plt.title('Score Distribution by Class')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def evaluate_model(json_path, output_dir, model_name='model', class_names=None, use_fixed_threshold=True):
    """모델 평가 메인 함수
    Args:
        json_path: 추론 결과 JSON 파일 경로
        output_dir: 평가 결과 저장 디렉토리
        model_name: 모델 이름
        class_names: 클래스 이름 딕셔너리
        use_fixed_threshold: True면 고정 threshold 사용 (validation-normal 기준), False면 F1-max threshold 탐색
    """
    print(f"\n{'='*80}")
    print(f"모델 평가: {model_name}")
    print(f"{'='*80}")
    
    # 출력 디렉토리 생성
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 점수와 라벨 로드
    print(f"\n[1] 결과 파일 로드: {json_path}")
    y_scores, y_true = load_scores(json_path)
    print(f"    총 {len(y_scores)}개 샘플")
    print(f"    정상: {np.sum(y_true == 0)}개, 이상: {np.sum(y_true > 0)}개")
    
    # 클래스별 샘플 수 균형 확인
    normal_count = int(np.sum(y_true == 0))
    anomaly_count = int(np.sum(y_true > 0))
    print(f"    [균형 확인] 정상: {normal_count}개, 이상: {anomaly_count}개")
    if normal_count == 0 or anomaly_count == 0:
        print(f"    [WARN] 클래스 불균형이 심합니다!")
    
    # 이진 분류 평가 (고정 threshold 사용)
    print(f"\n[2] 이진 분류 평가 (정상 vs 이상)")
    binary_metrics, threshold = evaluate_binary(y_true, y_scores, threshold=None, use_fixed_threshold=use_fixed_threshold)
    
    print(f"    ROC-AUC: {binary_metrics['roc_auc']:.4f}")
    print(f"    PR-AUC:  {binary_metrics['pr_auc']:.4f}")
    print(f"    Accuracy: {binary_metrics['accuracy']:.4f}")
    print(f"    Precision: {binary_metrics['precision']:.4f}")
    print(f"    Recall: {binary_metrics['recall']:.4f}")
    print(f"    F1-Score: {binary_metrics['f1']:.4f}")
    print(f"    Threshold: {threshold:.6e}")
    print(f"    Confusion Matrix:")
    print(f"      TN={binary_metrics['tn']}, FP={binary_metrics['fp']}")
    print(f"      FN={binary_metrics['fn']}, TP={binary_metrics['tp']}")
    if binary_metrics['tn'] == 0:
        print(f"    [WARN] TN=0입니다! threshold가 너무 낮거나 데이터 불균형이 심합니다.")
    
    # 다중 클래스 평가
    print(f"\n[3] 다중 클래스 평가 (각 질병별)")
    multiclass_results = evaluate_multiclass(y_true, y_scores, class_names)
    
    for class_name, metrics in multiclass_results.items():
        print(f"\n    [{class_name}]")
        print(f"      샘플 수: {metrics['n_samples']}")
        if metrics['roc_auc'] is not None:
            print(f"      ROC-AUC: {metrics['roc_auc']:.4f}")
            print(f"      PR-AUC: {metrics['pr_auc']:.4f}")
            print(f"      Precision: {metrics['precision']:.4f}")
            print(f"      Recall: {metrics['recall']:.4f}")
            print(f"      F1-Score: {metrics['f1']:.4f}")
        else:
            print(f"      (평가 불가: 양성 또는 음성 샘플이 없음)")
    
    # 시각화
    print(f"\n[4] 시각화 생성")
    y_pred_binary = (y_scores >= threshold).astype(int)
    y_true_binary = (y_true > 0).astype(int)
    
    plot_roc_curve(y_true, y_scores, output_dir / f'roc_curve_{timestamp}.png')
    print(f"    -> ROC 곡선: {output_dir / f'roc_curve_{timestamp}.png'}")
    
    plot_pr_curve(y_true, y_scores, output_dir / f'pr_curve_{timestamp}.png')
    print(f"    -> PR 곡선: {output_dir / f'pr_curve_{timestamp}.png'}")
    
    plot_confusion_matrix(y_true_binary, y_pred_binary, 
                         output_dir / f'confusion_matrix_{timestamp}.png')
    print(f"    -> Confusion Matrix: {output_dir / f'confusion_matrix_{timestamp}.png'}")
    
    plot_score_distribution(y_true, y_scores, 
                           output_dir / f'score_distribution_{timestamp}.png')
    print(f"    -> Score 분포: {output_dir / f'score_distribution_{timestamp}.png'}")
    
    # 결과 저장
    print(f"\n[5] 결과 저장")
    results = {
        'model_name': model_name,
        'binary_classification': binary_metrics,
        'multiclass_classification': multiclass_results,
        'summary': {
            'total_samples': int(len(y_scores)),
            'normal_samples': int(np.sum(y_true == 0)),
            'anomaly_samples': int(np.sum(y_true > 0)),
            'best_roc_auc': float(binary_metrics['roc_auc']),
            'best_pr_auc': float(binary_metrics['pr_auc']),
            'best_f1': float(binary_metrics['f1'])
        }
    }
    
    # 모든 NumPy 타입을 Python 기본 타입으로 변환
    results = convert_to_python_type(results)
    
    # JSON 저장
    json_path_out = output_dir / f'evaluation_results_{timestamp}.json'
    with open(json_path_out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"    -> JSON 결과: {json_path_out}")
    
    # 텍스트 리포트 저장
    txt_path_out = output_dir / f'evaluation_report_{timestamp}.txt'
    with open(txt_path_out, 'w', encoding='utf-8') as f:
        f.write(f"{'='*80}\n")
        f.write(f"모델 평가 리포트: {model_name}\n")
        f.write(f"{'='*80}\n\n")
        
        f.write("이진 분류 평가 (정상 vs 이상)\n")
        f.write("-" * 80 + "\n")
        f.write(f"ROC-AUC:     {binary_metrics['roc_auc']:.4f}\n")
        f.write(f"PR-AUC:      {binary_metrics['pr_auc']:.4f}\n")
        f.write(f"Accuracy:    {binary_metrics['accuracy']:.4f}\n")
        f.write(f"Precision:   {binary_metrics['precision']:.4f}\n")
        f.write(f"Recall:      {binary_metrics['recall']:.4f}\n")
        f.write(f"F1-Score:    {binary_metrics['f1']:.4f}\n")
        f.write(f"Threshold:   {threshold:.6f}\n\n")
        f.write(f"Confusion Matrix:\n")
        f.write(f"  TN={binary_metrics['tn']}, FP={binary_metrics['fp']}\n")
        f.write(f"  FN={binary_metrics['fn']}, TP={binary_metrics['tp']}\n\n")
        
        f.write("다중 클래스 평가 (각 질병별)\n")
        f.write("-" * 80 + "\n")
        for class_name, metrics in multiclass_results.items():
            f.write(f"\n[{class_name}]\n")
            f.write(f"  샘플 수: {metrics['n_samples']}\n")
            if metrics['roc_auc'] is not None:
                f.write(f"  ROC-AUC: {metrics['roc_auc']:.4f}\n")
                f.write(f"  PR-AUC: {metrics['pr_auc']:.4f}\n")
                f.write(f"  Precision: {metrics['precision']:.4f}\n")
                f.write(f"  Recall: {metrics['recall']:.4f}\n")
                f.write(f"  F1-Score: {metrics['f1']:.4f}\n")
            else:
                f.write(f"  (평가 불가)\n")
    
    print(f"    -> 텍스트 리포트: {txt_path_out}")
    
    print(f"\n{'='*80}")
    print(f"평가 완료! 결과는 {output_dir}에 저장되었습니다.")
    print(f"{'='*80}\n")
    
    return results


def main():
    """명령행에서 직접 실행할 때"""
    import argparse
    
    parser = argparse.ArgumentParser(description='모델 평가')
    parser.add_argument('--json_path', type=str, required=True,
                       help='추론 결과 JSON 파일 경로 (ae_scores.json, dual_scores.json, fd_scores.json)')
    parser.add_argument('--output_dir', type=str, required=True,
                       help='평가 결과 저장 디렉토리')
    parser.add_argument('--model_name', type=str, default='model',
                       help='모델 이름 (결과 파일에 표시)')
    parser.add_argument('--class_names', type=str, nargs='+', default=None,
                       help='클래스 이름 리스트 (예: good pneumonia tuberculosis)')
    parser.add_argument('--use_fixed_threshold', action='store_true', default=True,
                       help='고정 threshold 사용 (validation-normal 기준)')
    parser.add_argument('--use_f1_max_threshold', action='store_true', default=False,
                       help='F1-max threshold 탐색 사용 (기존 방식)')
    
    args = parser.parse_args()
    
    # 클래스 이름 딕셔너리 생성 (MVTec 형식: good=0, 나머지=1,2,3...)
    class_names_dict = None
    if args.class_names:
        class_names_dict = {i: name for i, name in enumerate(args.class_names)}
    
    use_fixed_threshold = args.use_fixed_threshold and not args.use_f1_max_threshold
    evaluate_model(args.json_path, args.output_dir, args.model_name, class_names_dict, use_fixed_threshold=use_fixed_threshold)


if __name__ == '__main__':
    main()

