"""
GPU 최적화 시스템 테스트

GPU 최적화 클래스의 기능과 성능을 검증합니다.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.gpu_optimizer.gpu_optimizer import GPUOptimizer, GPUMemoryManager, GPUBatchProcessor
from config.config import Config


class TestGPUMemoryManager:
    """GPU 메모리 관리자 테스트"""
    
    def test_memory_manager_initialization(self):
        """메모리 관리자 초기화 테스트"""
        manager = GPUMemoryManager()
        
        assert manager.allocated_tensors == []
        assert manager.memory_lock is not None
    
    def test_tensor_allocation_tracking(self):
        """텐서 할당 추적 테스트"""
        manager = GPUMemoryManager()
        mock_tensor = Mock()
        
        manager.allocate_tensor(mock_tensor)
        assert mock_tensor in manager.allocated_tensors
        
        manager.deallocate_tensor(mock_tensor)
        assert mock_tensor not in manager.allocated_tensors
    
    def test_clear_all_tensors(self):
        """모든 텐서 해제 테스트"""
        manager = GPUMemoryManager()
        mock_tensors = [Mock() for _ in range(3)]
        
        for tensor in mock_tensors:
            manager.allocate_tensor(tensor)
        
        assert len(manager.allocated_tensors) == 3
        
        manager.clear_all()
        assert len(manager.allocated_tensors) == 0


class TestGPUBatchProcessor:
    """GPU 배치 처리기 테스트"""
    
    def test_batch_processor_initialization(self):
        """배치 처리기 초기화 테스트"""
        processor = GPUBatchProcessor(device="cpu", batch_size=4)
        
        assert processor.device == "cpu"
        assert processor.batch_size == 4
        assert processor.processing_queue == []
    
    def test_add_to_batch(self):
        """배치에 데이터 추가 테스트"""
        processor = GPUBatchProcessor()
        test_data = ["item1", "item2", "item3"]
        
        for item in test_data:
            processor.add_to_batch(item)
        
        assert processor.processing_queue == test_data
    
    def test_process_batch(self):
        """배치 처리 테스트"""
        processor = GPUBatchProcessor(batch_size=2)
        test_data = ["a", "b", "c", "d"]
        
        for item in test_data:
            processor.add_to_batch(item)
        
        def mock_process_fn(batch):
            return [item.upper() for item in batch]
        
        results = processor.process_batch(mock_process_fn)
        
        assert results == ["A", "B", "C", "D"]
        assert processor.processing_queue == []
    
    def test_optimal_batch_size_calculation(self):
        """최적 배치 크기 계산 테스트"""
        processor = GPUBatchProcessor(batch_size=10)
        
        # 메모리가 충분한 경우
        optimal_size = processor.get_optimal_batch_size(1000000, 100000)
        assert optimal_size <= processor.batch_size
        assert optimal_size > 0
        
        # 메모리가 부족한 경우
        optimal_size = processor.get_optimal_batch_size(1000, 10000)
        assert optimal_size == 1
        
        # 비정상적인 입력
        optimal_size = processor.get_optimal_batch_size(0, 100)
        assert optimal_size == 1


class TestGPUOptimizer:
    """GPU 최적화 클래스 테스트"""
    
    @pytest.fixture
    def config(self):
        """테스트용 설정 객체"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'DEBUG'
        config.GPU_BATCH_SIZE = 4
        config.GPU_MEMORY_FRACTION = 0.8
        config.ENABLE_GPU_OPTIMIZATION = True
        config.AUTO_BATCH_SIZE = True
        config.BASELINE_THROUGHPUT = 5.0
        return config
    
    @pytest.fixture
    def gpu_optimizer(self, config):
        """GPU 최적화 인스턴스"""
        return GPUOptimizer(config)
    
    def test_optimizer_initialization(self, gpu_optimizer):
        """GPU 최적화 초기화 테스트"""
        assert gpu_optimizer.config is not None
        assert gpu_optimizer.logger is not None
        assert gpu_optimizer.memory_manager is not None
        assert gpu_optimizer.batch_processor is not None
        assert gpu_optimizer.performance_stats is not None
        assert gpu_optimizer.device in ["cuda", "cpu"]
    
    def test_device_detection(self, gpu_optimizer):
        """디바이스 감지 테스트"""
        device = gpu_optimizer._detect_device()
        assert device in ["cuda", "cpu"]
    
    def test_memory_info_cpu_mode(self, gpu_optimizer):
        """CPU 모드 메모리 정보 테스트"""
        # CPU 모드로 강제 설정
        gpu_optimizer.has_cuda = False
        
        memory_info = gpu_optimizer.get_memory_info()
        
        assert 'device' in memory_info
        assert memory_info['device'] == 'cpu'
        assert 'total_memory' in memory_info
        assert 'available_memory' in memory_info
        assert 'used_memory' in memory_info
        assert 'memory_utilization' in memory_info
    
    @patch('src.gpu_optimizer.gpu_optimizer.torch')
    def test_memory_info_cuda_mode(self, mock_torch, gpu_optimizer):
        """CUDA 모드 메모리 정보 테스트"""
        # Mock CUDA 환경 설정
        gpu_optimizer.has_cuda = True
        mock_torch.cuda.get_device_properties.return_value.total_memory = 8000000000
        mock_torch.cuda.memory_allocated.return_value = 2000000000
        mock_torch.cuda.memory_reserved.return_value = 2500000000
        
        memory_info = gpu_optimizer.get_memory_info()
        
        assert memory_info['device'] == 'cuda:0'
        assert memory_info['total_memory'] == 8000000000
        assert memory_info['allocated_memory'] == 2000000000
        assert memory_info['free_memory'] == 6000000000
    
    def test_batch_size_optimization(self, gpu_optimizer):
        """배치 크기 최적화 테스트"""
        # 메모리 정보 Mock
        gpu_optimizer.get_memory_info = Mock(return_value={'free_memory': 1000000})
        
        optimal_size = gpu_optimizer.optimize_batch_size(100000)
        
        assert optimal_size > 0
        assert optimal_size <= gpu_optimizer.batch_processor.batch_size
        assert len(gpu_optimizer.performance_stats['batch_sizes_used']) > 0
    
    def test_memory_context_manager(self, gpu_optimizer):
        """메모리 컨텍스트 매니저 테스트"""
        # Mock CUDA 메서드
        gpu_optimizer.has_cuda = True
        gpu_optimizer.clear_gpu_memory = Mock()
        
        with patch('src.gpu_optimizer.gpu_optimizer.torch') as mock_torch:
            mock_torch.cuda.memory_allocated.return_value = 1000000
            
            with gpu_optimizer.gpu_memory_context():
                pass
            
            # 메모리 정리가 호출되었는지 확인
            gpu_optimizer.clear_gpu_memory.assert_called()
    
    def test_clear_gpu_memory(self, gpu_optimizer):
        """GPU 메모리 정리 테스트"""
        gpu_optimizer.memory_manager.clear_all = Mock()
        
        # GPU 모드에서 테스트
        gpu_optimizer.has_cuda = True
        with patch('src.gpu_optimizer.gpu_optimizer.torch') as mock_torch:
            gpu_optimizer.clear_gpu_memory()
            
            gpu_optimizer.memory_manager.clear_all.assert_called_once()
            mock_torch.cuda.empty_cache.assert_called_once()
            mock_torch.cuda.synchronize.assert_called_once()
    
    def test_optimized_processing(self, gpu_optimizer):
        """최적화된 처리 테스트"""
        test_data = ["item1", "item2", "item3", "item4"]
        
        def mock_process_fn(batch):
            return [item.upper() for item in batch]
        
        # 메모리 정보 Mock
        gpu_optimizer.get_memory_info = Mock(return_value={
            'free_memory': 1000000,
            'memory_utilization': 50.0
        })
        
        results = gpu_optimizer.process_with_optimization(test_data, mock_process_fn)
        
        assert len(results) == len(test_data)
        assert all(result.isupper() for result in results)
        assert gpu_optimizer.performance_stats['total_items_processed'] >= len(test_data)
    
    def test_fallback_to_cpu(self, gpu_optimizer):
        """CPU 폴백 테스트"""
        original_device = gpu_optimizer.device
        
        gpu_optimizer.fallback_to_cpu()
        
        assert gpu_optimizer.device == "cpu"
        assert gpu_optimizer.has_cuda == False
    
    def test_item_size_estimation(self, gpu_optimizer):
        """데이터 항목 크기 추정 테스트"""
        # 문자열 테스트
        string_size = gpu_optimizer._estimate_item_size("test string")
        assert string_size == len("test string")
        
        # 리스트 테스트
        list_data = ["item1", "item2", "item3"]
        list_size = gpu_optimizer._estimate_item_size(list_data)
        assert list_size > 0
        
        # 알 수 없는 타입 테스트
        unknown_size = gpu_optimizer._estimate_item_size(object())
        assert unknown_size == 1024 * 1024 * 3  # 기본값
    
    def test_performance_improvement_calculation(self, gpu_optimizer):
        """성능 개선률 계산 테스트"""
        # 기준값보다 높은 처리량
        improvement = gpu_optimizer._calculate_improvement(10.0)
        assert improvement >= 0
        
        # 기준값보다 낮은 처리량
        improvement = gpu_optimizer._calculate_improvement(3.0)
        assert improvement == 0.0  # 음수 개선률은 0으로 설정
    
    def test_benchmark_performance(self, gpu_optimizer):
        """성능 벤치마킹 테스트"""
        test_data = ["item1", "item2"]
        
        def mock_process_fn(batch):
            time.sleep(0.01)  # 처리 시간 시뮬레이션
            return [item.upper() for item in batch]
        
        # 메모리 정보 Mock
        gpu_optimizer.get_memory_info = Mock(return_value={
            'free_memory': 1000000,
            'memory_utilization': 30.0
        })
        gpu_optimizer.monitor_gpu_utilization = Mock(return_value={
            'gpu_utilization': 50.0
        })
        
        results = gpu_optimizer.benchmark_performance(test_data, mock_process_fn, iterations=2)
        
        assert 'iterations' in results
        assert results['iterations'] == 2
        assert 'processing_times' in results
        assert len(results['processing_times']) == 2
        assert 'average_processing_time' in results
        assert 'average_throughput' in results
        assert 'performance_improvement' in results
    
    def test_performance_report(self, gpu_optimizer):
        """성능 리포트 생성 테스트"""
        # 일부 통계 데이터 추가
        gpu_optimizer.performance_stats['total_processing_time'] = 10.0
        gpu_optimizer.performance_stats['total_items_processed'] = 100
        gpu_optimizer.performance_stats['batch_sizes_used'] = [4, 6, 8]
        gpu_optimizer.performance_stats['gpu_utilization_history'] = [
            {'gpu_utilization': 70.0},
            {'gpu_utilization': 80.0}
        ]
        
        # 메모리 정보 Mock
        gpu_optimizer.get_memory_info = Mock(return_value={
            'memory_utilization': 60.0
        })
        
        report = gpu_optimizer.get_performance_report()
        
        assert 'gpu_device' in report
        assert 'total_processing_time' in report
        assert 'total_items_processed' in report
        assert 'average_throughput' in report
        assert 'memory_optimization' in report
        assert 'gpu_utilization' in report
        assert 'current_memory_info' in report
        
        # 처리량 계산 검증
        expected_throughput = 100 / 10.0
        assert report['average_throughput'] == expected_throughput
    
    def test_context_manager_usage(self, gpu_optimizer):
        """컨텍스트 매니저 사용 테스트"""
        gpu_optimizer.clear_gpu_memory = Mock()
        
        with gpu_optimizer:
            pass
        
        # 종료 시 메모리 정리가 호출되는지 확인
        gpu_optimizer.clear_gpu_memory.assert_called_once()
    
    def test_context_manager_with_exception(self, gpu_optimizer):
        """예외 발생 시 컨텍스트 매니저 테스트"""
        gpu_optimizer.clear_gpu_memory = Mock()
        
        try:
            with gpu_optimizer:
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # 예외 발생 후에도 메모리 정리가 호출되는지 확인
        gpu_optimizer.clear_gpu_memory.assert_called_once()
    
    @patch('src.gpu_optimizer.gpu_optimizer.pynvml')
    def test_gpu_utilization_monitoring(self, mock_pynvml, gpu_optimizer):
        """GPU 사용률 모니터링 테스트"""
        # CUDA 모드로 설정
        gpu_optimizer.has_cuda = True
        
        # pynvml Mock 설정
        mock_handle = Mock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        
        mock_utilization = Mock()
        mock_utilization.gpu = 75.0
        mock_utilization.memory = 80.0
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 65.0
        mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 150000  # mW
        
        utilization = gpu_optimizer.monitor_gpu_utilization()
        
        assert utilization['gpu_utilization'] == 75.0
        assert utilization['memory_utilization'] == 80.0
        assert utilization['temperature'] == 65.0
        assert utilization['power_usage'] == 150.0  # W로 변환
        
        # 통계에 추가되었는지 확인
        assert len(gpu_optimizer.performance_stats['gpu_utilization_history']) > 0


