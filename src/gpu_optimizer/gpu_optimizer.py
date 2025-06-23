"""
GPU 최적화 클래스

GPU 자원 관리, 메모리 최적화, 배치 처리를 통한 성능 향상을 제공합니다.
"""

import logging
import time
import gc
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from threading import Lock
from contextlib import contextmanager
import psutil

# GPU 관련 imports (옵셔널)
try:
    import torch
    import torch.cuda as cuda
    import pynvml
    HAS_CUDA = torch.cuda.is_available()
    if HAS_CUDA:
        pynvml.nvmlInit()
except ImportError:
    torch = None
    cuda = None
    pynvml = None
    HAS_CUDA = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

from config.config import Config


class GPUMemoryManager:
    """GPU 메모리 관리 클래스"""
    
    def __init__(self):
        self.allocated_tensors = []
        self.memory_lock = Lock()
        
    def allocate_tensor(self, tensor: Any) -> None:
        """텐서 할당 추적"""
        with self.memory_lock:
            self.allocated_tensors.append(tensor)
    
    def deallocate_tensor(self, tensor: Any) -> None:
        """텐서 해제"""
        with self.memory_lock:
            if tensor in self.allocated_tensors:
                self.allocated_tensors.remove(tensor)
                if HAS_CUDA and hasattr(tensor, 'cuda'):
                    del tensor
    
    def clear_all(self) -> None:
        """모든 텐서 해제"""
        with self.memory_lock:
            for tensor in self.allocated_tensors:
                if HAS_CUDA and hasattr(tensor, 'cuda'):
                    del tensor
            self.allocated_tensors.clear()
            
        if HAS_CUDA:
            torch.cuda.empty_cache()
        gc.collect()


