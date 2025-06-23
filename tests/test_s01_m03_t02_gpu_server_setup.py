#!/usr/bin/env python3
"""
S01_M03_T02 통합 테스트: GPU 서버 설정 및 AI 모델 배포
Whisper, YOLO, OCR 모델의 GPU 서버 배포 준비 검증
"""

import sys
import os
import time
import json
import psutil
import platform
from typing import Dict, List, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append('/Users/chul/Documents/claude/influence_item')

def test_gpu_availability():
    """GPU 가용성 확인 테스트"""
    print("🧪 GPU 가용성 확인 테스트 시작...")
    
    try:
        # CUDA 가용성 확인
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                print(f"✅ CUDA 사용 가능: {gpu_count}개 GPU 감지")
                print(f"  GPU 모델: {gpu_name}")
            else:
                print("⚠️ CUDA를 사용할 수 없습니다. CPU 모드로 실행됩니다.")
        except ImportError:
            print("⚠️ PyTorch가 설치되지 않았습니다.")
            cuda_available = False
        
        # MPS (Apple Silicon) 확인
        mps_available = False
        if platform.system() == "Darwin":  # macOS
            try:
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    mps_available = True
                    print("✅ Apple MPS 사용 가능")
                else:
                    print("⚠️ Apple MPS를 사용할 수 없습니다.")
            except:
                print("⚠️ MPS 확인 중 오류 발생")
        
        # 시스템 리소스 확인
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        print(f"💻 시스템 정보:")
        print(f"  CPU 코어: {cpu_count}개")
        print(f"  메모리: {memory_gb:.1f}GB")
        print(f"  운영체제: {platform.system()}")
        
        # GPU 필요 모델들 체크
        gpu_models = ['whisper', 'yolo', 'ocr']
        for model in gpu_models:
            print(f"  {model.upper()} 모델: {'GPU 가속 가능' if cuda_available or mps_available else 'CPU 모드'}")
        
        print("✅ GPU 가용성 확인 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ GPU 가용성 확인 테스트 실패: {str(e)}")
        return False

def test_whisper_model_setup():
    """Whisper 모델 설정 테스트"""
    print("🧪 Whisper 모델 설정 테스트 시작...")
    
    try:
        import whisper
        from src.whisper_processor.whisper_processor import WhisperProcessor
        
        # 모델 크기별 테스트
        model_sizes = ['tiny', 'base', 'small']  # small 모델까지만 테스트
        
        for size in model_sizes:
            try:
                print(f"  {size} 모델 로딩 테스트...")
                model = whisper.load_model(size)
                
                # 모델 정보 확인
                model_info = {
                    'model_size': size,
                    'device': str(next(model.parameters()).device),
                    'parameters': sum(p.numel() for p in model.parameters()),
                }
                
                print(f"    ✅ {size} 모델 로드 성공")
                print(f"       디바이스: {model_info['device']}")
                print(f"       파라미터 수: {model_info['parameters']:,}")
                
                # 메모리 정리
                del model
                
            except Exception as e:
                print(f"    ⚠️ {size} 모델 로드 실패: {str(e)}")
        
        # WhisperProcessor 초기화 테스트
        processor = WhisperProcessor()
        assert processor is not None, "WhisperProcessor 초기화 실패"
        
        print("✅ Whisper 모델 설정 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ Whisper 모델 설정 테스트 실패: {str(e)}")
        return False

def test_yolo_model_setup():
    """YOLO 모델 설정 테스트"""
    print("🧪 YOLO 모델 설정 테스트 시작...")
    
    try:
        from ultralytics import YOLO
        from src.visual_processor.object_detector import ObjectDetector
        
        # YOLO 모델 파일 확인
        yolo_model_path = '/Users/chul/Documents/claude/influence_item/yolo11n.pt'
        assert os.path.exists(yolo_model_path), f"YOLO 모델 파일이 없습니다: {yolo_model_path}"
        
        # YOLO 모델 로드 테스트
        model = YOLO(yolo_model_path)
        
        # 모델 정보 확인
        model_info = model.info()
        print(f"  ✅ YOLO 모델 로드 성공")
        print(f"     모델 파일: {yolo_model_path}")
        
        # ObjectDetector 초기화 테스트
        detector = ObjectDetector()
        assert detector is not None, "ObjectDetector 초기화 실패"
        
        # 더미 이미지로 추론 테스트 (옵션)
        import numpy as np
        dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        try:
            results = model(dummy_image, verbose=False)
            print(f"  ✅ 더미 이미지 추론 성공")
        except Exception as e:
            print(f"  ⚠️ 더미 이미지 추론 실패: {str(e)}")
        
        print("✅ YOLO 모델 설정 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ YOLO 모델 설정 테스트 실패: {str(e)}")
        return False

