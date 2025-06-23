"""
T03A_S03_M03: 스케일링 메트릭 수집기
자동 스케일링의 기반이 되는 핵심 메트릭을 실시간으로 수집하고 저장하는 시스템
"""

import psutil
import sqlite3
import time
import json
import logging
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from queue import Queue
import os

# GPU 모니터링을 위한 임포트
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ScalingMetrics:
    """스케일링을 위한 핵심 메트릭"""
    timestamp: datetime
    
    # 처리 대기열 메트릭
    processing_queue_length: int
    pending_requests: int
    active_analyses: int
    
    # 시스템 리소스 메트릭
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    
    # GPU 메트릭 (있는 경우)
    gpu_utilization: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_temperature: Optional[float] = None
    
    # 응답 시간 메트릭
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # 처리량 메트릭
    completed_requests_last_hour: int = 0
    failed_requests_last_hour: int = 0
    success_rate: float = 100.0
    
    # 네트워크 메트릭
    network_io_mbps: float = 0.0
    active_connections: int = 0
    
    # 스케일링 결정 관련
    predicted_load_1h: Optional[float] = None
    scaling_recommendation: Optional[str] = None  # "scale_up", "scale_down", "maintain"


@dataclass
class ResponseTimeSnapshot:
    """응답 시간 스냅샷"""
    timestamp: datetime
    endpoint: str
    response_time_ms: float
    success: bool


