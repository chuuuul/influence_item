"""
T01_S03_M03: 네트워크 및 API 모니터링
네트워크 트래픽 및 API 응답 시간 모니터링 시스템
"""

import requests
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading
import json
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class NetworkMetrics:
    """네트워크 메트릭"""
    timestamp: datetime
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    connections_established: int
    connections_listening: int
    network_io_read_speed: float  # MB/s
    network_io_write_speed: float  # MB/s


@dataclass
class APIMetrics:
    """API 메트릭"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time: float
    request_size: int
    response_size: int
    success: bool
    error_message: Optional[str]


@dataclass
class APIEndpointStats:
    """API 엔드포인트 통계"""
    endpoint: str
    total_requests: int
    success_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    success_rate: float
    last_request: datetime


class NetworkMonitor:
    """네트워크 및 API 모니터링 관리자"""
    
    def __init__(self):
        self.network_history = deque(maxlen=1440)  # 24시간 (1분마다)
        self.api_history = deque(maxlen=10000)  # 최근 10000개 API 요청
        self.api_endpoints = defaultdict(list)
        self._lock = threading.Lock()
        
        # 이전 네트워크 통계 (속도 계산용)
        self._last_network_stats = None
        self._last_network_time = None
        
        # 모니터링할 API 엔드포인트 목록
        self.monitored_apis = [
            {
                'name': 'Google API Test',
                'url': 'https://www.google.com',
                'method': 'GET',
                'timeout': 10,
                'interval': 300  # 5분마다
            },
            {
                'name': 'Local Dashboard Health',
                'url': 'http://localhost:8501',
                'method': 'GET',
                'timeout': 5,
                'interval': 60  # 1분마다
            }
        ]
        
        # API 마지막 체크 시간
        self._last_api_checks = {}
    
    def collect_network_metrics(self) -> NetworkMetrics:
        """네트워크 메트릭 수집"""
        try:
            # 네트워크 통계 수집
            net_io = psutil.net_io_counters()
            
            # 네트워크 연결 정보 (권한 문제 시 기본값 사용)
            try:
                connections = psutil.net_connections()
            except (psutil.AccessDenied, OSError):
                connections = []
            
            current_time = time.time()
            
            # 연결 상태별 카운트
            established_count = sum(1 for conn in connections if conn.status == 'ESTABLISHED')
            listening_count = sum(1 for conn in connections if conn.status == 'LISTEN')
            
            # 네트워크 속도 계산
            read_speed = 0.0
            write_speed = 0.0
            
            if self._last_network_stats and self._last_network_time:
                time_diff = current_time - self._last_network_time
                if time_diff > 0:
                    bytes_read_diff = net_io.bytes_recv - self._last_network_stats.bytes_recv
                    bytes_write_diff = net_io.bytes_sent - self._last_network_stats.bytes_sent
                    
                    read_speed = (bytes_read_diff / time_diff) / (1024 * 1024)  # MB/s
                    write_speed = (bytes_write_diff / time_diff) / (1024 * 1024)  # MB/s
            
            metrics = NetworkMetrics(
                timestamp=datetime.now(),
                bytes_sent=net_io.bytes_sent,
                bytes_recv=net_io.bytes_recv,
                packets_sent=net_io.packets_sent,
                packets_recv=net_io.packets_recv,
                connections_established=established_count,
                connections_listening=listening_count,
                network_io_read_speed=max(0, read_speed),
                network_io_write_speed=max(0, write_speed)
            )
            
            # 이전 통계 업데이트
            self._last_network_stats = net_io
            self._last_network_time = current_time
            
            # 히스토리에 추가
            with self._lock:
                self.network_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect network metrics: {e}")
            return None
    
    def monitor_api_endpoint(self, url: str, method: str = 'GET', 
                           timeout: int = 10, headers: Dict = None,
                           data: Any = None) -> APIMetrics:
        """API 엔드포인트 모니터링"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            # 요청 크기 계산
            request_size = 0
            if data:
                if isinstance(data, (dict, list)):
                    request_size = len(json.dumps(data).encode('utf-8'))
                elif isinstance(data, str):
                    request_size = len(data.encode('utf-8'))
                elif isinstance(data, bytes):
                    request_size = len(data)
            
            # HTTP 요청 실행
            response = requests.request(
                method=method,
                url=url,
                timeout=timeout,
                headers=headers or {},
                data=data
            )
            
            response_time = (time.time() - start_time) * 1000  # ms
            response_size = len(response.content) if response.content else 0
            
            success = 200 <= response.status_code < 400
            error_message = None if success else f"HTTP {response.status_code}"
            
            metrics = APIMetrics(
                timestamp=timestamp,
                endpoint=url,
                method=method,
                status_code=response.status_code,
                response_time=response_time,
                request_size=request_size,
                response_size=response_size,
                success=success,
                error_message=error_message
            )
            
        except requests.exceptions.Timeout:
            response_time = timeout * 1000
            metrics = APIMetrics(
                timestamp=timestamp,
                endpoint=url,
                method=method,
                status_code=0,
                response_time=response_time,
                request_size=request_size if 'request_size' in locals() else 0,
                response_size=0,
                success=False,
                error_message="Request timeout"
            )
            
        except requests.exceptions.ConnectionError:
            response_time = (time.time() - start_time) * 1000
            metrics = APIMetrics(
                timestamp=timestamp,
                endpoint=url,
                method=method,
                status_code=0,
                response_time=response_time,
                request_size=request_size if 'request_size' in locals() else 0,
                response_size=0,
                success=False,
                error_message="Connection error"
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            metrics = APIMetrics(
                timestamp=timestamp,
                endpoint=url,
                method=method,
                status_code=0,
                response_time=response_time,
                request_size=request_size if 'request_size' in locals() else 0,
                response_size=0,
                success=False,
                error_message=str(e)
            )
        
        # 히스토리에 추가
        with self._lock:
            self.api_history.append(metrics)
            self.api_endpoints[url].append(metrics)
            
            # 엔드포인트별 최근 1000개만 유지
            if len(self.api_endpoints[url]) > 1000:
                self.api_endpoints[url] = self.api_endpoints[url][-1000:]
        
        return metrics
    
    def check_monitored_apis(self) -> List[APIMetrics]:
        """모니터링 대상 API들을 주기적으로 체크"""
        results = []
        current_time = time.time()
        
        for api_config in self.monitored_apis:
            url = api_config['url']
            interval = api_config.get('interval', 300)
            
            # 마지막 체크 시간 확인
            last_check = self._last_api_checks.get(url, 0)
            if current_time - last_check < interval:
                continue
            
            try:
                metrics = self.monitor_api_endpoint(
                    url=url,
                    method=api_config.get('method', 'GET'),
                    timeout=api_config.get('timeout', 10)
                )
                results.append(metrics)
                self._last_api_checks[url] = current_time
                
            except Exception as e:
                logger.error(f"Failed to check API {url}: {e}")
        
        return results
    
    def get_network_summary(self, hours: int = 24) -> Dict[str, Any]:
        """네트워크 요약 정보"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with self._lock:
                recent_metrics = [m for m in self.network_history 
                               if m.timestamp > cutoff_time]
            
            if not recent_metrics:
                return {"error": "No recent network data available"}
            
            # 통계 계산
            latest = recent_metrics[-1]
            first = recent_metrics[0]
            
            total_bytes_sent = latest.bytes_sent - first.bytes_sent
            total_bytes_recv = latest.bytes_recv - first.bytes_recv
            total_packets_sent = latest.packets_sent - first.packets_sent
            total_packets_recv = latest.packets_recv - first.packets_recv
            
            avg_connections = sum(m.connections_established for m in recent_metrics) / len(recent_metrics)
            max_connections = max(m.connections_established for m in recent_metrics)
            
            avg_read_speed = sum(m.network_io_read_speed for m in recent_metrics) / len(recent_metrics)
            avg_write_speed = sum(m.network_io_write_speed for m in recent_metrics) / len(recent_metrics)
            max_read_speed = max(m.network_io_read_speed for m in recent_metrics)
            max_write_speed = max(m.network_io_write_speed for m in recent_metrics)
            
            return {
                'period_hours': hours,
                'data_points': len(recent_metrics),
                'traffic_summary': {
                    'total_bytes_sent_mb': round(total_bytes_sent / (1024 * 1024), 2),
                    'total_bytes_recv_mb': round(total_bytes_recv / (1024 * 1024), 2),
                    'total_packets_sent': total_packets_sent,
                    'total_packets_recv': total_packets_recv
                },
                'connection_stats': {
                    'current_established': latest.connections_established,
                    'current_listening': latest.connections_listening,
                    'avg_established': round(avg_connections, 1),
                    'max_established': max_connections
                },
                'speed_stats': {
                    'avg_read_speed_mbps': round(avg_read_speed, 3),
                    'avg_write_speed_mbps': round(avg_write_speed, 3),
                    'max_read_speed_mbps': round(max_read_speed, 3),
                    'max_write_speed_mbps': round(max_write_speed, 3)
                },
                'latest_metrics': asdict(latest)
            }
            
        except Exception as e:
            logger.error(f"Failed to get network summary: {e}")
            return {"error": str(e)}
    
    def get_api_summary(self, hours: int = 24) -> Dict[str, Any]:
        """API 요약 정보"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with self._lock:
                recent_api_calls = [m for m in self.api_history 
                                  if m.timestamp > cutoff_time]
            
            if not recent_api_calls:
                return {"error": "No recent API data available"}
            
            # 전체 통계
            total_requests = len(recent_api_calls)
            successful_requests = sum(1 for call in recent_api_calls if call.success)
            failed_requests = total_requests - successful_requests
            success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
            
            # 응답 시간 통계
            response_times = [call.response_time for call in recent_api_calls]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            min_response_time = min(response_times) if response_times else 0
            max_response_time = max(response_times) if response_times else 0
            
            # 엔드포인트별 통계
            endpoint_stats = {}
            endpoints = set(call.endpoint for call in recent_api_calls)
            
            for endpoint in endpoints:
                endpoint_calls = [call for call in recent_api_calls if call.endpoint == endpoint]
                endpoint_successful = sum(1 for call in endpoint_calls if call.success)
                endpoint_response_times = [call.response_time for call in endpoint_calls]
                
                endpoint_stats[endpoint] = APIEndpointStats(
                    endpoint=endpoint,
                    total_requests=len(endpoint_calls),
                    success_requests=endpoint_successful,
                    failed_requests=len(endpoint_calls) - endpoint_successful,
                    avg_response_time=sum(endpoint_response_times) / len(endpoint_response_times),
                    min_response_time=min(endpoint_response_times),
                    max_response_time=max(endpoint_response_times),
                    success_rate=(endpoint_successful / len(endpoint_calls)) * 100,
                    last_request=max(call.timestamp for call in endpoint_calls)
                )
            
            # 상태 코드별 통계
            status_code_stats = defaultdict(int)
            for call in recent_api_calls:
                status_code_stats[call.status_code] += 1
            
            # 에러 분석
            error_analysis = defaultdict(int)
            for call in recent_api_calls:
                if not call.success and call.error_message:
                    error_analysis[call.error_message] += 1
            
            return {
                'period_hours': hours,
                'overall_stats': {
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'failed_requests': failed_requests,
                    'success_rate': round(success_rate, 2),
                    'avg_response_time': round(avg_response_time, 2),
                    'min_response_time': round(min_response_time, 2),
                    'max_response_time': round(max_response_time, 2)
                },
                'endpoint_stats': {
                    endpoint: asdict(stats) for endpoint, stats in endpoint_stats.items()
                },
                'status_code_distribution': dict(status_code_stats),
                'error_analysis': dict(error_analysis),
                'recent_failures': [
                    {
                        'endpoint': call.endpoint,
                        'timestamp': call.timestamp.isoformat(),
                        'error': call.error_message,
                        'response_time': call.response_time
                    }
                    for call in recent_api_calls[-10:] if not call.success
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get API summary: {e}")
            return {"error": str(e)}
    
    def get_real_time_network_stats(self) -> Dict[str, Any]:
        """실시간 네트워크 통계"""
        try:
            current_metrics = self.collect_network_metrics()
            if not current_metrics:
                return {"error": "Failed to collect current network metrics"}
            
            # 최근 5분간 API 통계
            recent_time = datetime.now() - timedelta(minutes=5)
            recent_api_calls = [call for call in self.api_history if call.timestamp > recent_time]
            
            return {
                'timestamp': current_metrics.timestamp.isoformat(),
                'network': {
                    'connections_established': current_metrics.connections_established,
                    'connections_listening': current_metrics.connections_listening,
                    'read_speed_mbps': current_metrics.network_io_read_speed,
                    'write_speed_mbps': current_metrics.network_io_write_speed,
                    'total_bytes_sent_gb': round(current_metrics.bytes_sent / (1024**3), 3),
                    'total_bytes_recv_gb': round(current_metrics.bytes_recv / (1024**3), 3)
                },
                'api': {
                    'recent_calls_5min': len(recent_api_calls),
                    'recent_success_rate': (
                        sum(1 for call in recent_api_calls if call.success) / len(recent_api_calls) * 100
                        if recent_api_calls else 100
                    ),
                    'avg_response_time_5min': (
                        sum(call.response_time for call in recent_api_calls) / len(recent_api_calls)
                        if recent_api_calls else 0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time network stats: {e}")
            return {"error": str(e)}


# 전역 네트워크 모니터 인스턴스
_network_monitor = None


def get_network_monitor() -> NetworkMonitor:
    """싱글톤 네트워크 모니터 반환"""
    global _network_monitor
    if _network_monitor is None:
        _network_monitor = NetworkMonitor()
    return _network_monitor


# API 호출을 자동으로 모니터링하는 데코레이터
def monitor_api_call(endpoint_name: str = None):
    """API 호출 모니터링 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_network_monitor()
            
            # endpoint_name이 없으면 함수 이름 사용
            endpoint = endpoint_name or func.__name__
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000  # ms
                
                # 성공 메트릭 기록
                metrics = APIMetrics(
                    timestamp=datetime.now(),
                    endpoint=endpoint,
                    method="INTERNAL",
                    status_code=200,
                    response_time=response_time,
                    request_size=0,
                    response_size=0,
                    success=True,
                    error_message=None
                )
                
                with monitor._lock:
                    monitor.api_history.append(metrics)
                
                return result
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000  # ms
                
                # 실패 메트릭 기록
                metrics = APIMetrics(
                    timestamp=datetime.now(),
                    endpoint=endpoint,
                    method="INTERNAL",
                    status_code=500,
                    response_time=response_time,
                    request_size=0,
                    response_size=0,
                    success=False,
                    error_message=str(e)
                )
                
                with monitor._lock:
                    monitor.api_history.append(metrics)
                
                raise e
                
        return wrapper
    return decorator