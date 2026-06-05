#!/usr/bin/env python3
"""
CheXpert 데이터를 MVTec 형식으로 변환하는 스크립트
archive/train.csv와 archive/train/ 폴더의 데이터를 MVTec 형식으로 변환합니다.
"""

import pandas as pd
import shutil
from pathlib import Path
from tqdm import tqdm
import os

def convert_chexpert_to_mvtec(
    csv_path: str,
    archive_root: str,
    output_root: str,
    train_ratio: float = 0.8,
    min_samples_per_disease: int = 10
):
    """
    CheXpert 형식 데이터를 MVTec 형식으로 변환
    
    Args:
        csv_path: train.csv 파일 경로
        archive_root: archive 폴더 경로 (이미지 파일이 있는 루트)
        output_root: 출력 루트 경로 (mvtec_root/chest_xray)
        train_ratio: 정상 데이터의 train 비율 (나머지는 test/good로)
        min_samples_per_disease: 질병별 최소 샘플 수 (이하인 경우 'other'로 통합)
    """
    print("=" * 80)
    print("CheXpert -> MVTec 변환 시작")
    print("=" * 80)
    
    # 경로 설정
    csv_path = Path(csv_path)
    archive_root = Path(archive_root)
    output_root = Path(output_root)
    
    # 출력 디렉토리 생성
    train_good_dir = output_root / 'train' / 'good'
    test_good_dir = output_root / 'test' / 'good'
    test_dirs = {}  # 질병별 test 디렉토리
    
    train_good_dir.mkdir(parents=True, exist_ok=True)
    test_good_dir.mkdir(parents=True, exist_ok=True)
    
    # CSV 파일 읽기
    print(f"\n[1] CSV 파일 읽기: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"    총 {len(df):,}개 행 로드 완료")
    
    # 질병 라벨 열 목록
    disease_columns = [
        'Enlarged Cardiomediastinum', 'Cardiomegaly', 'Lung Opacity', 'Lung Lesion',
        'Edema', 'Consolidation', 'Pneumonia', 'Atelectasis', 'Pneumothorax',
        'Pleural Effusion', 'Pleural Other', 'Fracture', 'Support Devices'
    ]
    
    # Path 열 경로 수정 함수
    def fix_path(path_str):
        """CheXpert-v1.0-small/train/... -> train/..."""
        if pd.isna(path_str):
            return None
        path_str = str(path_str)
        if path_str.startswith('CheXpert-v1.0-small/train/'):
            return path_str.replace('CheXpert-v1.0-small/train/', 'train/')
        elif path_str.startswith('train/'):
            return path_str
        else:
            return f"train/{path_str}"
    
    # 경로 수정
    print(f"\n[2] 이미지 경로 수정 중...")
    df['FixedPath'] = df['Path'].apply(fix_path)
    
    # 정상 데이터와 이상 데이터 분류
    print(f"\n[3] 데이터 분류 중...")
    
    # 정상 데이터: No Finding = 1.0
    normal_mask = df['No Finding'] == 1.0
    normal_df = df[normal_mask].copy()
    abnormal_df = df[~normal_mask].copy()
    
    print(f"    정상 데이터: {len(normal_df):,}개")
    print(f"    이상 데이터: {len(abnormal_df):,}개")
    
    # 정상 데이터 train/test 분할
    normal_df = normal_df.sample(frac=1, random_state=42).reset_index(drop=True)  # 셔플
    split_idx = int(len(normal_df) * train_ratio)
    normal_train = normal_df[:split_idx]
    normal_test = normal_df[split_idx:]
    
    print(f"    정상 train: {len(normal_train):,}개")
    print(f"    정상 test: {len(normal_test):,}개")
    
    # 이상 데이터를 질병별로 분류
    print(f"\n[4] 이상 데이터 질병별 분류 중...")
    disease_counts = {}
    
    for idx, row in abnormal_df.iterrows():
        diseases = []
        for col in disease_columns:
            if pd.notna(row[col]) and row[col] == 1.0:
                diseases.append(col)
        
        if len(diseases) == 0:
            # 질병 라벨이 없는 경우 (불확실한 경우 등)
            diseases = ['unknown']
        elif len(diseases) > 1:
            # 여러 질병이 있는 경우 첫 번째 질병 사용
            diseases = [diseases[0]]
        
        disease = diseases[0]
        
        # 질병명을 파일 시스템에 안전한 이름으로 변환
        safe_disease_name = disease.replace(' ', '_').lower()
        
        if safe_disease_name not in disease_counts:
            disease_counts[safe_disease_name] = 0
        disease_counts[safe_disease_name] += 1
    
    # 질병별 통계 출력
    print(f"\n    질병별 데이터 수:")
    for disease, count in sorted(disease_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {disease}: {count:,}개")
    
    # 최소 샘플 수 미만인 질병들을 'other'로 통합
    other_diseases = [d for d, c in disease_counts.items() if c < min_samples_per_disease]
    if other_diseases:
        print(f"\n    최소 샘플 수({min_samples_per_disease}개) 미만 질병을 'other'로 통합:")
        for d in other_diseases:
            print(f"      - {d}")
    
    # 파일 복사 함수
    def copy_image(src_path, dst_path):
        """이미지 파일 복사"""
        try:
            if src_path.exists():
                # 중복 방지: 파일이 이미 존재하면 건너뛰기
                if dst_path.exists():
                    return True  # 이미 복사됨
                shutil.copy2(src_path, dst_path)
                return True
            else:
                return False
        except Exception as e:
            print(f"      [ERROR] 복사 실패: {src_path} -> {e}")
            return False
    
    # 고유한 파일명 생성 함수
    def get_unique_filename(base_dir, original_path):
        """고유한 파일명 생성 (원본 경로 구조를 파일명에 포함)"""
        # 원본 경로에서 patient, study, view 정보 추출
        path_parts = Path(original_path).parts
        filename = Path(original_path).name
        
        # patient/study/view 정보가 있으면 파일명에 포함
        if len(path_parts) >= 3:
            # 예: patient00001_study1_view1_frontal.jpg
            patient = path_parts[-3] if len(path_parts) >= 3 else ""
            study = path_parts[-2] if len(path_parts) >= 2 else ""
            view_name = Path(filename).stem  # 확장자 제외
            ext = Path(filename).suffix
            
            unique_name = f"{patient}_{study}_{view_name}{ext}"
        else:
            # 경로 정보가 없으면 해시 사용
            import hashlib
            path_hash = hashlib.md5(str(original_path).encode()).hexdigest()[:8]
            ext = Path(filename).suffix
            unique_name = f"{path_hash}_{filename}"
        
        dst_path = base_dir / unique_name
        
        # 여전히 중복이면 숫자 추가
        counter = 1
        original_unique_name = unique_name
        while dst_path.exists():
            name_part = Path(original_unique_name).stem
            ext = Path(original_unique_name).suffix
            unique_name = f"{name_part}_{counter}{ext}"
            dst_path = base_dir / unique_name
            counter += 1
        
        return dst_path
    
    # 정상 데이터 복사 (train)
    print(f"\n[5] 정상 데이터 복사 중 (train/good)...")
    copied_train = 0
    failed_train = 0
    
    for idx, row in tqdm(normal_train.iterrows(), total=len(normal_train), desc="  train/good"):
        src_path = archive_root / row['FixedPath']
        if src_path.exists():
            dst_path = get_unique_filename(train_good_dir, row['FixedPath'])
            if copy_image(src_path, dst_path):
                copied_train += 1
            else:
                failed_train += 1
        else:
            failed_train += 1
    
    print(f"    완료: {copied_train:,}개 복사, {failed_train:,}개 실패")
    
    # 정상 데이터 복사 (test)
    print(f"\n[6] 정상 데이터 복사 중 (test/good)...")
    copied_test_good = 0
    failed_test_good = 0
    
    for idx, row in tqdm(normal_test.iterrows(), total=len(normal_test), desc="  test/good"):
        src_path = archive_root / row['FixedPath']
        if src_path.exists():
            dst_path = get_unique_filename(test_good_dir, row['FixedPath'])
            if copy_image(src_path, dst_path):
                copied_test_good += 1
            else:
                failed_test_good += 1
        else:
            failed_test_good += 1
    
    print(f"    완료: {copied_test_good:,}개 복사, {failed_test_good:,}개 실패")
    
    # 이상 데이터 복사 (질병별)
    print(f"\n[7] 이상 데이터 복사 중 (test/<질병명>)...")
    disease_copied = {}
    disease_failed = {}
    
    for idx, row in tqdm(abnormal_df.iterrows(), total=len(abnormal_df), desc="  test/<disease>"):
        # 질병 확인
        diseases = []
        for col in disease_columns:
            if pd.notna(row[col]) and row[col] == 1.0:
                diseases.append(col)
        
        if len(diseases) == 0:
            disease = 'unknown'
        else:
            disease = diseases[0]
        
        # 안전한 이름으로 변환
        safe_disease_name = disease.replace(' ', '_').lower()
        
        # 최소 샘플 수 미만이면 'other'로 통합
        if safe_disease_name in other_diseases:
            safe_disease_name = 'other'
        
        # 디렉토리 생성
        if safe_disease_name not in test_dirs:
            test_dirs[safe_disease_name] = output_root / 'test' / safe_disease_name
            test_dirs[safe_disease_name].mkdir(parents=True, exist_ok=True)
            disease_copied[safe_disease_name] = 0
            disease_failed[safe_disease_name] = 0
        
        # 파일 복사
        src_path = archive_root / row['FixedPath']
        if src_path.exists():
            dst_path = get_unique_filename(test_dirs[safe_disease_name], row['FixedPath'])
            if copy_image(src_path, dst_path):
                disease_copied[safe_disease_name] += 1
            else:
                disease_failed[safe_disease_name] += 1
        else:
            disease_failed[safe_disease_name] += 1
    
    # 결과 요약
    print(f"\n" + "=" * 80)
    print("변환 완료 요약")
    print("=" * 80)
    print(f"\n[정상 데이터]")
    print(f"  train/good: {copied_train:,}개")
    print(f"  test/good: {copied_test_good:,}개")
    
    print(f"\n[이상 데이터 - 질병별]")
    for disease in sorted(disease_copied.keys()):
        copied = disease_copied[disease]
        failed = disease_failed[disease]
        print(f"  test/{disease}: {copied:,}개 (실패: {failed:,}개)")
    
    total_copied = copied_train + copied_test_good + sum(disease_copied.values())
    total_failed = failed_train + failed_test_good + sum(disease_failed.values())
    
    print(f"\n[전체 통계]")
    print(f"  성공: {total_copied:,}개")
    print(f"  실패: {total_failed:,}개")
    print(f"  성공률: {total_copied/(total_copied+total_failed)*100:.2f}%")
    
    print(f"\n[출력 경로]")
    print(f"  {output_root}")
    
    print(f"\n" + "=" * 80)
    print("변환 완료!")
    print("=" * 80)


if __name__ == "__main__":
    # 경로 설정 (PA + ROI 마스킹 데이터 사용)
    csv_path = r"c:\Project\AI\mvtec_root\chest_xray\archive_pa\train.csv"
    archive_root = r"c:\Project\AI\mvtec_root\chest_xray\archive_pa"
    output_root = r"c:\Project\AI\mvtec_root\chest_xray"
    
    # 변환 실행
    convert_chexpert_to_mvtec(
        csv_path=csv_path,
        archive_root=archive_root,
        output_root=output_root,
        train_ratio=0.8,  # 정상 데이터의 80%를 train으로
        min_samples_per_disease=10  # 10개 미만은 'other'로 통합
    )

