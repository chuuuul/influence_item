"""
실시간 비동기 처리 파이프라인

GPU 클러스터 최적화와 비동기 처리를 통해 실시간 처리 능력을 극대화하는
고성능 AI 파이프라인입니다.
"""

import asyncio
import logging
import time
import json
import uuid
import weakref
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from queue import Queue, Empty
import threading
import multiprocessing as mp
from collections import defaultdict, deque
import psutil
import gc

try:
    import torch
    import torch.multiprocessing as torch_mp
    import torch.distributed as dist
    HAS_TORCH = True
except ImportError:
    torch = None
    torch_mp = None
    dist = None
    HAS_TORCH = False

try:
    import uvloop
    HAS_UVLOOP = True
except ImportError:
    uvloop = None
    HAS_UVLOOP = False

from config.config import Config
from ..gpu_optimizer.gpu_optimizer import GPUOptimizer
from ..ai_fusion.cross_attention_fusion import CrossAttentionFusionEngine


@dataclass
class ProcessingTask:
    """처리 작업 정의"""
    task_id: str
    data: Any
    task_type: str  # 'audio', 'visual', 'fusion', 'inference'
    priority: int = 1  # 1-10, 높을수록 우선순위 높음
    timestamp: float = field(default_factory=time.time)
    dependencies: List[str] = field(default_factory=list)
    callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ProcessingResult:
    """처리 결과"""
    task_id: str
    result: Any
    processing_time: float
    gpu_id: Optional[int] = None
    worker_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskScheduler:
    """작업 스케줄러 (우선순위 기반)"""
    
    def __init__(self, max_queue_size: int = 10000):
        self.task_queues = {
            priority: asyncio.Queue(maxsize=max_queue_size // 10)
            for priority in range(1, 11)
        }
        self.pending_tasks = {}  # task_id -> task
        self.completed_tasks = {}  # task_id -> result
        self.task_dependencies = defaultdict(set)  # task_id -> {dependency_ids}
        self.dependency_waiters = defaultdict(list)  # task_id -> [waiting_task_ids]
        self.stats = {
            'total_scheduled': 0,
            'total_completed': 0,
            'average_wait_time': 0.0,
            'queue_depths': defaultdict(int)
        }
        self.logger = logging.getLogger(__name__)
    
    async def schedule_task(self, task: ProcessingTask) -> None:
        """작업 스케줄링"""
        try:
            self.pending_tasks[task.task_id] = task
            
            # 의존성 확인
            if task.dependencies:
                unresolved_deps = [
                    dep for dep in task.dependencies 
                    if dep not in self.completed_tasks
                ]
                
                if unresolved_deps:
                    # 의존성이 해결될 때까지 대기
                    for dep in unresolved_deps:
                        self.dependency_waiters[dep].append(task.task_id)
                    self.logger.debug(f"작업 {task.task_id} 의존성 대기: {unresolved_deps}")
                    return
            
            # 우선순위 큐에 추가
            await self.task_queues[task.priority].put(task)
            self.stats['total_scheduled'] += 1
            self.stats['queue_depths'][task.priority] += 1
            
            self.logger.debug(f"작업 스케줄링 완료: {task.task_id} (우선순위: {task.priority})")
            
        except Exception as e:
            self.logger.error(f"작업 스케줄링 실패: {str(e)}")
    
    async def get_next_task(self) -> Optional[ProcessingTask]:
        """다음 작업 가져오기 (우선순위 순)"""
        # 높은 우선순위부터 확인
        for priority in range(10, 0, -1):
            try:
                task = await asyncio.wait_for(
                    self.task_queues[priority].get(), 
                    timeout=0.1
                )
                self.stats['queue_depths'][priority] -= 1
                return task
            except asyncio.TimeoutError:
                continue
        
        return None
    
    async def complete_task(self, result: ProcessingResult) -> None:
        """작업 완료 처리"""
        try:
            task_id = result.task_id
            self.completed_tasks[task_id] = result
            self.stats['total_completed'] += 1
            
            # 대기 중인 작업들 확인
            waiting_tasks = self.dependency_waiters.pop(task_id, [])
            for waiting_task_id in waiting_tasks:
                if waiting_task_id in self.pending_tasks:
                    task = self.pending_tasks[waiting_task_id]
                    
                    # 모든 의존성이 해결되었는지 확인
                    all_resolved = all(
                        dep in self.completed_tasks 
                        for dep in task.dependencies
                    )
                    
                    if all_resolved:
                        await self.schedule_task(task)
            
            self.logger.debug(f"작업 완료: {task_id}")
            
        except Exception as e:
            self.logger.error(f"작업 완료 처리 실패: {str(e)}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """큐 통계 반환"""
        return {
            'queue_depths': dict(self.stats['queue_depths']),
            'total_scheduled': self.stats['total_scheduled'],
            'total_completed': self.stats['total_completed'],
            'completion_rate': (
                self.stats['total_completed'] / max(1, self.stats['total_scheduled'])
            ),
            'pending_tasks': len(self.pending_tasks)
        }


class GPUWorkerPool:
    """GPU 워커 풀"""
    
    def __init__(self, config: Config, gpu_count: int):
        self.config = config
        self.gpu_count = gpu_count
        self.workers = {}  # gpu_id -> worker_process
        self.worker_queues = {}  # gpu_id -> Queue
        self.worker_stats = defaultdict(dict)
        self.logger = logging.getLogger(__name__)
        
        # GPU별 메모리 사용량 추적
        self.gpu_memory_usage = {i: 0.0 for i in range(gpu_count)}
        self.gpu_utilization = {i: 0.0 for i in range(gpu_count)}
        
        self.is_running = False
        
    async def start_workers(self) -> None:
        """워커 프로세스 시작"""
        try:
            self.is_running = True
            
            for gpu_id in range(self.gpu_count):
                # 각 GPU별 큐 생성
                self.worker_queues[gpu_id] = mp.Queue(maxsize=100)
                
                # 워커 프로세스 시작
                worker_process = mp.Process(
                    target=self._gpu_worker_process,
                    args=(gpu_id, self.worker_queues[gpu_id])
                )
                worker_process.start()
                self.workers[gpu_id] = worker_process
                
                self.logger.info(f"GPU {gpu_id} 워커 프로세스 시작")
            
            # 모니터링 태스크 시작
            asyncio.create_task(self._monitor_workers())
            
        except Exception as e:
            self.logger.error(f"워커 시작 실패: {str(e)}")
            await self.stop_workers()
    
    def _gpu_worker_process(self, gpu_id: int, task_queue: mp.Queue) -> None:
        """GPU 워커 프로세스"""
        try:
            # GPU 설정
            if HAS_TORCH:
                torch.cuda.set_device(gpu_id)
                torch.cuda.empty_cache()
            
            # GPU 최적화기 초기화
            gpu_optimizer = GPUOptimizer(self.config)
            
            # AI 융합 엔진 초기화
            fusion_engine = CrossAttentionFusionEngine(self.config)
            
            self.logger.info(f"GPU {gpu_id} 워커 초기화 완료")
            
            while True:
                try:
                    # 작업 가져오기 (블로킹, 타임아웃 있음)
                    task_data = task_queue.get(timeout=5.0)
                    
                    if task_data is None:  # 종료 신호
                        break
                    
                    # 작업 처리
                    result = self._process_task_on_gpu(
                        task_data, gpu_id, gpu_optimizer, fusion_engine
                    )
                    
                    # 결과를 큐에 다시 넣기 (간단한 구현)
                    task_queue.put(result)
                    
                except Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"GPU {gpu_id} 워커 처리 오류: {str(e)}")
                    continue
        
        except Exception as e:
            self.logger.error(f"GPU {gpu_id} 워커 프로세스 오류: {str(e)}")
    
    def _process_task_on_gpu(
        self, 
        task: ProcessingTask, 
        gpu_id: int,
        gpu_optimizer: GPUOptimizer,
        fusion_engine: CrossAttentionFusionEngine
    ) -> ProcessingResult:
        """GPU에서 작업 처리"""
        start_time = time.time()
        
        try:
            with gpu_optimizer.gpu_memory_context():
                if task.task_type == 'fusion':
                    # 멀티모달 융합 처리
                    result = asyncio.run(fusion_engine.fuse_multimodal_data(
                        **task.data
                    ))
                elif task.task_type == 'audio':
                    # 음성 처리
                    result = self._process_audio_task(task.data, gpu_optimizer)
                elif task.task_type == 'visual':
                    # 시각 처리
                    result = self._process_visual_task(task.data, gpu_optimizer)
                elif task.task_type == 'inference':
                    # 추론 처리
                    result = self._process_inference_task(task.data, gpu_optimizer)
                else:
                    result = f"Unknown task type: {task.task_type}"
            
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                task_id=task.task_id,
                result=result,
                processing_time=processing_time,
                gpu_id=gpu_id,
                worker_id=f"gpu_worker_{gpu_id}"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                task_id=task.task_id,
                result=None,
                processing_time=processing_time,
                gpu_id=gpu_id,
                worker_id=f"gpu_worker_{gpu_id}",
                error=str(e)
            )
    
    def _process_audio_task(self, data: Any, gpu_optimizer: GPUOptimizer) -> Any:
        """음성 작업 처리"""
        # 음성 처리 로직 (예시)
        time.sleep(0.1)  # 시뮬레이션
        return {"audio_processed": True, "features": "audio_features"}
    
    def _process_visual_task(self, data: Any, gpu_optimizer: GPUOptimizer) -> Any:
        """시각 작업 처리"""
        # 시각 처리 로직 (예시)
        time.sleep(0.15)  # 시뮬레이션
        return {"visual_processed": True, "features": "visual_features"}
    
    def _process_inference_task(self, data: Any, gpu_optimizer: GPUOptimizer) -> Any:
        """추론 작업 처리"""
        # 추론 로직 (예시)
        time.sleep(0.05)  # 시뮬레이션
        return {"inference_result": True, "predictions": [0.9, 0.1]}
    
    async def submit_task(self, task: ProcessingTask) -> Optional[int]:
        """작업 제출 (가장 여유로운 GPU 선택)"""
        try:
            # 가장 여유로운 GPU 찾기
            best_gpu = min(
                range(self.gpu_count),
                key=lambda gpu_id: (
                    self.gpu_memory_usage[gpu_id] + 
                    self.worker_queues[gpu_id].qsize() * 0.1
                )
            )
            
            # 큐에 작업 추가
            self.worker_queues[best_gpu].put_nowait(task)
            
            self.logger.debug(f"작업 {task.task_id}을 GPU {best_gpu}에 제출")
            return best_gpu
            
        except Exception as e:
            self.logger.error(f"작업 제출 실패: {str(e)}")
            return None
    
    async def _monitor_workers(self) -> None:
        """워커 모니터링"""
        while self.is_running:
            try:
                for gpu_id in range(self.gpu_count):
                    if gpu_id in self.workers:
                        worker = self.workers[gpu_id]
                        
                        # 프로세스 상태 확인
                        if not worker.is_alive():
                            self.logger.warning(f"GPU {gpu_id} 워커 비정상 종료 감지")
                            # 워커 재시작 로직
                            await self._restart_worker(gpu_id)
                        
                        # GPU 사용률 업데이트 (간단한 추정)
                        queue_size = self.worker_queues[gpu_id].qsize()
                        self.gpu_utilization[gpu_id] = min(100.0, queue_size * 10)
                
                await asyncio.sleep(5.0)  # 5초마다 체크
                
            except Exception as e:
                self.logger.error(f"워커 모니터링 오류: {str(e)}")
                await asyncio.sleep(1.0)
    
    async def _restart_worker(self, gpu_id: int) -> None:
        """워커 재시작"""
        try:
            # 기존 워커 정리
            if gpu_id in self.workers:
                worker = self.workers[gpu_id]
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5.0)
                del self.workers[gpu_id]
            
            # 새 워커 시작
            worker_process = mp.Process(
                target=self._gpu_worker_process,
                args=(gpu_id, self.worker_queues[gpu_id])
            )
            worker_process.start()
            self.workers[gpu_id] = worker_process
            
            self.logger.info(f"GPU {gpu_id} 워커 재시작 완료")
            
        except Exception as e:
            self.logger.error(f"GPU {gpu_id} 워커 재시작 실패: {str(e)}")
    
    async def stop_workers(self) -> None:
        """워커 중지"""
        try:
            self.is_running = False
            
            # 모든 워커에 종료 신호 전송
            for gpu_id in range(self.gpu_count):
                if gpu_id in self.worker_queues:
                    self.worker_queues[gpu_id].put(None)
            
            # 워커 프로세스 종료 대기
            for gpu_id, worker in self.workers.items():
                worker.join(timeout=10.0)
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            
            self.workers.clear()
            self.logger.info("모든 GPU 워커 중지 완료")
            
        except Exception as e:
            self.logger.error(f"워커 중지 오류: {str(e)}")
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """워커 통계 반환"""
        return {
            'gpu_count': self.gpu_count,
            'active_workers': len([w for w in self.workers.values() if w.is_alive()]),
            'gpu_utilization': dict(self.gpu_utilization),
            'gpu_memory_usage': dict(self.gpu_memory_usage),
            'queue_sizes': {
                gpu_id: queue.qsize() 
                for gpu_id, queue in self.worker_queues.items()
            }
        }


class AsyncRealTimeProcessor:
    """비동기 실시간 처리기"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        실시간 처리기 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # GPU 설정
        self.gpu_count = torch.cuda.device_count() if HAS_TORCH else 0
        self.device = "cuda" if self.gpu_count > 0 else "cpu"
        
        # 컴포넌트 초기화
        self.task_scheduler = TaskScheduler()
        self.gpu_worker_pool = GPUWorkerPool(self.config, self.gpu_count) if self.gpu_count > 0 else None
        
        # 스레드 풀 (CPU 집약적 작업용)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=getattr(self.config, 'CPU_WORKERS', psutil.cpu_count()),
            thread_name_prefix="async_processor"
        )
        
        # 결과 캐시
        self.result_cache = {}
        self.cache_ttl = getattr(self.config, 'CACHE_TTL', 300)  # 5분
        
        # 성능 통계
        self.performance_stats = {
            'total_processed': 0,
            'processing_times': deque(maxlen=1000),
            'throughput_history': deque(maxlen=100),
            'error_count': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # 상태 관리
        self.is_running = False
        self.background_tasks = set()
        
        self.logger.info(
            f"실시간 처리기 초기화 완료 - GPU: {self.gpu_count}개, "
            f"CPU 워커: {getattr(self.config, 'CPU_WORKERS', psutil.cpu_count())}개"
        )
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def start(self) -> None:
        """처리기 시작"""
        try:
            if self.is_running:
                self.logger.warning("처리기가 이미 실행 중입니다")
                return
            
            self.is_running = True
            
            # GPU 워커 풀 시작
            if self.gpu_worker_pool:
                await self.gpu_worker_pool.start_workers()
            
            # 백그라운드 태스크 시작
            background_tasks = [
                asyncio.create_task(self._process_tasks()),
                asyncio.create_task(self._monitor_performance()),
                asyncio.create_task(self._cleanup_cache())
            ]
            
            for task in background_tasks:
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
            
            self.logger.info("실시간 처리기 시작 완료")
            
        except Exception as e:
            self.logger.error(f"처리기 시작 실패: {str(e)}")
            await self.stop()
    
    async def stop(self) -> None:
        """처리기 중지"""
        try:
            self.is_running = False
            
            # 백그라운드 태스크 취소
            for task in self.background_tasks:
                task.cancel()
            
            # 모든 태스크 완료 대기
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # GPU 워커 풀 중지
            if self.gpu_worker_pool:
                await self.gpu_worker_pool.stop_workers()
            
            # 스레드 풀 중지
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("실시간 처리기 중지 완료")
            
        except Exception as e:
            self.logger.error(f"처리기 중지 오류: {str(e)}")
    
    async def submit_task(
        self, 
        data: Any, 
        task_type: str,
        priority: int = 5,
        dependencies: Optional[List[str]] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """
        작업 제출
        
        Args:
            data: 처리할 데이터
            task_type: 작업 타입
            priority: 우선순위 (1-10)
            dependencies: 의존성 작업 ID 목록
            callback: 완료 콜백
            
        Returns:
            작업 ID
        """
        try:
            task_id = str(uuid.uuid4())
            
            task = ProcessingTask(
                task_id=task_id,
                data=data,
                task_type=task_type,
                priority=min(10, max(1, priority)),
                dependencies=dependencies or [],
                callback=callback
            )
            
            await self.task_scheduler.schedule_task(task)
            
            self.logger.debug(f"작업 제출: {task_id} ({task_type})")
            return task_id
            
        except Exception as e:
            self.logger.error(f"작업 제출 실패: {str(e)}")
            raise
    
    async def _process_tasks(self) -> None:
        """작업 처리 메인 루프"""
        while self.is_running:
            try:
                # 다음 작업 가져오기
                task = await self.task_scheduler.get_next_task()
                
                if task is None:
                    await asyncio.sleep(0.01)  # 10ms 대기
                    continue
                
                # 캐시 확인
                cache_key = self._generate_cache_key(task)
                if cache_key in self.result_cache:
                    cached_result, timestamp = self.result_cache[cache_key]
                    if time.time() - timestamp < self.cache_ttl:
                        # 캐시 히트
                        result = ProcessingResult(
                            task_id=task.task_id,
                            result=cached_result,
                            processing_time=0.0,
                            metadata={'cache_hit': True}
                        )
                        await self._handle_task_completion(task, result)
                        self.performance_stats['cache_hits'] += 1
                        continue
                
                self.performance_stats['cache_misses'] += 1
                
                # 작업 처리
                asyncio.create_task(self._execute_task(task))
                
            except Exception as e:
                self.logger.error(f"작업 처리 루프 오류: {str(e)}")
                await asyncio.sleep(0.1)
    
    async def _execute_task(self, task: ProcessingTask) -> None:
        """작업 실행"""
        try:
            start_time = time.time()
            
            # GPU 작업인지 확인
            if self.gpu_worker_pool and task.task_type in ['fusion', 'visual', 'inference']:
                # GPU에서 처리
                gpu_id = await self.gpu_worker_pool.submit_task(task)
                if gpu_id is not None:
                    # GPU 결과 대기 (간단한 구현)
                    result = await self._wait_for_gpu_result(task, gpu_id)
                else:
                    # GPU 사용 불가, CPU 폴백
                    result = await self._execute_on_cpu(task)
            else:
                # CPU에서 처리
                result = await self._execute_on_cpu(task)
            
            # 처리 완료
            await self._handle_task_completion(task, result)
            
        except Exception as e:
            # 오류 처리
            processing_time = time.time() - start_time
            error_result = ProcessingResult(
                task_id=task.task_id,
                result=None,
                processing_time=processing_time,
                error=str(e)
            )
            
            await self._handle_task_completion(task, error_result)
            self.performance_stats['error_count'] += 1
    
    async def _wait_for_gpu_result(self, task: ProcessingTask, gpu_id: int) -> ProcessingResult:
        """GPU 결과 대기 (간단한 구현)"""
        # 실제 구현에서는 더 정교한 결과 수집 메커니즘이 필요
        timeout = 30.0  # 30초 타임아웃
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # GPU 워커 큐에서 결과 확인
                result = self.gpu_worker_pool.worker_queues[gpu_id].get_nowait()
                if isinstance(result, ProcessingResult) and result.task_id == task.task_id:
                    return result
            except:
                await asyncio.sleep(0.1)
        
        # 타임아웃
        return ProcessingResult(
            task_id=task.task_id,
            result=None,
            processing_time=timeout,
            error="GPU processing timeout"
        )
    
    async def _execute_on_cpu(self, task: ProcessingTask) -> ProcessingResult:
        """CPU에서 작업 실행"""
        try:
            start_time = time.time()
            
            # 스레드 풀에서 실행
            loop = asyncio.get_event_loop()
            result_data = await loop.run_in_executor(
                self.thread_pool,
                self._process_task_sync,
                task
            )
            
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                task_id=task.task_id,
                result=result_data,
                processing_time=processing_time,
                worker_id="cpu_worker"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return ProcessingResult(
                task_id=task.task_id,
                result=None,
                processing_time=processing_time,
                error=str(e)
            )
    
    def _process_task_sync(self, task: ProcessingTask) -> Any:
        """동기 작업 처리 (스레드에서 실행)"""
        try:
            if task.task_type == 'audio':
                # 음성 처리 시뮬레이션
                time.sleep(0.1)
                return {"audio_processed": True, "cpu_processed": True}
            elif task.task_type == 'visual':
                # 시각 처리 시뮬레이션
                time.sleep(0.15)
                return {"visual_processed": True, "cpu_processed": True}
            elif task.task_type == 'text':
                # 텍스트 처리 시뮬레이션
                time.sleep(0.05)
                return {"text_processed": True, "cpu_processed": True}
            else:
                return {"processed": True, "task_type": task.task_type}
                
        except Exception as e:
            raise Exception(f"Sync processing failed: {str(e)}")
    
    async def _handle_task_completion(self, task: ProcessingTask, result: ProcessingResult) -> None:
        """작업 완료 처리"""
        try:
            # 스케줄러에 완료 알림
            await self.task_scheduler.complete_task(result)
            
            # 캐시 업데이트
            if result.error is None and result.result is not None:
                cache_key = self._generate_cache_key(task)
                self.result_cache[cache_key] = (result.result, time.time())
            
            # 콜백 실행
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(result)
                    else:
                        task.callback(result)
                except Exception as e:
                    self.logger.warning(f"콜백 실행 오류: {str(e)}")
            
            # 성능 통계 업데이트
            self.performance_stats['total_processed'] += 1
            self.performance_stats['processing_times'].append(result.processing_time)
            
            if result.error:
                self.logger.warning(f"작업 오류: {task.task_id} - {result.error}")
            else:
                self.logger.debug(f"작업 완료: {task.task_id} ({result.processing_time:.3f}초)")
            
        except Exception as e:
            self.logger.error(f"작업 완료 처리 오류: {str(e)}")
    
    def _generate_cache_key(self, task: ProcessingTask) -> str:
        """캐시 키 생성"""
        try:
            # 간단한 해시 기반 캐시 키
            import hashlib
            
            data_str = json.dumps(task.data, sort_keys=True, default=str)
            key = f"{task.task_type}:{hashlib.md5(data_str.encode()).hexdigest()}"
            return key
        except:
            return f"{task.task_type}:{task.task_id}"
    
    async def _monitor_performance(self) -> None:
        """성능 모니터링"""
        while self.is_running:
            try:
                # 처리량 계산
                if self.performance_stats['processing_times']:
                    recent_times = list(self.performance_stats['processing_times'])[-100:]
                    avg_time = sum(recent_times) / len(recent_times)
                    throughput = 1.0 / avg_time if avg_time > 0 else 0
                    self.performance_stats['throughput_history'].append(throughput)
                
                # 메모리 정리
                if self.performance_stats['total_processed'] % 1000 == 0:
                    gc.collect()
                
                await asyncio.sleep(10.0)  # 10초마다 모니터링
                
            except Exception as e:
                self.logger.error(f"성능 모니터링 오류: {str(e)}")
                await asyncio.sleep(1.0)
    
    async def _cleanup_cache(self) -> None:
        """캐시 정리"""
        while self.is_running:
            try:
                current_time = time.time()
                expired_keys = [
                    key for key, (_, timestamp) in self.result_cache.items()
                    if current_time - timestamp > self.cache_ttl
                ]
                
                for key in expired_keys:
                    del self.result_cache[key]
                
                if expired_keys:
                    self.logger.debug(f"캐시 정리: {len(expired_keys)}개 항목 제거")
                
                await asyncio.sleep(60.0)  # 1분마다 정리
                
            except Exception as e:
                self.logger.error(f"캐시 정리 오류: {str(e)}")
                await asyncio.sleep(10.0)
    
    async def get_task_result(self, task_id: str, timeout: float = 30.0) -> Optional[ProcessingResult]:
        """작업 결과 대기"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if task_id in self.task_scheduler.completed_tasks:
                return self.task_scheduler.completed_tasks[task_id]
            
            await asyncio.sleep(0.1)
        
        return None  # 타임아웃
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        stats = {
            'total_processed': self.performance_stats['total_processed'],
            'error_count': self.performance_stats['error_count'],
            'cache_hit_rate': (
                self.performance_stats['cache_hits'] / 
                max(1, self.performance_stats['cache_hits'] + self.performance_stats['cache_misses'])
            ),
            'cache_size': len(self.result_cache),
            'is_running': self.is_running,
            'device': self.device,
            'gpu_count': self.gpu_count
        }
        
        # 처리 시간 통계
        if self.performance_stats['processing_times']:
            times = list(self.performance_stats['processing_times'])
            stats.update({
                'average_processing_time': sum(times) / len(times),
                'min_processing_time': min(times),
                'max_processing_time': max(times),
                'p95_processing_time': sorted(times)[int(len(times) * 0.95)]
            })
        
        # 처리량 통계
        if self.performance_stats['throughput_history']:
            throughputs = list(self.performance_stats['throughput_history'])
            stats.update({
                'current_throughput': throughputs[-1],
                'average_throughput': sum(throughputs) / len(throughputs),
                'peak_throughput': max(throughputs)
            })
        
        # 스케줄러 통계
        stats['scheduler'] = self.task_scheduler.get_queue_stats()
        
        # GPU 워커 통계
        if self.gpu_worker_pool:
            stats['gpu_workers'] = self.gpu_worker_pool.get_worker_stats()
        
        return stats
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.stop()


# 편의 함수들
async def create_real_time_processor(config: Optional[Config] = None) -> AsyncRealTimeProcessor:
    """실시간 처리기 생성 및 시작"""
    processor = AsyncRealTimeProcessor(config)
    await processor.start()
    return processor


def setup_uvloop() -> None:
    """uvloop 설정 (성능 향상)"""
    if HAS_UVLOOP:
        uvloop.install()
        logging.getLogger(__name__).info("uvloop 활성화 - 성능 향상 적용")
    else:
        logging.getLogger(__name__).warning("uvloop 미설치 - 기본 asyncio 사용")