class ScalingMetricsCollector:
    """스케일링 메트릭 수집기"""
    
    def __init__(self, db_path: str = "scaling_metrics.db", collection_interval: int = 60):
        """
        Args:
            db_path: 메트릭 저장 데이터베이스 경로
            collection_interval: 수집 간격 (초)
        """
        self.db_path = db_path
        self.collection_interval = collection_interval
        self.is_collecting = False
        self.collector_thread = None
        
        # 응답 시간 추적을 위한 큐 (최근 1시간)
        self.response_times = Queue()
        self.response_times_lock = threading.Lock()
        
        # 처리 통계 추적
        self.processing_stats = {
            'completed_requests': 0,
            'failed_requests': 0,
            'last_reset': datetime.now()
        }
        self.stats_lock = threading.Lock()
        
        # 네트워크 IO 기준점
        self.last_network_io = None
        self.last_network_time = None
        
        self._init_database()
        
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 스케일링 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scaling_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        processing_queue_length INTEGER NOT NULL,
                        pending_requests INTEGER NOT NULL,
                        active_analyses INTEGER NOT NULL,
                        cpu_percent REAL NOT NULL,
                        memory_percent REAL NOT NULL,
                        memory_available_gb REAL NOT NULL,
                        gpu_utilization REAL,
                        gpu_memory_percent REAL,
                        gpu_temperature REAL,
                        avg_response_time REAL NOT NULL,
                        p95_response_time REAL NOT NULL,
                        p99_response_time REAL NOT NULL,
                        completed_requests_last_hour INTEGER NOT NULL,
                        failed_requests_last_hour INTEGER NOT NULL,
                        success_rate REAL NOT NULL,
                        network_io_mbps REAL NOT NULL,
                        active_connections INTEGER NOT NULL,
                        predicted_load_1h REAL,
                        scaling_recommendation TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 응답 시간 로그 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS response_time_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        endpoint TEXT NOT NULL,
                        response_time_ms REAL NOT NULL,
                        success BOOLEAN NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 인덱스 생성
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_scaling_metrics_timestamp ON scaling_metrics(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_response_logs_timestamp ON response_time_logs(timestamp)')
                
                conn.commit()
                logger.info("Scaling metrics database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize scaling metrics database: {e}")
            raise
    
    def start_collection(self):
        """메트릭 수집 시작"""
        if self.is_collecting:
            logger.info("Metrics collection is already running")
            return
        
        self.is_collecting = True
        self.collector_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collector_thread.start()
        logger.info("Scaling metrics collection started")
    
    def stop_collection(self):
        """메트릭 수집 중지"""
        self.is_collecting = False
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=5)
        logger.info("Scaling metrics collection stopped")
    
    def _collection_loop(self):
        """메트릭 수집 루프"""
        while self.is_collecting:
            try:
                # 메트릭 수집
                metrics = self._collect_scaling_metrics()
                
                # 데이터베이스에 저장
                self._store_metrics(metrics)
                
                # 다음 수집까지 대기
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in scaling metrics collection loop: {e}")
                time.sleep(10)  # 에러 시 짧은 대기 후 재시도
    
    def _collect_scaling_metrics(self) -> ScalingMetrics:
        """스케일링 메트릭 수집"""
        try:
            timestamp = datetime.now()
            
            # 기본 시스템 메트릭
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_available_gb = memory.available / (1024**3)
            
            # 네트워크 연결 수
            try:
                connections = len([c for c in psutil.net_connections() if c.status == 'ESTABLISHED'])
            except (psutil.AccessDenied, OSError):
                connections = 0
            
            # GPU 메트릭 수집
            gpu_util, gpu_memory, gpu_temp = self._collect_gpu_metrics()
            
            # 처리 대기열 메트릭 (실제 구현에서는 애플리케이션 상태에서 가져옴)
            queue_metrics = self._get_processing_queue_metrics()
            
            # 응답 시간 통계
            response_stats = self._calculate_response_time_stats()
            
            # 처리량 통계
            processing_stats = self._get_processing_stats()
            
            # 네트워크 IO 속도
            network_speed = self._calculate_network_io_speed()
            
            return ScalingMetrics(
                timestamp=timestamp,
                processing_queue_length=queue_metrics['queue_length'],
                pending_requests=queue_metrics['pending_requests'],
                active_analyses=queue_metrics['active_analyses'],
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_gb=memory_available_gb,
                gpu_utilization=gpu_util,
                gpu_memory_percent=gpu_memory,
                gpu_temperature=gpu_temp,
                avg_response_time=response_stats['avg'],
                p95_response_time=response_stats['p95'],
                p99_response_time=response_stats['p99'],
                completed_requests_last_hour=processing_stats['completed'],
                failed_requests_last_hour=processing_stats['failed'],
                success_rate=processing_stats['success_rate'],
                network_io_mbps=network_speed,
                active_connections=connections
            )
            
        except Exception as e:
            logger.error(f"Failed to collect scaling metrics: {e}")
            # 기본값으로 빈 메트릭 반환
            return ScalingMetrics(
                timestamp=datetime.now(),
                processing_queue_length=0,
                pending_requests=0,
                active_analyses=0,
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_gb=0.0
            )
    
    def _collect_gpu_metrics(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """GPU 메트릭 수집"""
        if not GPU_AVAILABLE:
            return None, None, None
        
        try:
            gpus = GPUtil.getGPUs()
            if not gpus:
                return None, None, None
            
            # 첫 번째 GPU의 메트릭 사용
            gpu = gpus[0]
            return (
                gpu.load * 100,  # 백분율로 변환
                gpu.memoryUtil * 100,  # 백분율로 변환
                gpu.temperature
            )
            
        except Exception as e:
            logger.error(f"Failed to collect GPU metrics: {e}")
            return None, None, None
    
    def _get_processing_queue_metrics(self) -> Dict[str, int]:
        """처리 대기열 메트릭 수집"""
        # 실제 구현에서는 애플리케이션의 작업 큐나 상태 관리자에서 데이터를 가져옴
        # 현재는 시뮬레이션된 데이터 반환
        try:
            # 데이터베이스에서 진행 중인 분석 건수 확인
            with sqlite3.connect("influence_item.db") as conn:
                cursor = conn.cursor()
                
                # 진행 중인 분석 수
                cursor.execute("""
                    SELECT COUNT(*) FROM analysis_results 
                    WHERE status = 'processing' OR created_at > datetime('now', '-1 hour')
                """)
                active_analyses = cursor.fetchone()[0] or 0
                
                # 대기 중인 요청 수 (최근 생성되었지만 아직 처리되지 않은 것들)
                cursor.execute("""
                    SELECT COUNT(*) FROM analysis_results 
                    WHERE status = 'pending' OR status = 'queued'
                """)
                pending_requests = cursor.fetchone()[0] or 0
                
            return {
                'queue_length': active_analyses + pending_requests,
                'pending_requests': pending_requests,
                'active_analyses': active_analyses
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing queue metrics: {e}")
            return {
                'queue_length': 0,
                'pending_requests': 0,
                'active_analyses': 0
            }
    
    def _calculate_response_time_stats(self) -> Dict[str, float]:
        """응답 시간 통계 계산"""
        with self.response_times_lock:
            # 최근 1시간의 응답 시간만 유지
            cutoff_time = datetime.now() - timedelta(hours=1)
            recent_times = []
            
            # 큐에서 최근 데이터만 추출
            temp_queue = Queue()
            while not self.response_times.empty():
                snapshot = self.response_times.get()
                if snapshot.timestamp >= cutoff_time:
                    recent_times.append(snapshot.response_time_ms)
                    temp_queue.put(snapshot)
            
            # 큐 복원
            self.response_times = temp_queue
            
            if not recent_times:
                return {'avg': 0.0, 'p95': 0.0, 'p99': 0.0}
            
            recent_times.sort()
            avg_time = sum(recent_times) / len(recent_times)
            p95_time = recent_times[int(len(recent_times) * 0.95)]
            p99_time = recent_times[int(len(recent_times) * 0.99)]
            
            return {
                'avg': avg_time,
                'p95': p95_time,
                'p99': p99_time
            }
    
    def _get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 조회"""
        with self.stats_lock:
            # 1시간마다 통계 리셋
            if datetime.now() - self.processing_stats['last_reset'] > timedelta(hours=1):
                self.processing_stats = {
                    'completed_requests': 0,
                    'failed_requests': 0,
                    'last_reset': datetime.now()
                }
            
            total_requests = self.processing_stats['completed_requests'] + self.processing_stats['failed_requests']
            success_rate = (
                (self.processing_stats['completed_requests'] / total_requests * 100)
                if total_requests > 0 else 100.0
            )
            
            return {
                'completed': self.processing_stats['completed_requests'],
                'failed': self.processing_stats['failed_requests'],
                'success_rate': success_rate
            }
    
    def _calculate_network_io_speed(self) -> float:
        """네트워크 IO 속도 계산 (Mbps)"""
        try:
            current_io = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_network_io is None:
                self.last_network_io = current_io
                self.last_network_time = current_time
                return 0.0
            
            # 전송 속도 계산
            bytes_sent_diff = current_io.bytes_sent - self.last_network_io.bytes_sent
            bytes_recv_diff = current_io.bytes_recv - self.last_network_io.bytes_recv
            time_diff = current_time - self.last_network_time
            
            if time_diff > 0:
                total_bytes = bytes_sent_diff + bytes_recv_diff
                mbps = (total_bytes * 8) / (time_diff * 1024 * 1024)  # Mbps로 변환
            else:
                mbps = 0.0
            
            # 기준점 업데이트
            self.last_network_io = current_io
            self.last_network_time = current_time
            
            return mbps
            
        except Exception as e:
            logger.error(f"Failed to calculate network IO speed: {e}")
            return 0.0
    
    def _store_metrics(self, metrics: ScalingMetrics):
        """메트릭을 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO scaling_metrics (
                        timestamp, processing_queue_length, pending_requests, active_analyses,
                        cpu_percent, memory_percent, memory_available_gb, gpu_utilization,
                        gpu_memory_percent, gpu_temperature, avg_response_time, p95_response_time,
                        p99_response_time, completed_requests_last_hour, failed_requests_last_hour,
                        success_rate, network_io_mbps, active_connections, predicted_load_1h,
                        scaling_recommendation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.timestamp, metrics.processing_queue_length, metrics.pending_requests,
                    metrics.active_analyses, metrics.cpu_percent, metrics.memory_percent,
                    metrics.memory_available_gb, metrics.gpu_utilization, metrics.gpu_memory_percent,
                    metrics.gpu_temperature, metrics.avg_response_time, metrics.p95_response_time,
                    metrics.p99_response_time, metrics.completed_requests_last_hour,
                    metrics.failed_requests_last_hour, metrics.success_rate, metrics.network_io_mbps,
                    metrics.active_connections, metrics.predicted_load_1h, metrics.scaling_recommendation
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store scaling metrics: {e}")
    
    def record_response_time(self, endpoint: str, response_time_ms: float, success: bool):
        """응답 시간 기록"""
        snapshot = ResponseTimeSnapshot(
            timestamp=datetime.now(),
            endpoint=endpoint,
            response_time_ms=response_time_ms,
            success=success
        )
        
        with self.response_times_lock:
            self.response_times.put(snapshot)
        
        # 데이터베이스에도 저장
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO response_time_logs (timestamp, endpoint, response_time_ms, success)
                    VALUES (?, ?, ?, ?)
                ''', (snapshot.timestamp, endpoint, response_time_ms, success))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store response time log: {e}")
    
    def record_processing_result(self, success: bool):
        """처리 결과 기록"""
        with self.stats_lock:
            if success:
                self.processing_stats['completed_requests'] += 1
            else:
                self.processing_stats['failed_requests'] += 1
    
    def get_recent_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """최근 메트릭 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM scaling_metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp ASC
                ''', (cutoff_time,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    row_dict = dict(zip(columns, row))
                    results.append(row_dict)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get recent metrics: {e}")
            return []
    
    def get_current_metrics(self) -> Optional[ScalingMetrics]:
        """현재 메트릭 조회"""
        try:
            return self._collect_scaling_metrics()
        except Exception as e:
            logger.error(f"Failed to get current metrics: {e}")
            return None
    
    def cleanup_old_data(self, days: int = 7):
        """오래된 데이터 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 메트릭 데이터 정리
                cursor.execute('DELETE FROM scaling_metrics WHERE timestamp < ?', (cutoff_time,))
                cursor.execute('DELETE FROM response_time_logs WHERE timestamp < ?', (cutoff_time,))
                
                conn.commit()
                cursor.execute('VACUUM')
                
            logger.info(f"Cleaned up scaling metrics data older than {days} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old scaling metrics data: {e}")


# 전역 스케일링 메트릭 수집기 인스턴스
_scaling_metrics_collector = None


def get_scaling_metrics_collector(db_path: str = "scaling_metrics.db") -> ScalingMetricsCollector:
    """싱글톤 스케일링 메트릭 수집기 반환"""
    global _scaling_metrics_collector
    if _scaling_metrics_collector is None:
        _scaling_metrics_collector = ScalingMetricsCollector(db_path)
    return _scaling_metrics_collector