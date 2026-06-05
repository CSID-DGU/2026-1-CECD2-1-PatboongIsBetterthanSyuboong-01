#!/usr/bin/env python3
"""GPU 상태 확인 스크립트"""
import torch

print("=" * 60)
print("GPU 상태 확인")
print("=" * 60)
print(f"PyTorch 버전: {torch.__version__}")
print(f"CUDA 사용 가능: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA 버전: {torch.version.cuda}")
    print(f"cuDNN 버전: {torch.backends.cudnn.version()}")
    print(f"GPU 개수: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"    메모리: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
else:
    print("\n[경고] CUDA를 사용할 수 없습니다!")
    print("가능한 원인:")
    print("  1. PyTorch가 CPU 버전으로 설치됨")
    print("  2. CUDA가 설치되지 않음")
    print("  3. GPU 드라이버 문제")
    print("\n해결 방법:")
    print("  - PyTorch CUDA 버전 재설치 필요")
    print("  - https://pytorch.org/get-started/locally/ 에서 CUDA 버전 확인 후 설치")

print("=" * 60)

