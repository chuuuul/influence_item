"""
T01_S03_M03: 모니터링 데이터 저장 스키마
시계열 모니터링 데이터 저장 및 관리 시스템
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class MonitoringDatabase:
    """모니터링 데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "monitoring_data.db"):
        """
        Args:
            db_path: 모니터링 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 시스템 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        cpu_percent REAL NOT NULL,
                        memory_percent REAL NOT NULL,
                        memory_available INTEGER NOT NULL,
                        disk_percent REAL NOT NULL,
                        disk_free INTEGER NOT NULL,
                        active_connections INTEGER NOT NULL,
                        uptime REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # GPU 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gpu_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        gpu_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        load_percent REAL NOT NULL,
                        memory_util_percent REAL NOT NULL,
                        memory_total_mb INTEGER NOT NULL,
                        memory_used_mb INTEGER NOT NULL,
                        memory_free_mb INTEGER NOT NULL,
                        temperature_c REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 네트워크 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS network_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        bytes_sent INTEGER NOT NULL,
                        bytes_recv INTEGER NOT NULL,
                        packets_sent INTEGER NOT NULL,
                        packets_recv INTEGER NOT NULL,
                        connections_established INTEGER NOT NULL,
                        connections_listening INTEGER NOT NULL,
                        network_io_read_speed REAL NOT NULL,
                        network_io_write_speed REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # API 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS api_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        endpoint TEXT NOT NULL,
                        method TEXT NOT NULL,
                        status_code INTEGER NOT NULL,
                        response_time REAL NOT NULL,
                        request_size INTEGER NOT NULL,
                        response_size INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 데이터베이스 성능 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS database_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        database_size_mb REAL NOT NULL,
                        table_count INTEGER NOT NULL,
                        index_count INTEGER NOT NULL,
                        query_execution_time REAL NOT NULL,
                        cache_hit_ratio REAL NOT NULL,
                        slow_queries_count INTEGER NOT NULL,
                        largest_table_size_mb REAL NOT NULL,
                        largest_table_name TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # n8n 워크플로우 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS n8n_workflow_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        workflow_id TEXT NOT NULL,
                        workflow_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        total_executions INTEGER NOT NULL,
                        success_rate REAL NOT NULL,
                        avg_execution_time REAL NOT NULL,
                        last_execution DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # n8n 실행 메트릭 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS n8n_execution_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        execution_id TEXT NOT NULL,
                        workflow_id TEXT NOT NULL,
                        workflow_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        start_time DATETIME NOT NULL,
                        end_time DATETIME,
                        execution_time REAL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 헬스체크 로그 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS health_check_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        component TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT NOT NULL,
                        response_time REAL NOT NULL,
                        details TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 알림 로그 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alert_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT NOT NULL,
                        metric_value REAL,
                        threshold_value REAL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 인덱스 생성 (성능 최적화)
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_gpu_metrics_timestamp ON gpu_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_network_metrics_timestamp ON network_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON api_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_api_metrics_endpoint ON api_metrics(endpoint)",
                    "CREATE INDEX IF NOT EXISTS idx_database_metrics_timestamp ON database_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_n8n_workflow_timestamp ON n8n_workflow_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_n8n_execution_timestamp ON n8n_execution_metrics(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_health_logs_timestamp ON health_check_logs(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_health_logs_component ON health_check_logs(component)",
                    "CREATE INDEX IF NOT EXISTS idx_alert_logs_timestamp ON alert_logs(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_alert_logs_type ON alert_logs(alert_type)"
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                conn.commit()
                logger.info("Monitoring database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize monitoring database: {e}")
            raise
    
    def store_system_metrics(self, metrics_data: Dict[str, Any]):
        """시스템 메트릭 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO system_metrics (
                            timestamp, cpu_percent, memory_percent, memory_available,
                            disk_percent, disk_free, active_connections, uptime
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metrics_data['timestamp'],
                        metrics_data['cpu_percent'],
                        metrics_data['memory_percent'],
                        metrics_data['memory_available'],
                        metrics_data['disk_percent'],
                        metrics_data['disk_free'],
                        metrics_data['active_connections'],
                        metrics_data['uptime']
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store system metrics: {e}")
    
    def store_gpu_metrics(self, gpu_metrics_list: List[Dict[str, Any]]):
        """GPU 메트릭 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    for gpu_data in gpu_metrics_list:
                        cursor.execute('''
                            INSERT INTO gpu_metrics (
                                timestamp, gpu_id, name, load_percent, memory_util_percent,
                                memory_total_mb, memory_used_mb, memory_free_mb, temperature_c
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            gpu_data['timestamp'],
                            gpu_data['gpu_id'],
                            gpu_data['name'],
                            gpu_data['load'],
                            gpu_data['memory_util'],
                            gpu_data['memory_total'],
                            gpu_data['memory_used'],
                            gpu_data['memory_free'],
                            gpu_data['temperature']
                        ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store GPU metrics: {e}")
    
    def store_network_metrics(self, metrics_data: Dict[str, Any]):
        """네트워크 메트릭 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO network_metrics (
                            timestamp, bytes_sent, bytes_recv, packets_sent, packets_recv,
                            connections_established, connections_listening, 
                            network_io_read_speed, network_io_write_speed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metrics_data['timestamp'],
                        metrics_data['bytes_sent'],
                        metrics_data['bytes_recv'],
                        metrics_data['packets_sent'],
                        metrics_data['packets_recv'],
                        metrics_data['connections_established'],
                        metrics_data['connections_listening'],
                        metrics_data['network_io_read_speed'],
                        metrics_data['network_io_write_speed']
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store network metrics: {e}")
    
    def store_api_metrics(self, metrics_data: Dict[str, Any]):
        """API 메트릭 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO api_metrics (
                            timestamp, endpoint, method, status_code, response_time,
                            request_size, response_size, success, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metrics_data['timestamp'],
                        metrics_data['endpoint'],
                        metrics_data['method'],
                        metrics_data['status_code'],
                        metrics_data['response_time'],
                        metrics_data['request_size'],
                        metrics_data['response_size'],
                        metrics_data['success'],
                        metrics_data.get('error_message')
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store API metrics: {e}")
    
    def store_database_metrics(self, metrics_data: Dict[str, Any]):
        """데이터베이스 메트릭 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO database_metrics (
                            timestamp, database_size_mb, table_count, index_count,
                            query_execution_time, cache_hit_ratio, slow_queries_count,
                            largest_table_size_mb, largest_table_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metrics_data['timestamp'],
                        metrics_data['database_size_mb'],
                        metrics_data['table_count'],
                        metrics_data['index_count'],
                        metrics_data['query_execution_time'],
                        metrics_data['cache_hit_ratio'],
                        metrics_data['slow_queries_count'],
                        metrics_data['largest_table_size_mb'],
                        metrics_data['largest_table_name']
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store database metrics: {e}")
    
    def store_health_check(self, component: str, status: str, message: str, 
                          response_time: float, details: Dict = None):
        """헬스체크 로그 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO health_check_logs (
                            timestamp, component, status, message, response_time, details
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now(),
                        component,
                        status,
                        message,
                        response_time,
                        json.dumps(details) if details else None
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store health check: {e}")
    
    def store_alert(self, alert_type: str, severity: str, message: str, 
                   component: str, metric_value: float = None, 
                   threshold_value: float = None):
        """알림 로그 저장"""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO alert_logs (
                            timestamp, alert_type, severity, message, component,
                            metric_value, threshold_value
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now(),
                        alert_type,
                        severity,
                        message,
                        component,
                        metric_value,
                        threshold_value
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    def get_system_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """시스템 메트릭 이력 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM system_metrics 
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
            logger.error(f"Failed to get system metrics history: {e}")
            return []
    
    def get_gpu_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """GPU 메트릭 이력 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM gpu_metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp ASC, gpu_id ASC
                ''', (cutoff_time,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    row_dict = dict(zip(columns, row))
                    results.append(row_dict)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get GPU metrics history: {e}")
            return []
    
    def get_api_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """API 성능 요약 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 통계
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_requests,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                        AVG(response_time) as avg_response_time,
                        MIN(response_time) as min_response_time,
                        MAX(response_time) as max_response_time
                    FROM api_metrics 
                    WHERE timestamp >= ?
                ''', (cutoff_time,))
                
                overall_stats = cursor.fetchone()
                
                # 엔드포인트별 통계
                cursor.execute('''
                    SELECT 
                        endpoint,
                        COUNT(*) as total_requests,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                        AVG(response_time) as avg_response_time,
                        MAX(timestamp) as last_request
                    FROM api_metrics 
                    WHERE timestamp >= ?
                    GROUP BY endpoint
                    ORDER BY total_requests DESC
                ''', (cutoff_time,))
                
                endpoint_stats = cursor.fetchall()
                
                return {
                    'overall': {
                        'total_requests': overall_stats[0],
                        'successful_requests': overall_stats[1],
                        'success_rate': (overall_stats[1] / overall_stats[0] * 100) if overall_stats[0] > 0 else 0,
                        'avg_response_time': overall_stats[2],
                        'min_response_time': overall_stats[3],
                        'max_response_time': overall_stats[4]
                    },
                    'endpoints': [
                        {
                            'endpoint': row[0],
                            'total_requests': row[1],
                            'successful_requests': row[2],
                            'success_rate': (row[2] / row[1] * 100) if row[1] > 0 else 0,
                            'avg_response_time': row[3],
                            'last_request': row[4]
                        }
                        for row in endpoint_stats
                    ]
                }
                
        except Exception as e:
            logger.error(f"Failed to get API performance summary: {e}")
            return {}
    
    def cleanup_old_data(self, hours: int = 168):  # 기본 7일
        """오래된 데이터 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            tables = [
                'system_metrics',
                'gpu_metrics',
                'network_metrics',
                'api_metrics',
                'database_metrics',
                'n8n_workflow_metrics',
                'n8n_execution_metrics',
                'health_check_logs'
            ]
            
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    for table in tables:
                        cursor.execute(f'''
                            DELETE FROM {table} 
                            WHERE timestamp < ?
                        ''', (cutoff_time,))
                    
                    # 해결된 알림만 정리 (미해결 알림은 유지)
                    cursor.execute('''
                        DELETE FROM alert_logs 
                        WHERE timestamp < ? AND resolved = 1
                    ''', (cutoff_time,))
                    
                    conn.commit()
                    
                    # VACUUM으로 데이터베이스 최적화
                    cursor.execute('VACUUM')
                    
            logger.info(f"Cleaned up monitoring data older than {hours} hours")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old monitoring data: {e}")
    
    def get_database_size(self) -> float:
        """데이터베이스 크기 조회 (MB)"""
        try:
            db_file = Path(self.db_path)
            if db_file.exists():
                return db_file.stat().st_size / (1024 * 1024)
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get database size: {e}")
            return 0.0


# 전역 모니터링 데이터베이스 인스턴스
_monitoring_db = None


def get_monitoring_database(db_path: str = "monitoring_data.db") -> MonitoringDatabase:
    """싱글톤 모니터링 데이터베이스 반환"""
    global _monitoring_db
    if _monitoring_db is None:
        _monitoring_db = MonitoringDatabase(db_path)
    return _monitoring_db