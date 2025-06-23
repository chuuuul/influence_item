"""
T05_S02_M02: 통합 에러 핸들링 시스템
포괄적인 에러 처리 및 복구 메커니즘
"""

import logging
import traceback
import sys
import os
import json
import streamlit as st
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Type, List
from functools import wraps
from pathlib import Path
import threading
from enum import Enum

# 커스텀 에러 클래스들
class SystemError(Exception):
    """시스템 전역 에러 기본 클래스"""
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "SYSTEM_ERROR"
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()


class DataIntegrityError(SystemError):
    """데이터 무결성 관련 에러"""
    def __init__(self, message: str, table: str = None, record_id: str = None):
        super().__init__(message, "DATA_INTEGRITY_ERROR", {
            "table": table,
            "record_id": record_id
        })


class ExternalServiceError(SystemError):
    """외부 서비스 연동 에러"""
    def __init__(self, message: str, service: str = None, status_code: int = None):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", {
            "service": service,
            "status_code": status_code
        })


class DatabaseError(SystemError):
    """데이터베이스 관련 에러"""
    def __init__(self, message: str, operation: str = None, table: str = None):
        super().__init__(message, "DATABASE_ERROR", {
            "operation": operation,
            "table": table
        })


class ValidationError(SystemError):
    """데이터 검증 에러"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, "VALIDATION_ERROR", {
            "field": field,
            "value": str(value) if value is not None else None
        })


class ErrorSeverity(Enum):
    """에러 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorHandler:
    """통합 에러 처리기"""
    
    def __init__(self, log_file: str = "error_log.jsonl"):
        """
        Args:
            log_file: 에러 로그 파일 경로
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # 에러 통계
        self.error_stats = {
            "total_errors": 0,
            "by_severity": {s.value: 0 for s in ErrorSeverity},
            "by_type": {},
            "last_reset": datetime.now().isoformat()
        }
        
        self._lock = threading.Lock()
        
        # 로거 설정
        self.logger = logging.getLogger("error_handler")
        self.logger.setLevel(logging.ERROR)
        
        # 파일 핸들러 추가
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file.with_suffix('.log'))
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def handle_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_message: str = None,
        recovery_action: Callable = None
    ) -> Dict[str, Any]:
        """
        에러 처리 및 로깅
        
        Args:
            error: 발생한 에러
            context: 에러 발생 컨텍스트 정보
            severity: 에러 심각도
            user_message: 사용자에게 표시할 메시지
            recovery_action: 복구 액션 함수
            
        Returns:
            에러 처리 결과
        """
        try:
            with self._lock:
                # 에러 정보 구성
                error_info = self._build_error_info(error, context, severity)
                
                # 사용자 메시지 설정
                if user_message:
                    error_info["user_message"] = user_message
                else:
                    error_info["user_message"] = self._generate_user_message(error, severity)
                
                # 에러 로깅
                self._log_error(error_info)
                
                # 통계 업데이트
                self._update_statistics(error_info)
                
                # 복구 액션 실행
                recovery_result = None
                if recovery_action:
                    try:
                        recovery_result = recovery_action()
                        error_info["recovery_executed"] = True
                        error_info["recovery_result"] = recovery_result
                    except Exception as recovery_error:
                        error_info["recovery_failed"] = True
                        error_info["recovery_error"] = str(recovery_error)
                        self.logger.error(f"Recovery action failed: {recovery_error}")
                
                # Streamlit에 에러 표시
                self._display_error_in_streamlit(error_info)
                
                return {
                    "success": True,
                    "error_id": error_info["error_id"],
                    "user_message": error_info["user_message"],
                    "severity": severity.value,
                    "recovery_executed": error_info.get("recovery_executed", False),
                    "recovery_result": recovery_result
                }
                
        except Exception as handler_error:
            # 에러 핸들러 자체에서 에러 발생
            fallback_message = f"Critical error in error handler: {handler_error}"
            self.logger.critical(fallback_message)
            
            if 'st' in sys.modules:
                st.error("🚨 시스템 오류가 발생했습니다. 관리자에게 문의해주세요.")
            
            return {
                "success": False,
                "error": fallback_message,
                "severity": "critical"
            }
    
    def _build_error_info(self, error: Exception, context: Dict[str, Any], severity: ErrorSeverity) -> Dict[str, Any]:
        """에러 정보 구성"""
        error_id = f"ERR_{int(datetime.now().timestamp() * 1000)}"
        
        # 스택 트레이스 정보
        tb_info = traceback.format_exception(type(error), error, error.__traceback__)
        
        error_info = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "severity": severity.value,
            "traceback": tb_info,
            "context": context or {},
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
                "working_directory": os.getcwd()
            }
        }
        
        # 커스텀 에러 클래스의 추가 정보
        if isinstance(error, SystemError):
            error_info["error_code"] = error.error_code
            error_info["details"] = error.details
        
        return error_info
    
    def _generate_user_message(self, error: Exception, severity: ErrorSeverity) -> str:
        """사용자 친화적 에러 메시지 생성"""
        if severity == ErrorSeverity.CRITICAL:
            return "🚨 심각한 시스템 오류가 발생했습니다. 즉시 관리자에게 문의해주세요."
        elif severity == ErrorSeverity.HIGH:
            return "⚠️ 중요한 오류가 발생했습니다. 작업을 중단하고 관리자에게 문의해주세요."
        elif severity == ErrorSeverity.MEDIUM:
            if isinstance(error, DatabaseError):
                return "💾 데이터베이스 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            elif isinstance(error, ExternalServiceError):
                return "🌐 외부 서비스 연결 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            elif isinstance(error, ValidationError):
                return f"📝 입력 데이터 오류: {error.message}"
            else:
                return "⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        else:  # LOW
            return "ℹ️ 일시적인 문제가 발생했습니다. 계속 진행할 수 있습니다."
    
    def _log_error(self, error_info: Dict[str, Any]):
        """에러 로깅"""
        # JSON Lines 형식으로 저장
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_info, ensure_ascii=False) + '\n')
        
        # 표준 로거에도 기록
        severity = error_info["severity"]
        message = f"[{error_info['error_id']}] {error_info['error_type']}: {error_info['error_message']}"
        
        if severity == "critical":
            self.logger.critical(message)
        elif severity == "high":
            self.logger.error(message)
        elif severity == "medium":
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def _update_statistics(self, error_info: Dict[str, Any]):
        """에러 통계 업데이트"""
        self.error_stats["total_errors"] += 1
        
        severity = error_info["severity"]
        self.error_stats["by_severity"][severity] += 1
        
        error_type = error_info["error_type"]
        if error_type not in self.error_stats["by_type"]:
            self.error_stats["by_type"][error_type] = 0
        self.error_stats["by_type"][error_type] += 1
    
    def _display_error_in_streamlit(self, error_info: Dict[str, Any]):
        """Streamlit에 에러 표시"""
        if 'st' not in sys.modules:
            return
        
        severity = error_info["severity"]
        user_message = error_info["user_message"]
        error_id = error_info["error_id"]
        
        if severity == "critical":
            st.error(f"{user_message}\n\n**에러 ID**: `{error_id}`")
            st.stop()
        elif severity == "high":
            st.error(f"{user_message}\n\n**에러 ID**: `{error_id}`")
        elif severity == "medium":
            st.warning(f"{user_message}\n\n**에러 ID**: `{error_id}`")
        else:
            st.info(f"{user_message}\n\n**에러 ID**: `{error_id}`")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """에러 통계 조회"""
        with self._lock:
            return self.error_stats.copy()
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 에러 목록 조회"""
        try:
            errors = []
            if not self.log_file.exists():
                return errors
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 최근 에러부터 반환
            for line in reversed(lines[-limit:]):
                try:
                    error_info = json.loads(line.strip())
                    errors.append(error_info)
                except json.JSONDecodeError:
                    continue
            
            return errors
            
        except Exception as e:
            self.logger.error(f"Failed to get recent errors: {e}")
            return []
    
    def clear_error_log(self) -> bool:
        """에러 로그 초기화"""
        try:
            with self._lock:
                if self.log_file.exists():
                    self.log_file.unlink()
                
                # 통계도 초기화
                self.error_stats = {
                    "total_errors": 0,
                    "by_severity": {s.value: 0 for s in ErrorSeverity},
                    "by_type": {},
                    "last_reset": datetime.now().isoformat()
                }
                
                self.logger.info("Error log cleared")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to clear error log: {e}")
            return False


