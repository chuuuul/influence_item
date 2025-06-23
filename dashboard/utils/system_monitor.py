"""
T05_S02_M02: 시스템 모니터링 및 헬스체크
실시간 시스템 상태 모니터링 및 알림 시스템
"""

import psutil
import sqlite3
import requests
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

# GPU 모니터링을 위한 임포트
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """헬스 상태"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


@dataclass
class HealthCheck:
    """헬스체크 결과"""
    component: str
    status: HealthStatus
    message: str
    response_time: float
    timestamp: datetime
    details: Dict[str, Any] = None


@dataclass
class GPUMetrics:
    """GPU 메트릭"""
    gpu_id: int
    name: str
    load: float
    memory_util: float
    memory_total: int
    memory_used: int
    memory_free: int
    temperature: float
    timestamp: datetime


@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available: int
    disk_percent: float
    disk_free: int
    active_connections: int
    uptime: float
    gpu_metrics: List[GPUMetrics] = None


class AlertManager:
    """알림 관리자"""
    
    def __init__(self):
        """알림 관리자 초기화"""
        self.alert_rules = {
            "cpu_high": {"threshold": 80, "enabled": True, "cooldown": 300},  # 5분
            "memory_high": {"threshold": 85, "enabled": True, "cooldown": 300},
            "disk_full": {"threshold": 90, "enabled": True, "cooldown": 600},  # 10분
            "database_error": {"threshold": 1, "enabled": True, "cooldown": 60},
            "external_service_down": {"threshold": 1, "enabled": True, "cooldown": 180}
        }
        
        self.last_alerts = {}  # 쿨다운 관리
        self._lock = threading.Lock()
    
    def should_send_alert(self, alert_type: str, current_value: float) -> bool:
        """알림을 보낼지 결정"""
        with self._lock:
            rule = self.alert_rules.get(alert_type)
            if not rule or not rule["enabled"]:
                return False
            
            # 임계값 확인
            if current_value < rule["threshold"]:
                return False
            
            # 쿨다운 확인
            last_alert_time = self.last_alerts.get(alert_type, 0)
            if time.time() - last_alert_time < rule["cooldown"]:
                return False
            
            # 알림 발송 기록
            self.last_alerts[alert_type] = time.time()
            return True
    
    def send_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """알림 발송"""
        try:
            alert_data = {
                "type": alert_type,
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "system": "influence_item_dashboard"
            }
            
            # 로그로 기록
            logger.warning(f"ALERT [{alert_type}]: {message}")
            
            # 향후 Slack/이메일 연동 지점
            # self._send_slack_alert(alert_data)
            # self._send_email_alert(alert_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False


class SystemMonitor:
    """시스템 모니터링 관리자"""
    
    def __init__(self, metrics_file: str = "system_metrics.jsonl"):
        """
        Args:
            metrics_file: 메트릭 저장 파일
        """
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(exist_ok=True)
        
        self.alert_manager = AlertManager()
        self.is_monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 60  # 1분 간격
        
        # 헬스체크 컴포넌트들
        self.health_checkers = {
            "database": self._check_database_health,
            "disk_space": self._check_disk_health,
            "memory": self._check_memory_health,
            "cpu": self._check_cpu_health,
            "gpu": self._check_gpu_health,
            "external_services": self._check_external_services_health
        }
        
        self._lock = threading.Lock()
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self.is_monitoring:
            logger.info("Monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                # 시스템 메트릭 수집
                metrics = self._collect_system_metrics()
                
                # 메트릭 저장
                self._save_metrics(metrics)
                
                # 알림 확인
                self._check_alerts(metrics)
                
                # 다음 주기까지 대기
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)  # 에러 시 짧은 대기 후 재시도
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 정보
            memory = psutil.virtual_memory()
            
            # 디스크 정보
            disk = psutil.disk_usage('/')
            
            # 네트워크 연결 수 (권한 문제 시 기본값 사용)
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, OSError):
                connections = 0
            
            # 시스템 업타임
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            # GPU 메트릭 수집
            gpu_metrics = self._collect_gpu_metrics()
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available=memory.available,
                disk_percent=disk.used / disk.total * 100,
                disk_free=disk.free,
                active_connections=connections,
                uptime=uptime,
                gpu_metrics=gpu_metrics
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return None
    
    def _collect_gpu_metrics(self) -> List[GPUMetrics]:
        """GPU 메트릭 수집"""
        if not GPU_AVAILABLE:
            return []
        
        try:
            gpus = GPUtil.getGPUs()
            gpu_metrics = []
            
            for gpu in gpus:
                metrics = GPUMetrics(
                    gpu_id=gpu.id,
                    name=gpu.name,
                    load=gpu.load * 100,  # 백분율로 변환
                    memory_util=gpu.memoryUtil * 100,  # 백분율로 변환
                    memory_total=gpu.memoryTotal,
                    memory_used=gpu.memoryUsed,
                    memory_free=gpu.memoryFree,
                    temperature=gpu.temperature,
                    timestamp=datetime.now()
                )
                gpu_metrics.append(metrics)
            
            return gpu_metrics
            
        except Exception as e:
            logger.error(f"Failed to collect GPU metrics: {e}")
            return []
    
    def _save_metrics(self, metrics: SystemMetrics):
        """메트릭 저장"""
        if not metrics:
            return
        
        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                metrics_dict = asdict(metrics)
                metrics_dict['timestamp'] = metrics.timestamp.isoformat()
                f.write(json.dumps(metrics_dict, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def _check_alerts(self, metrics: SystemMetrics):
        """알림 확인 및 발송"""
        if not metrics:
            return
        
        # CPU 사용률 확인
        if self.alert_manager.should_send_alert("cpu_high", metrics.cpu_percent):
            self.alert_manager.send_alert(
                "cpu_high",
                f"높은 CPU 사용률 감지: {metrics.cpu_percent:.1f}%",
                "warning"
            )
        
        # 메모리 사용률 확인
        if self.alert_manager.should_send_alert("memory_high", metrics.memory_percent):
            self.alert_manager.send_alert(
                "memory_high",
                f"높은 메모리 사용률 감지: {metrics.memory_percent:.1f}%",
                "warning"
            )
        
        # 디스크 사용률 확인
        if self.alert_manager.should_send_alert("disk_full", metrics.disk_percent):
            self.alert_manager.send_alert(
                "disk_full",
                f"디스크 공간 부족: {metrics.disk_percent:.1f}% 사용 중",
                "critical"
            )
    
    def get_health_status(self) -> Dict[str, HealthCheck]:
        """전체 시스템 헬스 상태 조회"""
        health_results = {}
        
        for component, checker in self.health_checkers.items():
            try:
                start_time = time.time()
                result = checker()
                response_time = (time.time() - start_time) * 1000  # ms
                
                if isinstance(result, HealthCheck):
                    result.response_time = response_time
                    health_results[component] = result
                else:
                    # 결과가 HealthCheck 객체가 아닌 경우 변환
                    health_results[component] = HealthCheck(
                        component=component,
                        status=HealthStatus.HEALTHY if result else HealthStatus.CRITICAL,
                        message="Health check completed",
                        response_time=response_time,
                        timestamp=datetime.now(),
                        details=result if isinstance(result, dict) else None
                    )
                    
            except Exception as e:
                health_results[component] = HealthCheck(
                    component=component,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check failed: {str(e)}",
                    response_time=0,
                    timestamp=datetime.now()
                )
                logger.error(f"Health check failed for {component}: {e}")
        
        return health_results
    
    def _check_database_health(self) -> HealthCheck:
        """데이터베이스 헬스 확인"""
        try:
            conn = sqlite3.connect("influence_item.db", timeout=5)
            
            # 간단한 쿼리 실행
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # 무결성 검사
            cursor = conn.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            conn.close()
            
            if integrity_result == "ok":
                return HealthCheck(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message=f"Database is healthy with {table_count} tables",
                    response_time=0,  # 나중에 설정됨
                    timestamp=datetime.now(),
                    details={
                        "table_count": table_count,
                        "integrity": integrity_result
                    }
                )
            else:
                return HealthCheck(
                    component="database",
                    status=HealthStatus.CRITICAL,
                    message=f"Database integrity check failed: {integrity_result}",
                    response_time=0,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return HealthCheck(
                component="database",
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def _check_disk_health(self) -> HealthCheck:
        """디스크 헬스 확인"""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.used / disk.total * 100
            
            if disk_percent > 90:
                status = HealthStatus.CRITICAL
                message = f"Disk space critically low: {disk_percent:.1f}% used"
            elif disk_percent > 80:
                status = HealthStatus.WARNING
                message = f"Disk space running low: {disk_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space healthy: {disk_percent:.1f}% used"
            
            return HealthCheck(
                component="disk_space",
                status=status,
                message=message,
                response_time=0,
                timestamp=datetime.now(),
                details={
                    "total_gb": round(disk.total / 1024**3, 2),
                    "used_gb": round(disk.used / 1024**3, 2),
                    "free_gb": round(disk.free / 1024**3, 2),
                    "percent_used": disk_percent
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="disk_space",
                status=HealthStatus.CRITICAL,
                message=f"Disk check failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def _check_memory_health(self) -> HealthCheck:
        """메모리 헬스 확인"""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                status = HealthStatus.CRITICAL
                message = f"Memory usage critically high: {memory.percent:.1f}%"
            elif memory.percent > 80:
                status = HealthStatus.WARNING
                message = f"Memory usage high: {memory.percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory.percent:.1f}%"
            
            return HealthCheck(
                component="memory",
                status=status,
                message=message,
                response_time=0,
                timestamp=datetime.now(),
                details={
                    "total_gb": round(memory.total / 1024**3, 2),
                    "available_gb": round(memory.available / 1024**3, 2),
                    "used_gb": round(memory.used / 1024**3, 2),
                    "percent_used": memory.percent
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="memory",
                status=HealthStatus.CRITICAL,
                message=f"Memory check failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def _check_cpu_health(self) -> HealthCheck:
        """CPU 헬스 확인"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > 90:
                status = HealthStatus.CRITICAL
                message = f"CPU usage critically high: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.WARNING
                message = f"CPU usage high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"
            
            return HealthCheck(
                component="cpu",
                status=status,
                message=message,
                response_time=0,
                timestamp=datetime.now(),
                details={
                    "cpu_count": psutil.cpu_count(),
                    "cpu_percent": cpu_percent,
                    "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="cpu",
                status=HealthStatus.CRITICAL,
                message=f"CPU check failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def _check_gpu_health(self) -> HealthCheck:
        """GPU 헬스 확인"""
        if not GPU_AVAILABLE:
            return HealthCheck(
                component="gpu",
                status=HealthStatus.WARNING,
                message="GPU monitoring not available (GPUtil not installed)",
                response_time=0,
                timestamp=datetime.now()
            )
        
        try:
            gpus = GPUtil.getGPUs()
            
            if not gpus:
                return HealthCheck(
                    component="gpu",
                    status=HealthStatus.WARNING,
                    message="No GPUs detected",
                    response_time=0,
                    timestamp=datetime.now()
                )
            
            gpu_details = []
            overall_status = HealthStatus.HEALTHY
            messages = []
            
            for gpu in gpus:
                gpu_load = gpu.load * 100
                gpu_memory = gpu.memoryUtil * 100
                gpu_temp = gpu.temperature
                
                gpu_status = HealthStatus.HEALTHY
                gpu_message = f"GPU {gpu.id} ({gpu.name}): Normal"
                
                # GPU 로드 확인
                if gpu_load > 95:
                    gpu_status = HealthStatus.CRITICAL
                    gpu_message = f"GPU {gpu.id}: Critical load {gpu_load:.1f}%"
                    overall_status = HealthStatus.CRITICAL
                elif gpu_load > 85:
                    gpu_status = HealthStatus.WARNING
                    gpu_message = f"GPU {gpu.id}: High load {gpu_load:.1f}%"
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.WARNING
                
                # GPU 메모리 확인
                if gpu_memory > 95:
                    gpu_status = HealthStatus.CRITICAL
                    gpu_message = f"GPU {gpu.id}: Critical memory {gpu_memory:.1f}%"
                    overall_status = HealthStatus.CRITICAL
                elif gpu_memory > 85:
                    gpu_status = HealthStatus.WARNING
                    gpu_message = f"GPU {gpu.id}: High memory {gpu_memory:.1f}%"
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.WARNING
                
                # GPU 온도 확인
                if gpu_temp > 85:
                    gpu_status = HealthStatus.CRITICAL
                    gpu_message = f"GPU {gpu.id}: Critical temperature {gpu_temp}°C"
                    overall_status = HealthStatus.CRITICAL
                elif gpu_temp > 75:
                    gpu_status = HealthStatus.WARNING
                    gpu_message = f"GPU {gpu.id}: High temperature {gpu_temp}°C"
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.WARNING
                
                gpu_details.append({
                    "id": gpu.id,
                    "name": gpu.name,
                    "load_percent": gpu_load,
                    "memory_percent": gpu_memory,
                    "memory_total_mb": gpu.memoryTotal,
                    "memory_used_mb": gpu.memoryUsed,
                    "temperature_c": gpu_temp,
                    "status": gpu_status.value
                })
                
                messages.append(gpu_message)
            
            summary_message = f"{len(gpus)} GPU(s) detected. " + "; ".join(messages)
            
            return HealthCheck(
                component="gpu",
                status=overall_status,
                message=summary_message,
                response_time=0,
                timestamp=datetime.now(),
                details={
                    "gpu_count": len(gpus),
                    "gpus": gpu_details
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="gpu",
                status=HealthStatus.CRITICAL,
                message=f"GPU health check failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def _check_external_services_health(self) -> HealthCheck:
        """외부 서비스 헬스 확인"""
        try:
            # 향후 외부 API 연동 시 확장 가능
            external_services = [
                {"name": "Google", "url": "https://www.google.com", "timeout": 5},
                # {"name": "Coupang API", "url": "...", "timeout": 10},
                # {"name": "Gemini API", "url": "...", "timeout": 10}
            ]
            
            service_statuses = []
            overall_status = HealthStatus.HEALTHY
            
            for service in external_services:
                try:
                    response = requests.get(service["url"], timeout=service["timeout"])
                    if response.status_code == 200:
                        service_statuses.append({
                            "name": service["name"],
                            "status": "healthy",
                            "response_time": response.elapsed.total_seconds() * 1000
                        })
                    else:
                        service_statuses.append({
                            "name": service["name"],
                            "status": "warning",
                            "status_code": response.status_code
                        })
                        overall_status = HealthStatus.WARNING
                        
                except requests.RequestException as e:
                    service_statuses.append({
                        "name": service["name"],
                        "status": "critical",
                        "error": str(e)
                    })
                    overall_status = HealthStatus.CRITICAL
            
            healthy_count = sum(1 for s in service_statuses if s["status"] == "healthy")
            total_count = len(service_statuses)
            
            return HealthCheck(
                component="external_services",
                status=overall_status,
                message=f"External services: {healthy_count}/{total_count} healthy",
                response_time=0,
                timestamp=datetime.now(),
                details={
                    "services": service_statuses,
                    "healthy_count": healthy_count,
                    "total_count": total_count
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="external_services",
                status=HealthStatus.CRITICAL,
                message=f"External services check failed: {str(e)}",
                response_time=0,
                timestamp=datetime.now()
            )
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """메트릭 요약 정보 조회"""
        try:
            if not self.metrics_file.exists():
                return {"error": "No metrics data available"}
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            metrics_data = []
            
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        timestamp = datetime.fromisoformat(data['timestamp'])
                        if timestamp >= cutoff_time:
                            metrics_data.append(data)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
            if not metrics_data:
                return {"error": "No recent metrics data"}
            
            # 통계 계산
            cpu_values = [m['cpu_percent'] for m in metrics_data]
            memory_values = [m['memory_percent'] for m in metrics_data]
            disk_values = [m['disk_percent'] for m in metrics_data]
            
            return {
                "period_hours": hours,
                "data_points": len(metrics_data),
                "cpu": {
                    "avg": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values)
                },
                "memory": {
                    "avg": sum(memory_values) / len(memory_values),
                    "max": max(memory_values),
                    "min": min(memory_values)
                },
                "disk": {
                    "avg": sum(disk_values) / len(disk_values),
                    "max": max(disk_values),
                    "min": min(disk_values)
                },
                "latest_metrics": metrics_data[-1] if metrics_data else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {"error": str(e)}


# 전역 시스템 모니터 인스턴스
_system_monitor = None


def get_system_monitor() -> SystemMonitor:
    """싱글톤 시스템 모니터 반환"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor