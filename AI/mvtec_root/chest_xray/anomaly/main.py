#!/usr/bin/env python3
"""
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
"""
       

from .options import parse_args
from .environment import convert_to_mvtec
from .train import train_autoencoder, train_dual_anomaly, train_dual_anomaly_staged
from .inference import infer_autoencoder, infer_dual_anomaly
from .evaluate import evaluate_model
from .utils import ensure_dir


def main():
    """메인 진입점"""
    args = parse_args()
    
    if args.mode == 'convert_to_mvtec':
        assert args.mvtec_out, '--mvtec_out required'
        convert_to_mvtec(args.data_root, args.mvtec_out, args.category)
    elif args.mode == 'train_autoencoder':
        train_autoencoder(args)
    elif args.mode == 'train_dual':
        # 단계별 학습 옵션 확인
        use_staged = getattr(args, 'staged_training', False)
        if use_staged:
            train_dual_anomaly_staged(args)
        else:
            train_dual_anomaly(args)
    elif args.mode == 'infer_autoencoder':
        assert args.checkpoint, '--checkpoint required'
        ensure_dir(args.out_dir)
        infer_autoencoder(args)
    elif args.mode == 'infer_dual':
        assert args.checkpoint, '--checkpoint required'
        ensure_dir(args.out_dir)
        infer_dual_anomaly(args)
    elif args.mode == 'evaluate':
        assert args.json_path, '--json_path required'
        ensure_dir(args.out_dir)
        # 클래스 이름 딕셔너리 생성 (MVTec 형식: good=0, 나머지=1,2,3...)
        class_names_dict = None
        if args.class_names:
            class_names_dict = {i: name for i, name in enumerate(args.class_names)}
        # Threshold 옵션 전달
        use_fixed_threshold = getattr(args, 'use_fixed_threshold', True) and not getattr(args, 'use_f1_max_threshold', False)
        evaluate_model(args.json_path, args.out_dir, args.model_name, class_names_dict, use_fixed_threshold=use_fixed_threshold)


if __name__ == '__main__':
    main()