def error_handler_decorator(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    user_message: str = None,
    recovery_action: Callable = None,
    reraise: bool = False
):
    """에러 핸들링 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler = get_error_handler()
                
                # 함수 정보를 컨텍스트에 추가
                context = {
                    "function": func.__name__,
                    "module": func.__module__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
                
                result = error_handler.handle_error(
                    error=e,
                    context=context,
                    severity=severity,
                    user_message=user_message,
                    recovery_action=recovery_action
                )
                
                if reraise and not result.get("recovery_executed"):
                    raise e
                
                return result
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    user_message: str = None,
    recovery_action: Callable = None,
    default_return: Any = None,
    **kwargs
) -> Any:
    """안전한 함수 실행"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_handler = get_error_handler()
        
        context = {
            "function": func.__name__ if hasattr(func, '__name__') else str(func),
            "args_count": len(args),
            "kwargs_keys": list(kwargs.keys())
        }
        
        error_handler.handle_error(
            error=e,
            context=context,
            severity=severity,
            user_message=user_message,
            recovery_action=recovery_action
        )
        
        return default_return


# 전역 에러 핸들러 인스턴스
_error_handler = None


def get_error_handler() -> ErrorHandler:
    """싱글톤 에러 핸들러 반환"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def setup_global_exception_handler():
    """전역 예외 처리기 설정"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Ctrl+C는 정상 처리
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_handler = get_error_handler()
        error_handler.handle_error(
            error=exc_value,
            context={"source": "global_exception_handler"},
            severity=ErrorSeverity.CRITICAL,
            user_message="예상치 못한 심각한 오류가 발생했습니다."
        )
    
    sys.excepthook = handle_exception