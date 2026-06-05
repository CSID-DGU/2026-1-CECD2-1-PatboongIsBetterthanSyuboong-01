#!/usr/bin/env python3
"""
명령행 인자 파싱 모듈
"""

import argparse


def parse_args():
    """명령행 인자 파싱"""
    p = argparse.ArgumentParser(description='의료 영상 이상 탐지 통합 예제')
    
    # 모드 선택
    p.add_argument('--mode', type=str, required=True,
                   choices=['convert_to_mvtec', 'train_autoencoder', 'train_dual', 'infer_autoencoder', 'infer_dual', 'evaluate'],
                   help='실행 모드')
    
    # 데이터 경로
    p.add_argument('--data_root', type=str, default=None,
                   help='(convert: src_root / train,infer: mvtec 카테고리 루트, evaluate: 불필요)')
    p.add_argument('--img_size', type=int, default=256, help='이미지 크기')
    p.add_argument('--batch_size', type=int, default=16, help='배치 크기')
    p.add_argument('--num_workers', type=int, default=4, help='데이터 로더 워커 수')
    p.add_argument('--seed', type=int, default=42, help='랜덤 시드')
    
    # 디바이스 옵션
    p.add_argument('--device', type=str, default=None, help='사용할 디바이스 (cuda, cpu, cuda:0 등). 지정하지 않으면 자동 감지')
    
    # 증강 옵션
    p.add_argument('--aug', action='store_true', help='학습 시 데이터 증강 사용 (AE)')
    p.add_argument('--clahe', action='store_true', help='CLAHE 대비 보정 사용')
    p.add_argument('--noise_sigma', type=float, default=0.02, help='ToTensor 이후 가우시안 노이즈 표준편차 (기본: 0.02)')
    p.add_argument('--disable_auto_aug', action='store_true',
                   help='자동 증강(aug/clahe/noise) 비활성화 (기본값: 활성화)')
    
    # Autoencoder 옵션
    p.add_argument('--epochs', type=int, default=80, help='학습 에포크 수 (기본 80)')
    p.add_argument('--lr', type=float, default=1e-3, help='학습률')
    p.add_argument('--latent_ch', type=int, default=256, help='Latent channel 수 (기본값: 256, 이미지 해상도 256x256에 맞춤)')
    p.add_argument('--checkpoint_dir', type=str, default='./checkpoints', help='체크포인트 저장 디렉토리')
    p.add_argument('--checkpoint', type=str, help='AE 추론용 체크포인트 경로')
    p.add_argument('--freeze_ae', action='store_true', help='Dual 모델 학습 시 AE 가중치 고정')
    p.add_argument('--stability_weight', type=float, default=0.1,
                   help='스코어 분포 안정화를 위한 추가 패널티 가중치 (기본: 0.1)')
    p.add_argument('--stability_target', type=float, default=0.15,
                   help='스코어 평균을 수렴시키고자 하는 타깃 값 (0~1, 기본값: 0.15)')
    p.add_argument('--stability_warmup', type=int, default=5,
                   help='Stability 패널티 적용 전 워밍업 epoch 수 (기본: 5)')
    p.add_argument('--consistency_weight', type=float, default=0.0,
                   help='Dual branch 간 일관성 손실 가중치 (기본값: 0.0, 비활성화)')
    p.add_argument('--margin', type=float, default=0.1, help='Margin-based 손실의 margin 값 (기본값: 0.1)')
    p.add_argument('--pseudo_anomaly_ratio', type=float, default=0.3, help='배치의 몇 %를 pseudo anomaly로 변환할지 (기본값: 0.3)')
    p.add_argument('--use_fusion', action='store_true',
                   help='Dual branch fusion 모듈 사용 (기본값: False, ADRM 출력 직접 사용)')
    p.add_argument('--staged_training', action='store_true',
                   help='단계별 학습 사용 (AE → Attention → 전체 fine-tuning)')
    
    # 테스트 데이터 제한 옵션
    p.add_argument('--test_limit_per_class', type=int, default=0, help='테스트 시 각 클래스별 최대 샘플 수 (0이면 제한 없음)')
    
    # Convert -> MVTec 옵션
    p.add_argument('--mvtec_out', type=str,
                   help='MVTec 형식 출력 루트 (convert 모드에서 필수)')
    p.add_argument('--category', type=str, default='medical',
                   help='카테고리명 (하위 폴더)')
    
    # 출력 옵션
    p.add_argument('--out_dir', type=str, default='./outs', help='출력 디렉토리')
    
    # 추론 옵션
    p.add_argument('--val_stats_path', type=str, default=None,
                   help='Validation-normal 통계 JSON 파일 경로 (z-score 표준화용, infer_dual 모드에서 사용)')
    p.add_argument('--eval_json_path', type=str, default=None,
                   help='이전 평가 결과 JSON 경로 (threshold 재사용)')
    p.add_argument('--use_robust_score', action='store_true', default=True,
                   help='Robust score 계산 사용 (infer_dual 모드, 기본값: True)')
    
    # 평가 옵션
    p.add_argument('--json_path', type=str, help='평가할 추론 결과 JSON 파일 경로 (evaluate 모드에서 필수)')
    p.add_argument('--model_name', type=str, default='model', help='모델 이름 (결과 파일에 표시)')
    p.add_argument('--class_names', type=str, nargs='+', default=None,
                   help='클래스 이름 리스트 (예: good pneumonia tuberculosis)')
    p.add_argument('--use_fixed_threshold', action='store_true', default=True,
                   help='고정 threshold 사용 (validation-normal 기준, evaluate 모드)')
    p.add_argument('--use_f1_max_threshold', action='store_true', default=False,
                   help='F1-max threshold 탐색 사용 (기존 방식, evaluate 모드)')
    
    return p.parse_args()