class TestGPUOptimizationIntegration:
    """GPU 최적화 통합 테스트"""
    
    def test_end_to_end_optimization(self):
        """전체 최적화 워크플로우 테스트"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'INFO'
        config.GPU_BATCH_SIZE = 2
        config.ENABLE_GPU_OPTIMIZATION = True
        
        optimizer = GPUOptimizer(config)
        
        # 테스트 데이터 준비
        test_data = ["data1", "data2", "data3", "data4"]
        
        def process_function(batch):
            # 간단한 처리 시뮬레이션
            return [f"processed_{item}" for item in batch]
        
        # 처리 실행
        results = optimizer.process_with_optimization(test_data, process_function)
        
        # 결과 검증
        assert len(results) == len(test_data)
        assert all("processed_" in result for result in results)
        
        # 성능 통계 검증
        assert optimizer.performance_stats['total_items_processed'] >= len(test_data)
        assert optimizer.performance_stats['total_processing_time'] > 0
        
        # 성능 리포트 생성
        report = optimizer.get_performance_report()
        assert report['average_throughput'] > 0
    
    def test_memory_pressure_handling(self):
        """메모리 압박 상황 처리 테스트"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'INFO'
        config.GPU_BATCH_SIZE = 10
        config.ENABLE_GPU_OPTIMIZATION = True
        
        optimizer = GPUOptimizer(config)
        
        # 메모리 부족 상황 시뮬레이션
        optimizer.get_memory_info = Mock(return_value={'free_memory': 1000})  # 매우 적은 메모리
        
        # 큰 데이터 세트
        large_data = [f"large_item_{i}" for i in range(20)]
        
        def memory_intensive_process(batch):
            return [f"heavy_processed_{item}" for item in batch]
        
        # 처리가 실패하지 않고 완료되어야 함
        results = optimizer.process_with_optimization(large_data, memory_intensive_process)
        assert len(results) == len(large_data)
    
    def test_gpu_fallback_scenario(self):
        """GPU 실패 시 CPU 폴백 시나리오 테스트"""
        config = Mock(spec=Config)
        config.LOG_LEVEL = 'INFO'
        config.ENABLE_GPU_OPTIMIZATION = True
        
        optimizer = GPUOptimizer(config)
        
        # GPU 처리 실패 시뮬레이션
        def failing_gpu_process(batch):
            raise RuntimeError("GPU processing failed")
        
        test_data = ["item1", "item2"]
        
        # CPU 폴백이 정상 작동해야 함
        optimizer.fallback_to_cpu()
        assert optimizer.device == "cpu"
        assert optimizer.has_cuda == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])