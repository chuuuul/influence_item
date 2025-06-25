
import logging
import logging.handlers
import os
import json
from datetime import datetime
from typing import Any, Dict

class SecurityLogger:
    """보안 강화된 로거"""
    
    def __init__(self):
        self.setup_loggers()
    
    def setup_loggers(self):
        """로거 설정"""
        
        # 보안 이벤트 로거
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(logging.INFO)
        
        # 로그 파일 핸들러 (회전)
        security_handler = logging.handlers.RotatingFileHandler(
            'logs/security.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        
        # 보안 로그 포맷
        security_format = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(security_format)
        
        self.security_logger.addHandler(security_handler)
        
        # API 접근 로거
        self.api_logger = logging.getLogger('api_access')
        self.api_logger.setLevel(logging.INFO)
        
        api_handler = logging.handlers.RotatingFileHandler(
            'logs/api_access.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        
        api_format = logging.Formatter(
            '%(asctime)s - API - %(message)s'
        )
        api_handler.setFormatter(api_format)
        
        self.api_logger.addHandler(api_handler)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          severity: str = 'INFO'):
        """보안 이벤트 로깅"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        if severity == 'CRITICAL':
            self.security_logger.critical(json.dumps(log_entry))
        elif severity == 'WARNING':
            self.security_logger.warning(json.dumps(log_entry))
        else:
            self.security_logger.info(json.dumps(log_entry))
    
    def log_api_access(self, method: str, endpoint: str, ip: str, 
                      user_agent: str, status_code: int, 
                      response_time: float):
        """API 접근 로깅"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'endpoint': endpoint,
            'client_ip': ip,
            'user_agent': user_agent,
            'status_code': status_code,
            'response_time': response_time
        }
        
        self.api_logger.info(json.dumps(log_entry))
    
    def log_authentication_attempt(self, ip: str, success: bool, 
                                 user_id: str = None):
        """인증 시도 로깅"""
        details = {
            'client_ip': ip,
            'success': success,
            'user_id': user_id
        }
        
        severity = 'INFO' if success else 'WARNING'
        self.log_security_event('authentication_attempt', details, severity)

# 전역 보안 로거 인스턴스
security_logger = SecurityLogger()
