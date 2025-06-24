"""
YouTube Data API v3 할당량 관리 시스템

일일 10,000 요청 제한 관리, 요청 추적, 할당량 초과 방지
"""

import json
import logging
import sqlite3
import threading
import smtplib
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


@dataclass
class QuotaUsage:
    """할당량 사용량 정보"""
    date: str
    requests_made: int
    quota_exceeded: bool
    last_request_time: Optional[str] = None
    daily_limit: int = 10000
    
    @property
    def remaining_quota(self) -> int:
        """남은 할당량"""
        return max(0, self.daily_limit - self.requests_made)
    
    @property
    def usage_percentage(self) -> float:
        """사용률 (0-100%)"""
        return (self.requests_made / self.daily_limit) * 100 if self.daily_limit > 0 else 0


class QuotaManager:
    """
    YouTube Data API v3 할당량 관리자
    
    기능:
    - 일일 할당량 추적 (기본 10,000 요청)
    - 요청 전 할당량 확인
    - 할당량 초과 방지
    - 사용량 통계 및 모니터링
    - SQLite 기반 영구 저장
    - 스레드 세이프 구현
    """
    
    def __init__(self, 
                 daily_limit: int = 10000,
                 db_path: Optional[str] = None,
                 enable_logging: bool = True,
                 warning_threshold: float = 0.8,
                 critical_threshold: float = 0.95,
                 alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        """
        할당량 관리자 초기화
        
        Args:
            daily_limit: 일일 할당량 제한 (기본 10,000)
            db_path: SQLite 데이터베이스 경로 (없으면 기본 경로 사용)
            enable_logging: 로깅 활성화 여부
            warning_threshold: 경고 알림 임계값 (기본 80%)
            critical_threshold: 위험 알림 임계값 (기본 95%)
            alert_callback: 알림 콜백 함수
        """
        self.daily_limit = daily_limit
        self.db_path = db_path or str(Path.cwd() / "youtube_api_quota.db")
        self.enable_logging = enable_logging
        
        # 경고 및 알림 설정
        self.warning_threshold = warning_threshold  # 80% 기본값
        self.critical_threshold = critical_threshold  # 95% 기본값
        self.alert_callback = alert_callback
        self._alerts_sent = set()  # 중복 알림 방지
        
        # 스레드 세이프를 위한 락
        self._lock = threading.Lock()
        
        # 로거 설정
        if enable_logging:
            self.logger = self._setup_logger()
        else:
            self.logger = None
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 현재 날짜 캐시
        self._current_date = self._get_current_date()
        self._today_usage: Optional[QuotaUsage] = None
        
        self._log_info("YouTube API 할당량 관리자 초기화 완료")
        self._log_info(f"경고 임계값: {self.warning_threshold*100:.1f}%, 위험 임계값: {self.critical_threshold*100:.1f}%")
        
        # 실시간 모니터링 및 알림 시스템 강화
        self._setup_cost_monitoring_system()
    
    def _setup_cost_monitoring_system(self):
        """
        실시간 비용 모니터링 시스템 설정
        
        Features:
        - 할당량 80% 도달 시 즉시 경고 알림
        - 할당량 95% 도달 시 위험 알림
        - 중복 알림 방지 메커니즘
        - 실시간 콜백 시스템
        """
        self._monitoring_enabled = True
        self._last_alert_usage = 0
        self._alert_cooldown = 300  # 5분 쿨다운
        self._last_alert_time = {}
        
        # 모니터링 통계
        self._monitoring_stats = {
            "alerts_sent": 0,
            "warnings_sent": 0,
            "critical_alerts_sent": 0,
            "monitoring_start_time": datetime.now(timezone.utc).isoformat()
        }
        
        self._log_info("실시간 비용 모니터링 시스템 활성화")
        self._log_info(f"알림 쿨다운: {self._alert_cooldown}초")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(f"{__name__}.QuotaManager")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _log_info(self, message: str):
        """정보 로그 출력"""
        if self.logger:
            self.logger.info(message)
    
    def _log_warning(self, message: str):
        """경고 로그 출력"""
        if self.logger:
            self.logger.warning(message)
    
    def _log_error(self, message: str):
        """에러 로그 출력"""
        if self.logger:
            self.logger.error(message)
    
    def _get_current_date(self) -> str:
        """현재 날짜 반환 (UTC 기준)"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def _init_database(self):
        """SQLite 데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS quota_usage (
                        date TEXT PRIMARY KEY,
                        requests_made INTEGER DEFAULT 0,
                        quota_exceeded BOOLEAN DEFAULT FALSE,
                        last_request_time TEXT,
                        daily_limit INTEGER DEFAULT 10000,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS request_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        date TEXT NOT NULL,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                
        except sqlite3.Error as e:
            self._log_error(f"데이터베이스 초기화 실패: {str(e)}")
            raise
    
    def _get_today_usage(self) -> QuotaUsage:
        """오늘 날짜의 할당량 사용량 조회"""
        current_date = self._get_current_date()
        
        # 날짜가 바뀌었으면 캐시 무효화
        if current_date != self._current_date:
            self._current_date = current_date
            self._today_usage = None
        
        # 캐시된 데이터가 있으면 반환
        if self._today_usage is not None:
            return self._today_usage
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM quota_usage WHERE date = ?",
                    (current_date,)
                )
                row = cursor.fetchone()
                
                if row:
                    usage = QuotaUsage(
                        date=row['date'],
                        requests_made=row['requests_made'],
                        quota_exceeded=bool(row['quota_exceeded']),
                        last_request_time=row['last_request_time'],
                        daily_limit=row['daily_limit']
                    )
                else:
                    # 오늘 첫 사용이면 새 레코드 생성
                    usage = QuotaUsage(
                        date=current_date,
                        requests_made=0,
                        quota_exceeded=False,
                        daily_limit=self.daily_limit
                    )
                    
                    conn.execute('''
                        INSERT INTO quota_usage 
                        (date, requests_made, quota_exceeded, daily_limit, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        current_date, 0, False, self.daily_limit,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    conn.commit()
                
                # 캐시 업데이트
                self._today_usage = usage
                return usage
                
        except sqlite3.Error as e:
            self._log_error(f"할당량 사용량 조회 실패: {str(e)}")
            # 에러 시 기본값 반환
            return QuotaUsage(
                date=current_date,
                requests_made=0,
                quota_exceeded=False,
                daily_limit=self.daily_limit
            )
    
    def _update_usage(self, usage: QuotaUsage):
        """할당량 사용량 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE quota_usage 
                    SET requests_made = ?, 
                        quota_exceeded = ?,
                        last_request_time = ?,
                        updated_at = ?
                    WHERE date = ?
                ''', (
                    usage.requests_made,
                    usage.quota_exceeded,
                    usage.last_request_time,
                    datetime.now(timezone.utc).isoformat(),
                    usage.date
                ))
                conn.commit()
                
                # 캐시 업데이트
                self._today_usage = usage
                
        except sqlite3.Error as e:
            self._log_error(f"할당량 사용량 업데이트 실패: {str(e)}")
    
    def _log_request(self, success: bool = True, error_message: Optional[str] = None):
        """요청 로그 기록"""
        try:
            current_time = datetime.now(timezone.utc)
            current_date = current_time.strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO request_log 
                    (timestamp, date, success, error_message)
                    VALUES (?, ?, ?, ?)
                ''', (
                    current_time.isoformat(),
                    current_date,
                    success,
                    error_message
                ))
                conn.commit()
                
        except sqlite3.Error as e:
            self._log_error(f"요청 로그 기록 실패: {str(e)}")
    
    def can_make_request(self, requests_needed: int = 1) -> bool:
        """
        요청 가능 여부 확인
        
        Args:
            requests_needed: 필요한 요청 수 (기본 1)
            
        Returns:
            요청 가능 여부
        """
        with self._lock:
            usage = self._get_today_usage()
            
            # 이미 할당량이 초과되었으면 False
            if usage.quota_exceeded:
                return False
            
            # 요청 후 할당량을 초과하게 되면 False
            if usage.requests_made + requests_needed > usage.daily_limit:
                return False
            
            return True
    
    def record_request(self, requests_count: int = 1, success: bool = True, error_message: Optional[str] = None):
        """
        API 요청 기록
        
        Args:
            requests_count: 요청 수 (기본 1)
            success: 요청 성공 여부
            error_message: 에러 메시지 (실패 시)
        """
        with self._lock:
            usage = self._get_today_usage()
            
            # 성공한 요청만 할당량에 계산
            if success:
                usage.requests_made += requests_count
                usage.last_request_time = datetime.now(timezone.utc).isoformat()
                
                # 할당량 초과 체크
                if usage.requests_made >= usage.daily_limit:
                    usage.quota_exceeded = True
                    self._log_warning(f"일일 할당량 초과: {usage.requests_made}/{usage.daily_limit}")
                    self._send_alert("quota_exceeded", usage)
                else:
                    # 임계값 체크 및 알림
                    self._check_thresholds(usage)
            
            # 데이터베이스 업데이트
            self._update_usage(usage)
            
            # 요청 로그 기록
            self._log_request(success, error_message)
            
            if success:
                self._log_info(f"API 요청 기록: {requests_count}회 (총 {usage.requests_made}/{usage.daily_limit})")
    
    def mark_quota_exceeded(self):
        """할당량 초과 표시"""
        with self._lock:
            usage = self._get_today_usage()
            usage.quota_exceeded = True
            self._update_usage(usage)
            self._log_warning("할당량 초과로 표시됨")
    
    def reset_daily_quota(self, target_date: Optional[str] = None):
        """
        일일 할당량 리셋 (새로운 날짜 또는 관리자 리셋)
        
        Args:
            target_date: 리셋할 날짜 (없으면 오늘)
        """
        with self._lock:
            reset_date = target_date or self._get_current_date()
            
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        UPDATE quota_usage 
                        SET requests_made = 0, 
                            quota_exceeded = FALSE,
                            last_request_time = NULL,
                            updated_at = ?
                        WHERE date = ?
                    ''', (
                        datetime.now(timezone.utc).isoformat(),
                        reset_date
                    ))
                    conn.commit()
                
                # 오늘 날짜면 캐시 및 알림 상태 리셋
                if reset_date == self._get_current_date():
                    self._today_usage = None
                    # 오늘 날짜의 알림 상태 클리어
                    self._alerts_sent = {k for k in self._alerts_sent if reset_date not in k}
                
                self._log_info(f"할당량 리셋 완료: {reset_date}")
                
            except sqlite3.Error as e:
                self._log_error(f"할당량 리셋 실패: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        현재 할당량 상태 반환
        
        Returns:
            할당량 상태 정보
        """
        with self._lock:
            usage = self._get_today_usage()
            
            return {
                'date': usage.date,
                'requests_made': usage.requests_made,
                'daily_limit': usage.daily_limit,
                'remaining_quota': usage.remaining_quota,
                'usage_percentage': round(usage.usage_percentage, 2),
                'quota_exceeded': usage.quota_exceeded,
                'last_request_time': usage.last_request_time,
                'can_make_request': self.can_make_request()
            }
    
    def get_usage_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        최근 사용량 히스토리 조회
        
        Args:
            days: 조회할 일수 (기본 7일)
            
        Returns:
            사용량 히스토리 리스트
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 최근 N일 데이터 조회
                end_date = datetime.now(timezone.utc).date()
                start_date = end_date - timedelta(days=days-1)
                
                cursor = conn.execute('''
                    SELECT * FROM quota_usage 
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date DESC
                ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                history = []
                for row in cursor.fetchall():
                    usage = QuotaUsage(
                        date=row['date'],
                        requests_made=row['requests_made'],
                        quota_exceeded=bool(row['quota_exceeded']),
                        last_request_time=row['last_request_time'],
                        daily_limit=row['daily_limit']
                    )
                    history.append(asdict(usage))
                
                return history
                
        except sqlite3.Error as e:
            self._log_error(f"사용량 히스토리 조회 실패: {str(e)}")
            return []
    
    def get_request_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        요청 통계 조회
        
        Args:
            days: 조회할 일수 (기본 7일)
            
        Returns:
            요청 통계 정보
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 최근 N일 통계
                end_date = datetime.now(timezone.utc).date()
                start_date = end_date - timedelta(days=days-1)
                
                # 전체 요청 수
                cursor = conn.execute('''
                    SELECT COUNT(*) as total_requests,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests
                    FROM request_log 
                    WHERE date BETWEEN ? AND ?
                ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                stats = cursor.fetchone()
                
                # 일별 요청 수
                cursor = conn.execute('''
                    SELECT date, 
                           COUNT(*) as requests_count,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_count
                    FROM request_log 
                    WHERE date BETWEEN ? AND ?
                    GROUP BY date
                    ORDER BY date DESC
                ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                daily_stats = [dict(row) for row in cursor.fetchall()]
                
                success_rate = 0
                if stats['total_requests'] > 0:
                    success_rate = (stats['successful_requests'] / stats['total_requests']) * 100
                
                return {
                    'period_days': days,
                    'total_requests': stats['total_requests'],
                    'successful_requests': stats['successful_requests'],
                    'failed_requests': stats['failed_requests'],
                    'success_rate': round(success_rate, 2),
                    'daily_breakdown': daily_stats
                }
                
        except sqlite3.Error as e:
            self._log_error(f"요청 통계 조회 실패: {str(e)}")
            return {
                'period_days': days,
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'success_rate': 0,
                'daily_breakdown': []
            }
    
    def cleanup_old_data(self, keep_days: int = 30):
        """
        오래된 데이터 정리
        
        Args:
            keep_days: 보관할 일수 (기본 30일)
        """
        try:
            cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                # 오래된 할당량 데이터 삭제
                cursor = conn.execute('DELETE FROM quota_usage WHERE date < ?', (cutoff_date,))
                quota_deleted = cursor.rowcount
                
                # 오래된 요청 로그 삭제
                cursor = conn.execute('DELETE FROM request_log WHERE date < ?', (cutoff_date,))
                log_deleted = cursor.rowcount
                
                conn.commit()
                
                self._log_info(f"오래된 데이터 정리 완료: 할당량 {quota_deleted}건, 로그 {log_deleted}건 삭제")
                
        except sqlite3.Error as e:
            self._log_error(f"데이터 정리 실패: {str(e)}")
    
    def export_data(self, output_path: str, days: int = 30) -> bool:
        """
        데이터 내보내기 (JSON 형식)
        
        Args:
            output_path: 출력 파일 경로
            days: 내보낼 일수
            
        Returns:
            성공 여부
        """
        try:
            export_data = {
                'export_timestamp': datetime.now(timezone.utc).isoformat(),
                'export_days': days,
                'usage_history': self.get_usage_history(days),
                'request_stats': self.get_request_stats(days),
                'current_status': self.get_status()
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self._log_info(f"데이터 내보내기 완료: {output_path}")
            return True
            
        except Exception as e:
            self._log_error(f"데이터 내보내기 실패: {str(e)}")
            return False
    
    def _check_thresholds(self, usage: QuotaUsage):
        """
        강화된 할당량 임계값 체크 및 실시간 알림 전송
        
        Args:
            usage: 현재 할당량 사용량
        """
        if not self._monitoring_enabled:
            return
            
        usage_percentage = usage.usage_percentage / 100.0
        today = usage.date
        current_time = time.time()
        
        # 중복 알림 방지를 위한 쿨다운 체크
        def can_send_alert(alert_type: str) -> bool:
            last_time = self._last_alert_time.get(f"{alert_type}_{today}", 0)
            return (current_time - last_time) >= self._alert_cooldown
        
        # 위험 임계값 체크 (95%) - 즉시 알림
        critical_key = f"critical_{today}"
        if usage_percentage >= self.critical_threshold and critical_key not in self._alerts_sent:
            if can_send_alert("critical"):
                self._log_warning(f"🚨 위험: 할당량 {usage.usage_percentage:.1f}% 사용 ({usage.requests_made:,}/{usage.daily_limit:,})")
                self._send_enhanced_alert("critical_threshold", usage)
                self._alerts_sent.add(critical_key)
                self._last_alert_time[f"critical_{today}"] = current_time
                self._monitoring_stats["critical_alerts_sent"] += 1
        
        # 경고 임계값 체크 (80%) - 즉시 알림
        warning_key = f"warning_{today}"
        if usage_percentage >= self.warning_threshold and warning_key not in self._alerts_sent:
            if can_send_alert("warning"):
                self._log_warning(f"⚠️ 경고: 할당량 {usage.usage_percentage:.1f}% 사용 ({usage.requests_made:,}/{usage.daily_limit:,})")
                self._send_enhanced_alert("warning_threshold", usage)
                self._alerts_sent.add(warning_key)
                self._last_alert_time[f"warning_{today}"] = current_time
                self._monitoring_stats["warnings_sent"] += 1
        
        # 추가 세분화된 임계값 (90% - 긴급 사전 경고)
        urgent_key = f"urgent_{today}"
        if usage_percentage >= 0.90 and urgent_key not in self._alerts_sent:
            if can_send_alert("urgent"):
                self._log_warning(f"🔥 긴급: 할당량 {usage.usage_percentage:.1f}% 사용 - 조치 필요!")
                self._send_enhanced_alert("urgent_threshold", usage)
                self._alerts_sent.add(urgent_key)
                self._last_alert_time[f"urgent_{today}"] = current_time
    
    def _send_enhanced_alert(self, alert_type: str, usage: QuotaUsage):
        """
        향상된 실시간 알림 전송 시스템
        
        Args:
            alert_type: 알림 유형 (warning_threshold, critical_threshold, urgent_threshold, quota_exceeded)
            usage: 할당량 사용량 정보
        """
        if self.alert_callback:
            # 상세한 알림 데이터 구성
            alert_data = {
                "type": alert_type,
                "severity": self._get_alert_severity(alert_type),
                "usage_percentage": usage.usage_percentage,
                "requests_made": usage.requests_made,
                "daily_limit": usage.daily_limit,
                "remaining_quota": usage.remaining_quota,
                "date": usage.date,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "estimated_time_to_limit": self._calculate_time_to_limit(usage),
                "recommended_actions": self._get_recommended_actions(alert_type, usage),
                "cost_impact": self._calculate_cost_impact(usage),
                "monitoring_stats": self._monitoring_stats.copy()
            }
            
            try:
                self.alert_callback(alert_type, alert_data)
                self._monitoring_stats["alerts_sent"] += 1
                self._log_info(f"향상된 알림 전송 완료: {alert_type} (심각도: {alert_data['severity']})")
            except Exception as e:
                self._log_error(f"향상된 알림 전송 실패: {str(e)}")
        
        # 기존 알림도 유지 (하위 호환성)
        self._send_alert(alert_type, usage)
    
    def _send_alert(self, alert_type: str, usage: QuotaUsage):
        """
        기본 알림 전송 (하위 호환성 유지)
        
        Args:
            alert_type: 알림 유형 (warning_threshold, critical_threshold, quota_exceeded)
            usage: 할당량 사용량 정보
        """
        if self.alert_callback:
            alert_data = {
                "type": alert_type,
                "usage_percentage": usage.usage_percentage,
                "requests_made": usage.requests_made,
                "daily_limit": usage.daily_limit,
                "remaining_quota": usage.remaining_quota,
                "date": usage.date,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            try:
                self.alert_callback(alert_type, alert_data)
                self._log_info(f"알림 전송 완료: {alert_type}")
            except Exception as e:
                self._log_error(f"알림 전송 실패: {str(e)}")
    
    def _get_alert_severity(self, alert_type: str) -> str:
        """알림 유형별 심각도 반환"""
        severity_map = {
            "warning_threshold": "medium",
            "urgent_threshold": "high", 
            "critical_threshold": "critical",
            "quota_exceeded": "critical"
        }
        return severity_map.get(alert_type, "low")
    
    def _calculate_time_to_limit(self, usage: QuotaUsage) -> Optional[str]:
        """할당량 한계 도달까지 예상 시간 계산"""
        if usage.remaining_quota <= 0:
            return "Already exceeded"
        
        # 최근 1시간 사용량 기반 예측 (간단한 추정)
        # 실제 구현에서는 더 정교한 예측 알고리즘 사용 가능
        try:
            current_hour = datetime.now(timezone.utc).hour
            if current_hour == 0:  # 자정이면 예측 불가
                return "Unable to estimate"
            
            hourly_rate = usage.requests_made / max(current_hour, 1)
            if hourly_rate <= 0:
                return "No usage trend"
            
            hours_to_limit = usage.remaining_quota / hourly_rate
            if hours_to_limit > 24:
                return "More than 24 hours"
            elif hours_to_limit > 1:
                return f"~{hours_to_limit:.1f} hours"
            else:
                minutes_to_limit = hours_to_limit * 60
                return f"~{minutes_to_limit:.0f} minutes"
        except:
            return "Unable to calculate"
    
    def _get_recommended_actions(self, alert_type: str, usage: QuotaUsage) -> List[str]:
        """알림 유형별 권장 조치사항"""
        actions = []
        
        if alert_type == "warning_threshold":
            actions = [
                "API 사용량 모니터링 강화",
                "불필요한 요청 최적화 검토", 
                "캐시 활용도 점검",
                "배치 처리 적용 검토"
            ]
        elif alert_type == "urgent_threshold":
            actions = [
                "즉시 API 사용량 검토",
                "중요하지 않은 API 호출 중단",
                "배치 처리로 효율성 개선",
                "추가 할당량 확보 준비"
            ]
        elif alert_type == "critical_threshold":
            actions = [
                "🚨 즉시 모든 비필수 API 호출 중단",
                "긴급 할당량 확보 조치",
                "시스템 관리자 즉시 통보",
                "서비스 중단 계획 준비"
            ]
        elif alert_type == "quota_exceeded":
            actions = [
                "🔴 모든 API 호출 중단",
                "서비스 제한 모드 활성화", 
                "할당량 증액 긴급 신청",
                "사용자 안내 메시지 게시"
            ]
        
        return actions
    
    def _calculate_cost_impact(self, usage: QuotaUsage) -> Dict[str, Any]:
        """비용 영향 계산"""
        # YouTube Data API v3의 기본 비용 (할당량 단위당 비용)
        # 실제 비용은 Google의 최신 가격 정책에 따라 달라질 수 있음
        quota_unit_cost = 0.0001  # 예시 비용 (실제 비용으로 업데이트 필요)
        
        estimated_daily_cost = usage.requests_made * quota_unit_cost
        projected_monthly_cost = estimated_daily_cost * 30
        
        return {
            "estimated_daily_cost_usd": round(estimated_daily_cost, 4),
            "projected_monthly_cost_usd": round(projected_monthly_cost, 2),
            "usage_efficiency": round((usage.requests_made / usage.daily_limit) * 100, 2),
            "cost_per_request": quota_unit_cost
        }
    
    def set_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        알림 콜백 함수 설정
        
        Args:
            callback: 알림 콜백 함수
        """
        self.alert_callback = callback
        self._log_info("알림 콜백 함수 설정 완료")
    
    def get_threshold_status(self) -> Dict[str, Any]:
        """
        임계값 상태 정보 반환
        
        Returns:
            임계값 상태 정보
        """
        usage = self._get_today_usage()
        usage_percentage = usage.usage_percentage / 100.0
        
        status = "normal"
        if usage.quota_exceeded:
            status = "exceeded"
        elif usage_percentage >= self.critical_threshold:
            status = "critical"
        elif usage_percentage >= self.warning_threshold:
            status = "warning"
        
        return {
            "status": status,
            "usage_percentage": usage.usage_percentage,
            "warning_threshold": self.warning_threshold * 100,
            "critical_threshold": self.critical_threshold * 100,
            "requests_made": usage.requests_made,
            "remaining_quota": usage.remaining_quota,
            "alerts_sent_today": len([k for k in self._alerts_sent if usage.date in k])
        }


# 전역 인스턴스 (싱글톤 패턴)
_global_quota_manager: Optional[QuotaManager] = None
_manager_lock = threading.Lock()


def get_global_quota_manager(daily_limit: int = 10000) -> QuotaManager:
    """
    전역 할당량 관리자 인스턴스 반환 (싱글톤)
    
    Args:
        daily_limit: 일일 할당량 제한
        
    Returns:
        QuotaManager 인스턴스
    """
    global _global_quota_manager
    
    with _manager_lock:
        if _global_quota_manager is None:
            _global_quota_manager = QuotaManager(daily_limit=daily_limit)
        
        return _global_quota_manager