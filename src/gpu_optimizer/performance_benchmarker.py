"""
성능 벤치마킹 도구

GPU 최적화 시스템의 성능을 측정하고 비교하는 도구입니다.
"""

import time
import logging
import statistics
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
from contextlib import contextmanager
import psutil

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

from config.config import Config
from .gpu_optimizer import GPUOptimizer


@dataclass
class BenchmarkResult:
    """벤치마크 결과 데이터 클래스"""
    test_name: str
    iterations: int
    total_items: int
    processing_times: List[float]
    throughput_rates: List[float]
    memory_usage: List[Dict[str, float]]
    gpu_utilization: List[float]
    cpu_utilization: List[float]
    
    @property
    def avg_processing_time(self) -> float:
        """평균 처리 시간"""
        return statistics.mean(self.processing_times) if self.processing_times else 0.0
    
    @property
    def avg_throughput(self) -> float:
        """평균 처리량"""
        return statistics.mean(self.throughput_rates) if self.throughput_rates else 0.0
    
    @property
    def throughput_std(self) -> float:
        """처리량 표준편차"""
        return statistics.stdev(self.throughput_rates) if len(self.throughput_rates) > 1 else 0.0
    
    @property
    def avg_memory_usage(self) -> float:
        """평균 메모리 사용률"""
        if not self.memory_usage:
            return 0.0
        memory_values = [usage.get('memory_utilization', 0) for usage in self.memory_usage]
        return statistics.mean(memory_values)
    
    @property
    def avg_gpu_utilization(self) -> float:
        """평균 GPU 사용률"""
        return statistics.mean(self.gpu_utilization) if self.gpu_utilization else 0.0


