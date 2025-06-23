"""
T04_S02_M02: 성능 모니터링 도구
대시보드 성능 최적화를 위한 모니터링 및 분석 도구
"""

import time
import psutil
import gc
import streamlit as st
from typing import Dict, Any, List
from datetime import datetime
from functools import wraps
import threading
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self):
        self.metrics = []
        self.start_time = time.time()
        self._lock = threading.Lock()
        
    def track_metric(self, name: str, value: float, unit: str = "ms"):
        """메트릭 추가"""
        with self._lock:
            self.metrics.append({
                "name": name,
                "value": value,
                "unit": unit,
                "timestamp": time.time()
            })
            
    def get_system_info(self) -> Dict[str, Any]:
        """시스템 리소스 정보 조회"""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """메트릭 요약 정보"""
        if not self.metrics:
            return {}
            
        with self._lock:
            total_metrics = len(self.metrics)
            recent_metrics = [m for m in self.metrics if time.time() - m["timestamp"] < 3600]  # 1시간 이내
            
            # 평균 로딩 시간 계산
            loading_times = [m["value"] for m in recent_metrics if "loading" in m["name"].lower()]
            avg_loading_time = sum(loading_times) / len(loading_times) if loading_times else 0
            
            return {
                "total_metrics": total_metrics,
                "recent_metrics": len(recent_metrics),
                "avg_loading_time": avg_loading_time,
                "metrics": recent_metrics[-10:],  # 최근 10개
                "uptime": time.time() - self.start_time
            }
    
    def force_garbage_collection(self):
        """강제 가비지 컬렉션"""
        gc.collect()
        collected = gc.collect()
        self.track_metric("garbage_collection", collected, "objects")
        return collected


# 전역 모니터 인스턴스
_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 인스턴스 반환"""
    return _monitor


def monitor_performance(func_name: str = None):
    """성능 모니터링 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                _monitor.track_metric(f"{name}_execution", execution_time)
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                _monitor.track_metric(f"{name}_error", execution_time)
                raise e
                
        return wrapper
    return decorator


@st.cache_data(ttl=60)
def get_cached_system_metrics() -> Dict[str, Any]:
    """캐시된 시스템 메트릭"""
    return _monitor.get_system_info()


def display_performance_metrics():
    """Streamlit에서 성능 메트릭 표시"""
    try:
        metrics = _monitor.get_metrics_summary()
        system_info = get_cached_system_metrics()
        
        if not metrics and not system_info:
            st.info("성능 데이터를 수집 중입니다...")
            return
        
        # 시스템 리소스 상태
        if system_info:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "메모리 사용률",
                    f"{system_info.get('memory', {}).get('percent', 0):.1f}%",
                    help="시스템 메모리 사용률"
                )
                
            with col2:
                st.metric(
                    "CPU 사용률", 
                    f"{system_info.get('cpu', {}).get('percent', 0):.1f}%",
                    help="시스템 CPU 사용률"
                )
        
        # 성능 메트릭
        if metrics:
            st.subheader("🚀 성능 메트릭")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "평균 로딩 시간",
                    f"{metrics.get('avg_loading_time', 0):.1f}ms",
                    help="최근 1시간 평균 로딩 시간"
                )
                
            with col2:
                st.metric(
                    "업타임",
                    f"{metrics.get('uptime', 0) / 3600:.1f}h",
                    help="시스템 가동 시간"
                )
                
            with col3:
                st.metric(
                    "최근 메트릭",
                    metrics.get('recent_metrics', 0),
                    help="최근 1시간 수집된 메트릭 수"
                )
        
        # 가비지 컬렉션 버튼
        if st.button("🧹 메모리 정리", help="가비지 컬렉션 실행"):
            collected = _monitor.force_garbage_collection()
            st.success(f"메모리 정리 완료: {collected}개 객체 해제")
            st.rerun()
            
    except Exception as e:
        st.error(f"성능 메트릭 표시 중 오류: {e}")


def optimize_streamlit_config():
    """Streamlit 성능 최적화 설정"""
    try:
        # 세션 상태 정리
        cleanup_session_state()
        
        # 메모리 사용량 체크
        memory_info = psutil.virtual_memory()
        if memory_info.percent > 80:
            logger.warning(f"High memory usage: {memory_info.percent}%")
            gc.collect()
            
        # CPU 사용량 체크
        cpu_percent = psutil.cpu_percent()
        if cpu_percent > 80:
            logger.warning(f"High CPU usage: {cpu_percent}%")
            
    except Exception as e:
        logger.error(f"Failed to optimize Streamlit config: {e}")


def cleanup_session_state():
    """세션 상태 정리"""
    try:
        # 오래된 임시 데이터 정리
        keys_to_remove = []
        for key in st.session_state:
            if key.startswith('temp_') or key.startswith('cache_'):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
            
        logger.info(f"Cleaned up {len(keys_to_remove)} session state keys")
        
    except Exception as e:
        logger.error(f"Failed to cleanup session state: {e}")


@monitor_performance("page_load")
def measure_page_load_time(page_name: str):
    """페이지 로딩 시간 측정"""
    start_time = time.time()
    
    def end_measurement():
        load_time = (time.time() - start_time) * 1000
        _monitor.track_metric(f"page_load_{page_name}", load_time)
        return load_time
    
    return end_measurement


def check_performance_thresholds() -> Dict[str, bool]:
    """성능 임계값 확인"""
    try:
        system_info = _monitor.get_system_info()
        metrics = _monitor.get_metrics_summary()
        
        checks = {
            "memory_ok": system_info.get('memory', {}).get('percent', 0) < 80,
            "cpu_ok": system_info.get('cpu', {}).get('percent', 0) < 80,
            "loading_time_ok": metrics.get('avg_loading_time', 0) < 2000,  # 2초 이내
        }
        
        return checks
        
    except Exception as e:
        logger.error(f"Failed to check performance thresholds: {e}")
        return {"memory_ok": True, "cpu_ok": True, "loading_time_ok": True}


def log_performance_warning(metric_name: str, value: float, threshold: float):
    """성능 경고 로깅"""
    if value > threshold:
        logger.warning(f"Performance warning: {metric_name} = {value} (threshold: {threshold})")
        _monitor.track_metric(f"warning_{metric_name}", value)