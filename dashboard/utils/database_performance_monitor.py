"""
T01_S03_M03: 데이터베이스 성능 모니터링
데이터베이스 성능 메트릭 수집 및 분석 시스템
"""

import sqlite3
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatabaseMetrics:
    """데이터베이스 메트릭"""
    timestamp: datetime
    connection_count: int
    database_size_mb: float
    query_execution_time: float
    table_count: int
    index_count: int
    cache_hit_ratio: float
    slow_queries_count: int
    largest_table_size_mb: float
    largest_table_name: str


@dataclass
class QueryMetrics:
    """쿼리 메트릭"""
    query_hash: str
    query_type: str
    execution_time: float
    timestamp: datetime
    table_accessed: str
    rows_affected: int
    status: str  # success, error, timeout


class DatabasePerformanceMonitor:
    """데이터베이스 성능 모니터링 관리자"""
    
    def __init__(self, db_path: str = "influence_item.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.metrics_history = []
        self.query_history = []
        self.slow_query_threshold = 1.0  # 1초 이상은 슬로우 쿼리
        self._lock = threading.Lock()
        
        # 쿼리 성능 추적을 위한 설정
        self.tracked_queries = {
            'SELECT': [],
            'INSERT': [],
            'UPDATE': [],
            'DELETE': []
        }
        
    def collect_database_metrics(self) -> DatabaseMetrics:
        """데이터베이스 메트릭 수집"""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                
                # 데이터베이스 크기 조회
                db_size = Path(self.db_path).stat().st_size / (1024 * 1024)  # MB
                
                # 테이블 수 조회
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # 인덱스 수 조회
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                index_count = cursor.fetchone()[0]
                
                # 테이블별 크기 조회
                table_sizes = self._get_table_sizes(cursor)
                largest_table = max(table_sizes.items(), key=lambda x: x[1]) if table_sizes else ("unknown", 0)
                
                # 연결 수 (SQLite는 단일 연결이므로 1)
                connection_count = 1
                
                # 캐시 히트 비율 (SQLite PRAGMA 사용)
                cache_hit_ratio = self._get_cache_hit_ratio(cursor)
                
                # 최근 슬로우 쿼리 수
                slow_queries_count = len([q for q in self.query_history 
                                        if q.execution_time > self.slow_query_threshold 
                                        and q.timestamp > datetime.now() - timedelta(hours=1)])
                
                # 테스트 쿼리 실행 시간 측정
                start_time = time.time()
                cursor.execute("SELECT 1")
                query_execution_time = (time.time() - start_time) * 1000  # ms
                
                metrics = DatabaseMetrics(
                    timestamp=datetime.now(),
                    connection_count=connection_count,
                    database_size_mb=db_size,
                    query_execution_time=query_execution_time,
                    table_count=table_count,
                    index_count=index_count,
                    cache_hit_ratio=cache_hit_ratio,
                    slow_queries_count=slow_queries_count,
                    largest_table_size_mb=largest_table[1],
                    largest_table_name=largest_table[0]
                )
                
                # 메트릭 히스토리에 추가
                with self._lock:
                    self.metrics_history.append(metrics)
                    # 최근 24시간만 유지
                    cutoff_time = datetime.now() - timedelta(hours=24)
                    self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            return None
    
    def _get_table_sizes(self, cursor: sqlite3.Cursor) -> Dict[str, float]:
        """테이블별 크기 조회"""
        table_sizes = {}
        try:
            # 모든 테이블 목록 조회
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for (table_name,) in tables:
                try:
                    # 테이블 행 수 조회
                    cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    row_count = cursor.fetchone()[0]
                    
                    # SQLite에서는 정확한 테이블 크기를 구하기 어려우므로 근사치 계산
                    # 평균 행 크기를 1KB로 가정
                    estimated_size_mb = (row_count * 1024) / (1024 * 1024)
                    table_sizes[table_name] = estimated_size_mb
                    
                except Exception as e:
                    logger.warning(f"Failed to get size for table {table_name}: {e}")
                    table_sizes[table_name] = 0.0
            
        except Exception as e:
            logger.error(f"Failed to get table sizes: {e}")
        
        return table_sizes
    
    def _get_cache_hit_ratio(self, cursor: sqlite3.Cursor) -> float:
        """캐시 히트 비율 조회"""
        try:
            # SQLite의 페이지 캐시 통계 조회
            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]
            
            # SQLite는 상세한 캐시 통계를 제공하지 않으므로 기본값 반환
            # 실제 환경에서는 다른 방법으로 측정해야 함
            return 85.0  # 기본 85% 가정
            
        except Exception as e:
            logger.warning(f"Failed to get cache hit ratio: {e}")
            return 0.0
    
    def track_query(self, query: str, execution_time: float, table_accessed: str = "unknown", 
                   rows_affected: int = 0, status: str = "success"):
        """쿼리 실행 추적"""
        try:
            # 쿼리 타입 결정
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT'):
                query_type = 'SELECT'
            elif query_upper.startswith('INSERT'):
                query_type = 'INSERT'
            elif query_upper.startswith('UPDATE'):
                query_type = 'UPDATE'
            elif query_upper.startswith('DELETE'):
                query_type = 'DELETE'
            else:
                query_type = 'OTHER'
            
            # 쿼리 해시 생성 (간단한 해시)
            query_hash = str(hash(query[:100]))  # 처음 100자만 사용
            
            query_metrics = QueryMetrics(
                query_hash=query_hash,
                query_type=query_type,
                execution_time=execution_time,
                timestamp=datetime.now(),
                table_accessed=table_accessed,
                rows_affected=rows_affected,
                status=status
            )
            
            with self._lock:
                self.query_history.append(query_metrics)
                # 최근 1000개 쿼리만 유지
                if len(self.query_history) > 1000:
                    self.query_history = self.query_history[-1000:]
                
                # 쿼리 타입별 추적
                if query_type in self.tracked_queries:
                    self.tracked_queries[query_type].append(query_metrics)
                    # 각 타입별로 최근 100개만 유지
                    if len(self.tracked_queries[query_type]) > 100:
                        self.tracked_queries[query_type] = self.tracked_queries[query_type][-100:]
        
        except Exception as e:
            logger.error(f"Failed to track query: {e}")
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """성능 요약 정보 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 메트릭 히스토리 필터링
            recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
            
            # 쿼리 히스토리 필터링
            recent_queries = [q for q in self.query_history if q.timestamp > cutoff_time]
            
            if not recent_metrics:
                return {"error": "No recent metrics data available"}
            
            # 기본 통계
            avg_db_size = sum(m.database_size_mb for m in recent_metrics) / len(recent_metrics)
            avg_query_time = sum(m.query_execution_time for m in recent_metrics) / len(recent_metrics)
            total_slow_queries = sum(m.slow_queries_count for m in recent_metrics)
            
            # 쿼리 타입별 통계
            query_type_stats = {}
            for query_type in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']:
                type_queries = [q for q in recent_queries if q.query_type == query_type]
                if type_queries:
                    avg_execution_time = sum(q.execution_time for q in type_queries) / len(type_queries)
                    max_execution_time = max(q.execution_time for q in type_queries)
                    query_count = len(type_queries)
                    success_rate = sum(1 for q in type_queries if q.status == 'success') / len(type_queries) * 100
                else:
                    avg_execution_time = 0
                    max_execution_time = 0
                    query_count = 0
                    success_rate = 100
                
                query_type_stats[query_type] = {
                    'count': query_count,
                    'avg_execution_time': avg_execution_time,
                    'max_execution_time': max_execution_time,
                    'success_rate': success_rate
                }
            
            # 슬로우 쿼리 분석
            slow_queries = [q for q in recent_queries if q.execution_time > self.slow_query_threshold]
            slow_query_analysis = {}
            if slow_queries:
                for query in slow_queries:
                    table = query.table_accessed
                    if table not in slow_query_analysis:
                        slow_query_analysis[table] = {
                            'count': 0,
                            'avg_time': 0,
                            'max_time': 0,
                            'query_types': set()
                        }
                    
                    slow_query_analysis[table]['count'] += 1
                    slow_query_analysis[table]['query_types'].add(query.query_type)
                    slow_query_analysis[table]['max_time'] = max(
                        slow_query_analysis[table]['max_time'], 
                        query.execution_time
                    )
                
                # 평균 시간 계산
                for table_data in slow_query_analysis.values():
                    table_queries = [q for q in slow_queries if q.table_accessed == table]
                    table_data['avg_time'] = sum(q.execution_time for q in table_queries) / len(table_queries)
                    table_data['query_types'] = list(table_data['query_types'])
            
            return {
                'period_hours': hours,
                'metrics_count': len(recent_metrics),
                'database_stats': {
                    'avg_size_mb': round(avg_db_size, 2),
                    'table_count': recent_metrics[-1].table_count if recent_metrics else 0,
                    'index_count': recent_metrics[-1].index_count if recent_metrics else 0,
                    'largest_table': recent_metrics[-1].largest_table_name if recent_metrics else "unknown"
                },
                'query_performance': {
                    'total_queries': len(recent_queries),
                    'avg_execution_time': round(avg_query_time, 2),
                    'slow_queries_count': len(slow_queries),
                    'query_type_stats': query_type_stats
                },
                'slow_query_analysis': slow_query_analysis,
                'latest_metrics': asdict(recent_metrics[-1]) if recent_metrics else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """실시간 통계 조회"""
        try:
            current_metrics = self.collect_database_metrics()
            if not current_metrics:
                return {"error": "Failed to collect current metrics"}
            
            # 최근 5분간 쿼리 통계
            recent_time = datetime.now() - timedelta(minutes=5)
            recent_queries = [q for q in self.query_history if q.timestamp > recent_time]
            
            return {
                'timestamp': current_metrics.timestamp.isoformat(),
                'database_size_mb': current_metrics.database_size_mb,
                'query_execution_time_ms': current_metrics.query_execution_time,
                'table_count': current_metrics.table_count,
                'cache_hit_ratio': current_metrics.cache_hit_ratio,
                'recent_queries_5min': len(recent_queries),
                'slow_queries_last_hour': current_metrics.slow_queries_count,
                'largest_table': {
                    'name': current_metrics.largest_table_name,
                    'size_mb': current_metrics.largest_table_size_mb
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time stats: {e}")
            return {"error": str(e)}
    
    def cleanup_old_data(self, hours: int = 24):
        """오래된 데이터 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with self._lock:
                # 메트릭 히스토리 정리
                self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
                
                # 쿼리 히스토리 정리
                self.query_history = [q for q in self.query_history if q.timestamp > cutoff_time]
                
                # 추적된 쿼리 정리
                for query_type in self.tracked_queries:
                    self.tracked_queries[query_type] = [
                        q for q in self.tracked_queries[query_type] 
                        if q.timestamp > cutoff_time
                    ]
            
            logger.info(f"Cleaned up database monitoring data older than {hours} hours")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")