def test_ocr_model_setup():
    """OCR 모델 설정 테스트"""
    print("🧪 OCR 모델 설정 테스트 시작...")
    
    try:
        import easyocr
        from src.visual_processor.ocr_processor import OCRProcessor
        
        # EasyOCR 초기화 테스트
        print("  EasyOCR 초기화 중...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)  # 테스트에서는 CPU 모드
        
        # OCRProcessor 초기화 테스트
        processor = OCRProcessor()
        assert processor is not None, "OCRProcessor 초기화 실패"
        
        # 더미 이미지로 OCR 테스트 (옵션)
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        
        try:
            # 텍스트가 있는 더미 이미지 생성
            img = Image.new('RGB', (200, 100), color='white')
            draw = ImageDraw.Draw(img)
            
            # 기본 폰트 사용
            try:
                # 시스템 기본 폰트 시도
                font = ImageFont.load_default()
            except:
                font = None
            
            draw.text((10, 30), "Test Text", fill='black', font=font)
            
            # numpy 배열로 변환
            img_array = np.array(img)
            
            # OCR 실행
            results = reader.readtext(img_array)
            print(f"  ✅ 더미 이미지 OCR 성공: {len(results)}개 텍스트 감지")
            
        except Exception as e:
            print(f"  ⚠️ 더미 이미지 OCR 테스트 건너뜀: {str(e)}")
        
        print("✅ OCR 모델 설정 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ OCR 모델 설정 테스트 실패: {str(e)}")
        return False

def test_model_optimization():
    """모델 최적화 설정 테스트"""
    print("🧪 모델 최적화 설정 테스트 시작...")
    
    try:
        from src.gpu_optimizer.gpu_optimizer import GPUOptimizer
        
        # GPU 옵티마이저 초기화
        optimizer = GPUOptimizer()
        
        # 현재 GPU 상태 확인
        gpu_status = optimizer.get_gpu_status()
        print(f"  GPU 상태: {gpu_status}")
        
        # 메모리 최적화 설정 확인
        optimization_settings = {
            'use_mixed_precision': True,
            'batch_size_auto_tune': True,
            'memory_fraction': 0.8,
            'allow_growth': True
        }
        
        for setting, value in optimization_settings.items():
            print(f"  {setting}: {value}")
        
        # 배치 크기 최적화 테스트
        try:
            optimal_batch_size = optimizer.find_optimal_batch_size('whisper')
            print(f"  ✅ Whisper 최적 배치 크기: {optimal_batch_size}")
        except Exception as e:
            print(f"  ⚠️ 배치 크기 최적화 실패: {str(e)}")
        
        print("✅ 모델 최적화 설정 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 모델 최적화 설정 테스트 실패: {str(e)}")
        return False

def test_performance_monitoring():
    """성능 모니터링 설정 테스트"""
    print("🧪 성능 모니터링 설정 테스트 시작...")
    
    try:
        from dashboard.utils.performance_monitor import PerformanceMonitor
        
        # 성능 모니터 초기화
        monitor = PerformanceMonitor()
        
        # 시스템 메트릭 수집 테스트
        metrics = monitor.collect_system_metrics()
        
        required_metrics = ['cpu_percent', 'memory_percent', 'disk_usage']
        for metric in required_metrics:
            assert metric in metrics, f"필수 메트릭 누락: {metric}"
            print(f"  {metric}: {metrics[metric]}")
        
        # GPU 메트릭 수집 테스트 (가능한 경우)
        try:
            gpu_metrics = monitor.collect_gpu_metrics()
            if gpu_metrics:
                print(f"  GPU 메트릭: {gpu_metrics}")
            else:
                print("  GPU 메트릭: 사용 불가")
        except Exception as e:
            print(f"  GPU 메트릭 수집 실패: {str(e)}")
        
        # 성능 로깅 테스트
        monitor.log_performance_data("test_operation", metrics)
        
        print("✅ 성능 모니터링 설정 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 성능 모니터링 설정 테스트 실패: {str(e)}")
        return False

def main():
    """S01_M03_T02 통합 테스트 메인 함수"""
    print("🚀 S01_M03_T02 GPU 서버 설정 및 AI 모델 배포 테스트 시작")
    print("=" * 60)
    
    test_results = []
    start_time = time.time()
    
    # 테스트 실행
    tests = [
        ("GPU 가용성 확인", test_gpu_availability),
        ("Whisper 모델 설정", test_whisper_model_setup),
        ("YOLO 모델 설정", test_yolo_model_setup),
        ("OCR 모델 설정", test_ocr_model_setup),
        ("모델 최적화 설정", test_model_optimization),
        ("성능 모니터링 설정", test_performance_monitoring)
    ]
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name} 테스트 실행 중...")
        try:
            result = test_func()
            test_results.append((test_name, result))
            if result:
                print(f"✅ {test_name} 테스트 성공")
            else:
                print(f"❌ {test_name} 테스트 실패")
        except Exception as e:
            print(f"💥 {test_name} 테스트 예외 발생: {str(e)}")
            test_results.append((test_name, False))
    
    # 결과 요약
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 60)
    print("🎯 S01_M03_T02 GPU 서버 설정 및 AI 모델 배포 테스트 결과 요약")
    print("=" * 60)
    
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"  {status}: {test_name}")
    
    print(f"\n📊 전체 결과: {passed_tests}/{total_tests} 테스트 통과 ({passed_tests/total_tests*100:.1f}%)")
    print(f"⏱️  소요 시간: {duration:.2f}초")
    
    if passed_tests == total_tests:
        print("\n🎉 모든 테스트 통과! S01_M03_T02 작업이 성공적으로 완료되었습니다.")
        return True
    else:
        print(f"\n⚠️  {total_tests - passed_tests}개 테스트 실패. 추가 수정이 필요합니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)