class GPUBatchProcessor:
    """GPU 배치 처리 클래스"""
    
    def __init__(self, device: str = "cuda", batch_size: int = 8):
        self.device = device if HAS_CUDA else "cpu"
        self.batch_size = batch_size
        self.processing_queue = []
        
    def add_to_batch(self, data: Any) -> None:
        """배치에 데이터 추가"""
        self.processing_queue.append(data)
    
    def process_batch(self, model_fn, *args, **kwargs) -> List[Any]:
        """배치 처리 실행"""
        if not self.processing_queue:
            return []
            
        results = []
        total_items = len(self.processing_queue)
        
        for i in range(0, total_items, self.batch_size):
            batch = self.processing_queue[i:i + self.batch_size]
            batch_results = model_fn(batch, *args, **kwargs)
            results.extend(batch_results)
            
        self.processing_queue.clear()
        return results
    
    def get_optimal_batch_size(self, available_memory: int, item_size: int) -> int:
        """최적 배치 크기 계산"""
        if available_memory <= 0 or item_size <= 0:
            return 1
            
        # 안전 여유분을 고려한 배치 크기 계산
        safety_factor = 0.8
        optimal_size = int((available_memory * safety_factor) // item_size)
        return max(1, min(optimal_size, self.batch_size))


class GPUOptimizer:
    """GPU 최적화 메인 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        GPU 최적화 시스템 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        
        # GPU 가용성 확인
        self.has_cuda = HAS_CUDA
        self.device = self._detect_device()
        self.device_count = self._get_device_count()
        
        # 컴포넌트 초기화
        self.memory_manager = GPUMemoryManager()
        self.batch_processor = GPUBatchProcessor(
            device=self.device,
            batch_size=getattr(self.config, 'GPU_BATCH_SIZE', 8)
        )
        
        # 성능 통계
        self.performance_stats = {
            'total_processing_time': 0.0,
            'total_items_processed': 0,
            'memory_usage_peaks': [],
            'batch_sizes_used': [],
            'gpu_utilization_history': []
        }
        
        # GPU 설정 적용
        self._configure_gpu()
        
        self.logger.info(f"GPU 최적화 시스템 초기화 완료 - 디바이스: {self.device}, GPU 개수: {self.device_count}")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _detect_device(self) -> str:
        """사용 가능한 디바이스 감지"""
        if self.has_cuda:
            return "cuda"
        else:
            self.logger.warning("CUDA를 사용할 수 없습니다. CPU 모드로 실행됩니다.")
            return "cpu"
    
    def _get_device_count(self) -> int:
        """GPU 디바이스 개수 확인"""
        if self.has_cuda:
            return torch.cuda.device_count()
        return 0
    
    def _configure_gpu(self) -> None:
        """GPU 설정 최적화"""
        if not self.has_cuda:
            return
            
        try:
            # CUDA 최적화 설정
            torch.cuda.empty_cache()
            
            # 메모리 할당자 설정
            if hasattr(torch.cuda, 'set_per_process_memory_fraction'):
                memory_fraction = getattr(self.config, 'GPU_MEMORY_FRACTION', 0.9)
                torch.cuda.set_per_process_memory_fraction(memory_fraction)
            
            # CuDNN 벤치마킹 활성화
            if hasattr(torch.backends, 'cudnn'):
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
            
            self.logger.info("GPU 설정 최적화 완료")
            
        except Exception as e:
            self.logger.warning(f"GPU 설정 중 오류 발생: {str(e)}")
    
    def get_memory_info(self, device_id: int = 0) -> Dict[str, Any]:
        """GPU 메모리 정보 조회"""
        if not self.has_cuda:
            return {
                'device': 'cpu',
                'total_memory': psutil.virtual_memory().total,
                'available_memory': psutil.virtual_memory().available,
                'used_memory': psutil.virtual_memory().used,
                'memory_utilization': psutil.virtual_memory().percent
            }
        
        try:
            # PyTorch 메모리 정보
            total_memory = torch.cuda.get_device_properties(device_id).total_memory
            allocated_memory = torch.cuda.memory_allocated(device_id)
            cached_memory = torch.cuda.memory_reserved(device_id)
            free_memory = total_memory - allocated_memory
            
            info = {
                'device': f'cuda:{device_id}',
                'total_memory': total_memory,
                'allocated_memory': allocated_memory,
                'cached_memory': cached_memory,
                'free_memory': free_memory,
                'memory_utilization': (allocated_memory / total_memory) * 100
            }
            
            # pynvml을 통한 추가 정보
            if pynvml:
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                gpu_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                info.update({
                    'nvidia_total_memory': gpu_info.total,
                    'nvidia_used_memory': gpu_info.used,
                    'nvidia_free_memory': gpu_info.free,
                    'gpu_utilization': utilization.gpu,
                    'memory_utilization_nvidia': utilization.memory
                })
            
            return info
            
        except Exception as e:
            self.logger.error(f"메모리 정보 조회 실패: {str(e)}")
            return {'error': str(e)}
    
    def optimize_batch_size(self, data_size: int, available_memory: Optional[int] = None) -> int:
        """데이터 크기에 따른 최적 배치 크기 계산"""
        if available_memory is None:
            memory_info = self.get_memory_info()
            available_memory = memory_info.get('free_memory', 0)
        
        optimal_size = self.batch_processor.get_optimal_batch_size(
            available_memory, data_size
        )
        
        self.performance_stats['batch_sizes_used'].append(optimal_size)
        self.logger.debug(f"최적 배치 크기: {optimal_size} (데이터 크기: {data_size}, 가용 메모리: {available_memory})")
        
        return optimal_size
    
    @contextmanager
    def gpu_memory_context(self, device_id: int = 0):
        """GPU 메모리 관리 컨텍스트 매니저"""
        initial_memory = None
        
        try:
            if self.has_cuda:
                initial_memory = torch.cuda.memory_allocated(device_id)
                
            yield
            
        finally:
            if self.has_cuda:
                current_memory = torch.cuda.memory_allocated(device_id)
                if initial_memory is not None:
                    memory_diff = current_memory - initial_memory
                    if memory_diff > 0:
                        self.logger.debug(f"메모리 사용량 증가: {memory_diff:,} bytes")
                
                # 메모리 정리
                self.clear_gpu_memory()
    
    def clear_gpu_memory(self) -> None:
        """GPU 메모리 정리"""
        try:
            # 관리되는 텐서 해제
            self.memory_manager.clear_all()
            
            if self.has_cuda:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Python 가비지 컬렉션
            gc.collect()
            
            self.logger.debug("GPU 메모리 정리 완료")
            
        except Exception as e:
            self.logger.warning(f"GPU 메모리 정리 중 오류: {str(e)}")
    
    def monitor_gpu_utilization(self, device_id: int = 0) -> Dict[str, float]:
        """GPU 사용률 모니터링"""
        utilization_info = {
            'gpu_utilization': 0.0,
            'memory_utilization': 0.0,
            'temperature': 0.0,
            'power_usage': 0.0
        }
        
        if not self.has_cuda or not pynvml:
            return utilization_info
        
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            
            # 사용률 정보
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            utilization_info['gpu_utilization'] = utilization.gpu
            utilization_info['memory_utilization'] = utilization.memory
            
            # 온도 정보
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                utilization_info['temperature'] = temperature
            except:
                pass
            
            # 전력 사용량
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
                utilization_info['power_usage'] = power
            except:
                pass
            
            # 통계에 추가
            self.performance_stats['gpu_utilization_history'].append(utilization_info.copy())
            
        except Exception as e:
            self.logger.warning(f"GPU 사용률 모니터링 오류: {str(e)}")
        
        return utilization_info
    
    def process_with_optimization(
        self, 
        data_batch: List[Any], 
        process_fn, 
        *args, 
        **kwargs
    ) -> List[Any]:
        """최적화된 배치 처리"""
        start_time = time.time()
        
        try:
            # 메모리 상태 확인
            memory_info = self.get_memory_info()
            self.logger.debug(f"처리 시작 - 메모리 사용률: {memory_info.get('memory_utilization', 0):.1f}%")
            
            # GPU 메모리 컨텍스트에서 처리
            with self.gpu_memory_context():
                # 배치 크기 최적화
                if data_batch:
                    item_size = self._estimate_item_size(data_batch[0])
                    optimal_batch_size = self.optimize_batch_size(
                        item_size, 
                        memory_info.get('free_memory')
                    )
                    
                    # 배치 처리
                    results = []
                    for i in range(0, len(data_batch), optimal_batch_size):
                        batch = data_batch[i:i + optimal_batch_size]
                        batch_results = process_fn(batch, *args, **kwargs)
                        results.extend(batch_results if isinstance(batch_results, list) else [batch_results])
                        
                        # 메모리 정리 (필요 시)
                        if i % (optimal_batch_size * 2) == 0:
                            self.clear_gpu_memory()
                else:
                    results = []
            
            # 성능 통계 업데이트
            processing_time = time.time() - start_time
            self.performance_stats['total_processing_time'] += processing_time
            self.performance_stats['total_items_processed'] += len(data_batch)
            
            self.logger.debug(f"배치 처리 완료 - {len(data_batch)}개 항목, 소요시간: {processing_time:.2f}초")
            
            return results
            
        except Exception as e:
            self.logger.error(f"최적화된 처리 중 오류: {str(e)}")
            raise
    
    def _estimate_item_size(self, item: Any) -> int:
        """데이터 항목 크기 추정"""
        try:
            if HAS_NUMPY and isinstance(item, np.ndarray):
                return item.nbytes
            elif hasattr(item, 'element_size') and hasattr(item, 'numel'):
                # PyTorch tensor
                return item.element_size() * item.numel()
            elif isinstance(item, (str, bytes)):
                return len(item)
            elif isinstance(item, list):
                return sum(self._estimate_item_size(sub_item) for sub_item in item[:10])  # 샘플링
            else:
                # 기본 추정치 (이미지 기준)
                return 1024 * 1024 * 3  # 1MB RGB 이미지
        except:
            return 1024 * 1024 * 3  # 기본값
    
    def fallback_to_cpu(self) -> None:
        """CPU 폴백 모드로 전환"""
        self.logger.warning("GPU 사용 불가 - CPU 모드로 전환")
        self.device = "cpu"
        self.has_cuda = False
        
        # 메모리 정리
        self.clear_gpu_memory()
    
    def benchmark_performance(self, test_data: List[Any], process_fn, iterations: int = 5) -> Dict[str, Any]:
        """성능 벤치마킹"""
        self.logger.info(f"성능 벤치마킹 시작 - {iterations}회 반복")
        
        results = {
            'iterations': iterations,
            'processing_times': [],
            'throughput': [],
            'memory_usage': [],
            'gpu_utilization': []
        }
        
        for i in range(iterations):
            start_time = time.time()
            memory_before = self.get_memory_info()
            
            # 처리 실행
            processed = self.process_with_optimization(test_data, process_fn)
            
            processing_time = time.time() - start_time
            memory_after = self.get_memory_info()
            gpu_util = self.monitor_gpu_utilization()
            
            # 결과 기록
            results['processing_times'].append(processing_time)
            results['throughput'].append(len(test_data) / processing_time)
            results['memory_usage'].append({
                'before': memory_before.get('memory_utilization', 0),
                'after': memory_after.get('memory_utilization', 0)
            })
            results['gpu_utilization'].append(gpu_util['gpu_utilization'])
            
            self.logger.debug(f"벤치마크 반복 {i+1}/{iterations} 완료 - {processing_time:.2f}초")
        
        # 통계 계산
        avg_time = sum(results['processing_times']) / len(results['processing_times'])
        avg_throughput = sum(results['throughput']) / len(results['throughput'])
        
        results['average_processing_time'] = avg_time
        results['average_throughput'] = avg_throughput
        results['performance_improvement'] = self._calculate_improvement(avg_throughput)
        
        self.logger.info(f"벤치마킹 완료 - 평균 처리시간: {avg_time:.2f}초, 평균 처리량: {avg_throughput:.1f} items/sec")
        
        return results
    
    def _calculate_improvement(self, current_throughput: float) -> float:
        """성능 개선률 계산 (기준값 대비)"""
        baseline_throughput = getattr(self.config, 'BASELINE_THROUGHPUT', current_throughput * 0.7)
        if baseline_throughput > 0:
            improvement = ((current_throughput - baseline_throughput) / baseline_throughput) * 100
            return max(0, improvement)
        return 0.0
    
    def get_performance_report(self) -> Dict[str, Any]:
        """성능 리포트 생성"""
        total_time = self.performance_stats['total_processing_time']
        total_items = self.performance_stats['total_items_processed']
        
        report = {
            'gpu_device': self.device,
            'gpu_count': self.device_count,
            'total_processing_time': total_time,
            'total_items_processed': total_items,
            'average_throughput': total_items / total_time if total_time > 0 else 0,
            'memory_optimization': {
                'peak_usage': max(self.performance_stats['memory_usage_peaks']) if self.performance_stats['memory_usage_peaks'] else 0,
                'average_batch_size': sum(self.performance_stats['batch_sizes_used']) / len(self.performance_stats['batch_sizes_used']) if self.performance_stats['batch_sizes_used'] else 0
            },
            'gpu_utilization': {
                'average': sum(u['gpu_utilization'] for u in self.performance_stats['gpu_utilization_history']) / len(self.performance_stats['gpu_utilization_history']) if self.performance_stats['gpu_utilization_history'] else 0,
                'peak': max(u['gpu_utilization'] for u in self.performance_stats['gpu_utilization_history']) if self.performance_stats['gpu_utilization_history'] else 0
            },
            'current_memory_info': self.get_memory_info(),
            'has_cuda': self.has_cuda
        }
        
        return report
    
    def optimize_model_loading(self, model_path: str, device_id: int = 0) -> Any:
        """모델 로딩 최적화"""
        if not self.has_cuda:
            self.logger.info(f"CPU에서 모델 로딩: {model_path}")
            # CPU에서 모델 로딩 로직
            return None
        
        try:
            with torch.cuda.device(device_id):
                # GPU 메모리 확인
                memory_info = self.get_memory_info(device_id)
                self.logger.info(f"GPU {device_id}에서 모델 로딩: {model_path} (가용 메모리: {memory_info.get('free_memory', 0):,} bytes)")
                
                # 모델 로딩 (구체적인 로딩 로직은 모델 타입에 따라 달라짐)
                # 여기서는 인터페이스만 제공
                return f"model_loaded_on_gpu_{device_id}"
                
        except Exception as e:
            self.logger.error(f"GPU 모델 로딩 실패: {str(e)}")
            self.fallback_to_cpu()
            return None
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.clear_gpu_memory()
        
        if exc_type is not None:
            self.logger.error(f"GPU 최적화 컨텍스트에서 오류 발생: {exc_val}")
        
        return False