# 전역 데이터베이스 성능 모니터 인스턴스
_db_monitor = None


def get_database_monitor(db_path: str = "influence_item.db") -> DatabasePerformanceMonitor:
    """싱글톤 데이터베이스 모니터 반환"""
    global _db_monitor
    if _db_monitor is None:
        _db_monitor = DatabasePerformanceMonitor(db_path)
    return _db_monitor


# 쿼리 실행 시간을 자동으로 추적하는 데코레이터
def track_query_performance(table_name: str = "unknown"):
    """쿼리 성능 추적 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            monitor = get_database_monitor()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000  # ms
                
                # 함수 이름에서 쿼리 타입 추정
                func_name = func.__name__.lower()
                if 'select' in func_name or 'get' in func_name or 'find' in func_name:
                    query_type = 'SELECT'
                elif 'insert' in func_name or 'create' in func_name or 'add' in func_name:
                    query_type = 'INSERT'
                elif 'update' in func_name or 'modify' in func_name or 'edit' in func_name:
                    query_type = 'UPDATE'
                elif 'delete' in func_name or 'remove' in func_name:
                    query_type = 'DELETE'
                else:
                    query_type = 'OTHER'
                
                monitor.track_query(
                    query=f"{query_type} operation in {func.__name__}",
                    execution_time=execution_time,
                    table_accessed=table_name,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000  # ms
                monitor.track_query(
                    query=f"FAILED operation in {func.__name__}",
                    execution_time=execution_time,
                    table_accessed=table_name,
                    status="error"
                )
                raise e
                
        return wrapper
    return decorator