class PerformanceBenchmarker:
    """성능 벤치마킹 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        벤치마커 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        self.gpu_optimizer = None
        self.baseline_results = {}
        
        # 시스템 정보 수집
        self.system_info = self._collect_system_info()
        
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
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """시스템 정보 수집"""
        info = {
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'platform': psutil.os.name,
        }
        
        # GPU 정보 (가능한 경우)
        try:
            import torch
            if torch.cuda.is_available():
                info['gpu_count'] = torch.cuda.device_count()
                info['gpu_name'] = torch.cuda.get_device_name(0)
                info['gpu_memory'] = torch.cuda.get_device_properties(0).total_memory
            else:
                info['gpu_available'] = False
        except ImportError:
            info['gpu_available'] = False
        
        return info
    
    @contextmanager
    def _performance_monitor(self, gpu_optimizer: Optional[GPUOptimizer] = None):
        """성능 모니터링 컨텍스트"""
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        start_memory = psutil.virtual_memory().percent
        
        gpu_util_start = 0.0
        if gpu_optimizer and gpu_optimizer.has_cuda:
            gpu_util_start = gpu_optimizer.monitor_gpu_utilization().get('gpu_utilization', 0.0)
        
        try:
            yield
        finally:
            end_time = time.time()
            end_cpu = psutil.cpu_percent()
            end_memory = psutil.virtual_memory().percent
            
            gpu_util_end = 0.0
            if gpu_optimizer and gpu_optimizer.has_cuda:
                gpu_util_end = gpu_optimizer.monitor_gpu_utilization().get('gpu_utilization', 0.0)
            
            # 모니터링 결과를 저장할 위치가 필요하다면 여기서 처리
    
    def benchmark_processing_function(
        self,
        process_fn: Callable,
        test_data: List[Any],
        test_name: str = "benchmark_test",
        iterations: int = 5,
        use_gpu_optimization: bool = True
    ) -> BenchmarkResult:
        """
        처리 함수 벤치마킹
        
        Args:
            process_fn: 벤치마킹할 처리 함수
            test_data: 테스트 데이터
            test_name: 테스트 이름
            iterations: 반복 횟수
            use_gpu_optimization: GPU 최적화 사용 여부
            
        Returns:
            벤치마크 결과
        """
        self.logger.info(f"벤치마킹 시작: {test_name} (반복: {iterations}회)")
        
        # GPU 최적화 설정
        gpu_optimizer = None
        if use_gpu_optimization:
            try:
                gpu_optimizer = GPUOptimizer(self.config)
                self.logger.info("GPU 최적화 모드로 벤치마킹")
            except Exception as e:
                self.logger.warning(f"GPU 최적화 초기화 실패: {str(e)}")
        
        # 결과 저장을 위한 리스트
        processing_times = []
        throughput_rates = []
        memory_usage = []
        gpu_utilization = []
        cpu_utilization = []
        
        # 웜업 실행 (결과에 포함하지 않음)
        self.logger.debug("웜업 실행 중...")
        try:
            if gpu_optimizer:
                gpu_optimizer.process_with_optimization(test_data[:2], process_fn)
            else:
                process_fn(test_data[:2])
        except Exception as e:
            self.logger.warning(f"웜업 실행 실패: {str(e)}")
        
        # 벤치마킹 실행
        for i in range(iterations):
            self.logger.debug(f"벤치마킹 반복 {i+1}/{iterations}")
            
            # 시작 시점 메트릭 수집
            start_time = time.time()
            start_cpu = psutil.cpu_percent(interval=None)
            
            if gpu_optimizer:
                start_memory = gpu_optimizer.get_memory_info()
                start_gpu_util = gpu_optimizer.monitor_gpu_utilization()
            else:
                start_memory = {'memory_utilization': psutil.virtual_memory().percent}
                start_gpu_util = {'gpu_utilization': 0.0}
            
            try:
                # 처리 실행
                if gpu_optimizer:
                    results = gpu_optimizer.process_with_optimization(test_data, process_fn)
                else:
                    results = process_fn(test_data)
                
                # 종료 시점 메트릭 수집
                end_time = time.time()
                end_cpu = psutil.cpu_percent(interval=None)
                
                if gpu_optimizer:
                    end_memory = gpu_optimizer.get_memory_info()
                    end_gpu_util = gpu_optimizer.monitor_gpu_utilization()
                else:
                    end_memory = {'memory_utilization': psutil.virtual_memory().percent}
                    end_gpu_util = {'gpu_utilization': 0.0}
                
                # 결과 계산
                processing_time = end_time - start_time
                throughput = len(test_data) / processing_time if processing_time > 0 else 0.0
                
                # 결과 저장
                processing_times.append(processing_time)
                throughput_rates.append(throughput)
                memory_usage.append({
                    'start': start_memory.get('memory_utilization', 0),
                    'end': end_memory.get('memory_utilization', 0),
                    'memory_utilization': end_memory.get('memory_utilization', 0)
                })
                gpu_utilization.append(end_gpu_util.get('gpu_utilization', 0.0))
                cpu_utilization.append(max(start_cpu, end_cpu))
                
                self.logger.debug(f"반복 {i+1} 완료 - 처리시간: {processing_time:.3f}s, 처리량: {throughput:.1f} items/s")
                
            except Exception as e:
                self.logger.error(f"벤치마킹 반복 {i+1} 실패: {str(e)}")
                # 실패한 반복은 기본값으로 처리
                processing_times.append(float('inf'))
                throughput_rates.append(0.0)
                memory_usage.append({'memory_utilization': 0})
                gpu_utilization.append(0.0)
                cpu_utilization.append(0.0)
        
        # 결과 객체 생성
        result = BenchmarkResult(
            test_name=test_name,
            iterations=iterations,
            total_items=len(test_data),
            processing_times=processing_times,
            throughput_rates=throughput_rates,
            memory_usage=memory_usage,
            gpu_utilization=gpu_utilization,
            cpu_utilization=cpu_utilization
        )
        
        self.logger.info(f"벤치마킹 완료: {test_name}")
        self.logger.info(f"평균 처리시간: {result.avg_processing_time:.3f}s")
        self.logger.info(f"평균 처리량: {result.avg_throughput:.1f} items/s")
        
        return result
    
    def compare_optimization_modes(
        self,
        process_fn: Callable,
        test_data: List[Any],
        iterations: int = 5
    ) -> Dict[str, BenchmarkResult]:
        """
        GPU 최적화 모드와 일반 모드 비교
        
        Args:
            process_fn: 처리 함수
            test_data: 테스트 데이터
            iterations: 반복 횟수
            
        Returns:
            모드별 벤치마크 결과
        """
        self.logger.info("GPU 최적화 모드 vs 일반 모드 비교 벤치마킹 시작")
        
        results = {}
        
        # 일반 모드 (GPU 최적화 없음)
        results['normal'] = self.benchmark_processing_function(
            process_fn, test_data, "Normal Mode", iterations, use_gpu_optimization=False
        )
        
        # GPU 최적화 모드
        results['optimized'] = self.benchmark_processing_function(
            process_fn, test_data, "GPU Optimized Mode", iterations, use_gpu_optimization=True
        )
        
        # 비교 결과 출력
        self._print_comparison_results(results)
        
        return results
    
    def _print_comparison_results(self, results: Dict[str, BenchmarkResult]) -> None:
        """비교 결과 출력"""
        if 'normal' not in results or 'optimized' not in results:
            return
        
        normal = results['normal']
        optimized = results['optimized']
        
        self.logger.info("\n=== 성능 비교 결과 ===")
        self.logger.info(f"{'모드':<15} {'처리시간(s)':<12} {'처리량(items/s)':<15} {'GPU 사용률(%)':<12} {'메모리 사용률(%)':<15}")
        self.logger.info("-" * 80)
        self.logger.info(f"{'일반 모드':<15} {normal.avg_processing_time:<12.3f} {normal.avg_throughput:<15.1f} {normal.avg_gpu_utilization:<12.1f} {normal.avg_memory_usage:<15.1f}")
        self.logger.info(f"{'최적화 모드':<15} {optimized.avg_processing_time:<12.3f} {optimized.avg_throughput:<15.1f} {optimized.avg_gpu_utilization:<12.1f} {optimized.avg_memory_usage:<15.1f}")
        
        # 개선률 계산
        if normal.avg_processing_time > 0:
            time_improvement = ((normal.avg_processing_time - optimized.avg_processing_time) / normal.avg_processing_time) * 100
            throughput_improvement = ((optimized.avg_throughput - normal.avg_throughput) / normal.avg_throughput) * 100 if normal.avg_throughput > 0 else 0
            
            self.logger.info("\n=== 개선률 ===")
            self.logger.info(f"처리시간 개선: {time_improvement:+.1f}%")
            self.logger.info(f"처리량 개선: {throughput_improvement:+.1f}%")
            
            # 목표 달성 여부 확인
            target_improvement = 30.0  # 30% 개선 목표
            if throughput_improvement >= target_improvement:
                self.logger.info(f"✅ 목표 달성: {throughput_improvement:.1f}% >= {target_improvement}%")
            else:
                self.logger.warning(f"❌ 목표 미달성: {throughput_improvement:.1f}% < {target_improvement}%")
    
    def benchmark_batch_sizes(
        self,
        process_fn: Callable,
        test_data: List[Any],
        batch_sizes: List[int] = None
    ) -> Dict[int, BenchmarkResult]:
        """
        다양한 배치 크기별 성능 벤치마킹
        
        Args:
            process_fn: 처리 함수
            test_data: 테스트 데이터
            batch_sizes: 테스트할 배치 크기 리스트
            
        Returns:
            배치 크기별 벤치마크 결과
        """
        if batch_sizes is None:
            batch_sizes = [1, 2, 4, 8, 16, 32]
        
        self.logger.info(f"배치 크기별 성능 벤치마킹 시작: {batch_sizes}")
        
        results = {}
        
        for batch_size in batch_sizes:
            self.logger.info(f"배치 크기 {batch_size} 테스트 중...")
            
            # 임시 설정으로 배치 크기 변경
            original_batch_size = getattr(self.config, 'GPU_BATCH_SIZE', 8)
            self.config.GPU_BATCH_SIZE = batch_size
            
            try:
                result = self.benchmark_processing_function(
                    process_fn, test_data, f"Batch Size {batch_size}", iterations=3
                )
                results[batch_size] = result
                
            except Exception as e:
                self.logger.error(f"배치 크기 {batch_size} 테스트 실패: {str(e)}")
                
            finally:
                # 원래 배치 크기 복원
                self.config.GPU_BATCH_SIZE = original_batch_size
        
        # 최적 배치 크기 찾기
        self._find_optimal_batch_size(results)
        
        return results
    
    def _find_optimal_batch_size(self, results: Dict[int, BenchmarkResult]) -> None:
        """최적 배치 크기 찾기"""
        if not results:
            return
        
        best_batch_size = max(results.keys(), key=lambda k: results[k].avg_throughput)
        best_result = results[best_batch_size]
        
        self.logger.info("\n=== 배치 크기별 성능 결과 ===")
        self.logger.info(f"{'배치 크기':<10} {'처리량(items/s)':<15} {'처리시간(s)':<12} {'메모리 사용률(%)':<15}")
        self.logger.info("-" * 60)
        
        for batch_size in sorted(results.keys()):
            result = results[batch_size]
            marker = " ⭐" if batch_size == best_batch_size else ""
            self.logger.info(f"{batch_size:<10} {result.avg_throughput:<15.1f} {result.avg_processing_time:<12.3f} {result.avg_memory_usage:<15.1f}{marker}")
        
        self.logger.info(f"\n🏆 최적 배치 크기: {best_batch_size} (처리량: {best_result.avg_throughput:.1f} items/s)")
    
    def benchmark_memory_efficiency(
        self,
        process_fn: Callable,
        data_sizes: List[int] = None
    ) -> Dict[int, BenchmarkResult]:
        """
        메모리 효율성 벤치마킹
        
        Args:
            process_fn: 처리 함수
            data_sizes: 테스트할 데이터 크기 리스트
            
        Returns:
            데이터 크기별 벤치마크 결과
        """
        if data_sizes is None:
            data_sizes = [10, 50, 100, 200, 500]
        
        self.logger.info(f"메모리 효율성 벤치마킹 시작: {data_sizes}")
        
        results = {}
        
        for size in data_sizes:
            # 테스트 데이터 생성
            test_data = [f"test_item_{i}" for i in range(size)]
            
            self.logger.info(f"데이터 크기 {size} 테스트 중...")
            
            try:
                result = self.benchmark_processing_function(
                    process_fn, test_data, f"Data Size {size}", iterations=3
                )
                results[size] = result
                
            except Exception as e:
                self.logger.error(f"데이터 크기 {size} 테스트 실패: {str(e)}")
        
        # 메모리 효율성 분석
        self._analyze_memory_efficiency(results)
        
        return results
    
    def _analyze_memory_efficiency(self, results: Dict[int, BenchmarkResult]) -> None:
        """메모리 효율성 분석"""
        if not results:
            return
        
        self.logger.info("\n=== 메모리 효율성 분석 ===")
        self.logger.info(f"{'데이터 크기':<12} {'처리량(items/s)':<15} {'메모리 사용률(%)':<15} {'효율성 지수':<12}")
        self.logger.info("-" * 60)
        
        for size in sorted(results.keys()):
            result = results[size]
            # 효율성 지수 = 처리량 / 메모리 사용률
            efficiency = result.avg_throughput / max(result.avg_memory_usage, 1.0)
            
            self.logger.info(f"{size:<12} {result.avg_throughput:<15.1f} {result.avg_memory_usage:<15.1f} {efficiency:<12.2f}")
    
    def generate_report(self, results: Dict[str, BenchmarkResult]) -> Dict[str, Any]:
        """
        종합 성능 리포트 생성
        
        Args:
            results: 벤치마크 결과들
            
        Returns:
            종합 리포트
        """
        report = {
            'system_info': self.system_info,
            'timestamp': time.time(),
            'results_summary': {},
            'performance_metrics': {},
            'recommendations': []
        }
        
        # 결과 요약
        for test_name, result in results.items():
            report['results_summary'][test_name] = {
                'avg_processing_time': result.avg_processing_time,
                'avg_throughput': result.avg_throughput,
                'throughput_std': result.throughput_std,
                'avg_memory_usage': result.avg_memory_usage,
                'avg_gpu_utilization': result.avg_gpu_utilization
            }
        
        # 성능 메트릭 계산
        if 'optimized' in results and 'normal' in results:
            optimized = results['optimized']
            normal = results['normal']
            
            if normal.avg_throughput > 0:
                improvement = ((optimized.avg_throughput - normal.avg_throughput) / normal.avg_throughput) * 100
                report['performance_metrics']['throughput_improvement'] = improvement
                report['performance_metrics']['meets_target'] = improvement >= 30.0
        
        # 추천사항 생성
        report['recommendations'] = self._generate_recommendations(results)
        
        return report
    
    def _generate_recommendations(self, results: Dict[str, BenchmarkResult]) -> List[str]:
        """성능 개선 추천사항 생성"""
        recommendations = []
        
        for test_name, result in results.items():
            # GPU 사용률이 낮은 경우
            if result.avg_gpu_utilization < 30.0:
                recommendations.append(f"{test_name}: GPU 사용률이 낮습니다 ({result.avg_gpu_utilization:.1f}%). 배치 크기를 늘리거나 GPU 활용도를 높이는 방안을 검토하세요.")
            
            # 메모리 사용률이 높은 경우
            if result.avg_memory_usage > 80.0:
                recommendations.append(f"{test_name}: 메모리 사용률이 높습니다 ({result.avg_memory_usage:.1f}%). 배치 크기를 줄이거나 메모리 최적화를 검토하세요.")
            
            # 처리량 변동이 큰 경우
            if result.throughput_std > result.avg_throughput * 0.2:
                recommendations.append(f"{test_name}: 처리량 변동이 큽니다 (표준편차: {result.throughput_std:.1f}). 시스템 안정성을 검토하세요.")
        
        if not recommendations:
            recommendations.append("시스템이 안정적으로 동작하고 있습니다.")
        
        return recommendations


def create_test_process_function() -> Callable:
    """테스트용 처리 함수 생성"""
    def test_process(data_batch):
        """간단한 테스트 처리 함수"""
        # 실제 처리 시뮬레이션
        time.sleep(0.001 * len(data_batch))  # 1ms per item
        return [f"processed_{item}" for item in data_batch]
    
    return test_process


if __name__ == "__main__":
    # 벤치마킹 예제 실행
    config = Config()
    benchmarker = PerformanceBenchmarker(config)
    
    # 테스트 데이터 생성
    test_data = [f"test_item_{i}" for i in range(50)]
    process_fn = create_test_process_function()
    
    # 비교 벤치마킹 실행
    results = benchmarker.compare_optimization_modes(process_fn, test_data)
    
    # 리포트 생성
    report = benchmarker.generate_report(results)
    print(f"\n성능 개선률: {report['performance_metrics'].get('throughput_improvement', 0):.1f}%")
    print(f"목표 달성: {'✅' if report['performance_metrics'].get('meets_target', False) else '❌'}")