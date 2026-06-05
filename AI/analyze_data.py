#!/usr/bin/env python3
"""
데이터 품질 분석 스크립트
train.csv 파일의 구조와 품질을 확인하여 모델 훈련에 적합한지 판단합니다.
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path
from collections import Counter

def analyze_train_data(csv_path, archive_root):
    """train.csv 데이터 분석"""
    print("=" * 80)
    print("데이터 품질 분석 시작")
    print("=" * 80)
    
    # CSV 파일 읽기
    print(f"\n[1] CSV 파일 읽기: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
        print(f"[OK] 성공적으로 읽음: {len(df)} 행, {len(df.columns)} 열")
    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        return
    
    # 기본 정보
    print(f"\n[2] 데이터 기본 정보")
    print(f"  - 총 행 수: {len(df):,}")
    print(f"  - 총 열 수: {len(df.columns)}")
    print(f"  - 열 이름: {list(df.columns)}")
    
    # 결측값 확인
    print(f"\n[3] 결측값 분석")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_info = pd.DataFrame({
        '결측값 수': missing,
        '결측값 비율(%)': missing_pct
    })
    missing_info = missing_info[missing_info['결측값 수'] > 0].sort_values('결측값 수', ascending=False)
    if len(missing_info) > 0:
        print("  결측값이 있는 열:")
        print(missing_info.to_string())
    else:
        print("  [OK] 결측값 없음")
    
    # Path 열 확인
    print(f"\n[4] 이미지 경로 확인")
    if 'Path' in df.columns:
        paths = df['Path'].dropna()
        print(f"  - 유효한 경로 수: {len(paths):,}")
        
        # 경로 유효성 확인 (샘플)
        archive_path = Path(archive_root)
        valid_paths = 0
        invalid_paths = 0
        sample_size = min(1000, len(paths))
        
        print(f"  - 샘플 검증 중 ({sample_size}개)...")
        for idx, path in enumerate(paths.head(sample_size)):
            full_path = archive_path / path
            if full_path.exists():
                valid_paths += 1
            else:
                invalid_paths += 1
                if invalid_paths <= 5:  # 처음 5개만 출력
                    print(f"    [ERROR] 파일 없음: {path}")
        
        print(f"  - 샘플 검증 결과: 유효 {valid_paths}개, 무효 {invalid_paths}개")
        if invalid_paths > 0:
            print(f"    [WARNING] 경고: 일부 이미지 파일이 존재하지 않습니다!")
    else:
        print("  [ERROR] 'Path' 열이 없습니다!")
    
    # 라벨 열 확인
    print(f"\n[5] 라벨 분포 분석")
    label_columns = [col for col in df.columns if col not in ['Path', 'Sex', 'Age', 'Frontal/Lateral', 'AP/PA']]
    
    if label_columns:
        print(f"  - 라벨 열 수: {len(label_columns)}")
        print(f"  - 라벨 열: {label_columns}")
        
        # 각 라벨의 값 분포
        print(f"\n  라벨별 값 분포:")
        for col in label_columns[:5]:  # 처음 5개만 상세 출력
            values = df[col].dropna()
            if len(values) > 0:
                value_counts = Counter(values)
                print(f"    [{col}]")
                for val, count in sorted(value_counts.items(), key=lambda x: x[1], reverse=True):
                    pct = (count / len(df)) * 100
                    print(f"      {val}: {count:,} ({pct:.2f}%)")
    
    # 정상/이상 데이터 분류
    print(f"\n[6] 정상/이상 데이터 분류")
    normal = pd.DataFrame()  # 초기화
    if 'No Finding' in df.columns:
        # No Finding = 1.0이면 정상
        normal = df[df['No Finding'] == 1.0]
        abnormal = df[df['No Finding'] != 1.0]
        print(f"  - 'No Finding' = 1.0 (정상): {len(normal):,} ({len(normal)/len(df)*100:.2f}%)")
        print(f"  - 'No Finding' ≠ 1.0 (이상 가능): {len(abnormal):,} ({len(abnormal)/len(df)*100:.2f}%)")
        
        # 다른 질병 라벨이 있는 경우
        disease_cols = [col for col in label_columns if col != 'No Finding']
        has_disease = df[disease_cols].apply(lambda x: (x == 1.0).any(), axis=1).sum()
        print(f"  - 질병 라벨이 1.0인 경우: {has_disease:,} ({has_disease/len(df)*100:.2f}%)")
    else:
        print("  [WARNING] 'No Finding' 열이 없어 정상/이상 분류 불가")
    
    # 연령 및 성별 분포
    print(f"\n[7] 메타데이터 분석")
    if 'Age' in df.columns:
        ages = df['Age'].dropna()
        if len(ages) > 0:
            print(f"  - 연령: 평균 {ages.mean():.1f}세, 범위 {ages.min():.0f}-{ages.max():.0f}세")
    
    if 'Sex' in df.columns:
        sex_counts = df['Sex'].value_counts()
        print(f"  - 성별 분포:")
        for sex, count in sex_counts.items():
            print(f"    {sex}: {count:,} ({count/len(df)*100:.2f}%)")
    
    # 중복 확인
    print(f"\n[8] 중복 데이터 확인")
    if 'Path' in df.columns:
        duplicates = df['Path'].duplicated().sum()
        print(f"  - 중복된 경로: {duplicates:,} ({duplicates/len(df)*100:.2f}%)")
        if duplicates > 0:
            print(f"    [WARNING] 경고: 중복된 이미지 경로가 있습니다!")
    
    # 모델 훈련 적합성 평가
    print(f"\n" + "=" * 80)
    print("모델 훈련 적합성 평가")
    print("=" * 80)
    
    issues = []
    warnings = []
    
    # 필수 체크
    if 'Path' not in df.columns:
        issues.append("[ERROR] 'Path' 열이 없습니다 - 이미지 경로를 찾을 수 없습니다")
    
    if len(df) < 100:
        issues.append(f"[ERROR] 데이터가 너무 적습니다 ({len(df)}개) - 최소 100개 이상 권장")
    
    # 경고 체크
    if missing_info.shape[0] > 0 and missing_info['결측값 비율(%)'].max() > 50:
        warnings.append("[WARNING] 일부 열의 결측값 비율이 50%를 초과합니다")
    
    if 'No Finding' not in df.columns:
        warnings.append("[WARNING] 'No Finding' 열이 없어 정상 데이터를 식별하기 어렵습니다")
    elif len(normal) > 0 and len(normal) < len(df) * 0.1:
        warnings.append(f"[WARNING] 정상 데이터가 전체의 10% 미만입니다 ({len(normal)/len(df)*100:.2f}%)")
    
    if duplicates > len(df) * 0.1:
        warnings.append(f"[WARNING] 중복 데이터가 전체의 10%를 초과합니다 ({duplicates/len(df)*100:.2f}%)")
    
    # 결과 출력
    if issues:
        print("\n[심각한 문제]")
        for issue in issues:
            print(f"  {issue}")
    
    if warnings:
        print("\n[경고 사항]")
        for warning in warnings:
            print(f"  {warning}")
    
    if not issues and not warnings:
        print("\n[OK] 데이터가 모델 훈련에 적합해 보입니다!")
    elif not issues:
        print("\n[OK] 데이터는 사용 가능하지만, 위 경고 사항을 고려하세요.")
    else:
        print("\n[ERROR] 데이터에 심각한 문제가 있어 수정이 필요합니다.")
    
    # 추가 권장사항
    print(f"\n[권장사항]")
    print(f"  1. 현재 프로젝트는 MVTec 형식 (train/good/, test/good/, test/pneumonia/)을 기대합니다")
    print(f"  2. CheXpert 형식의 CSV를 MVTec 형식으로 변환해야 할 수 있습니다")
    print(f"  3. 정상 데이터만 선별하여 train/good/ 폴더에 배치하세요")
    print(f"  4. 이상 데이터는 test/<질병명>/ 폴더에 배치하세요")
    
    print(f"\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)

if __name__ == "__main__":
    csv_path = r"c:\Project\AI\mvtec_root\chest_xray\archive\train.csv"
    archive_root = r"c:\Project\AI\mvtec_root\chest_xray\archive"
    
    analyze_train_data(csv_path, archive_root)

