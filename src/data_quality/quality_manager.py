"""
데이터 품질 관리 시스템

99% 신뢰도를 목표로 하는 포괄적 데이터 품질 관리 시스템입니다.
데이터 무결성, 중복 제거, 이상치 탐지, 라이프사이클 관리를 포함합니다.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import statistics
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)


class DataQualityIssue(Enum):
    """데이터 품질 이슈 유형"""
    MISSING_VALUES = "missing_values"
    DUPLICATE_RECORDS = "duplicate_records"
    INVALID_FORMAT = "invalid_format"
    OUTLIER_DETECTED = "outlier_detected"
    INCONSISTENT_DATA = "inconsistent_data"
    STALE_DATA = "stale_data"
    INTEGRITY_VIOLATION = "integrity_violation"
    ENCODING_ERROR = "encoding_error"


class DataQualitySeverity(Enum):
    """품질 이슈 심각도"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class QualityMetric:
    """품질 지표"""
    metric_name: str
    current_value: float
    target_value: float
    threshold_warning: float
    threshold_critical: float
    measurement_time: datetime = field(default_factory=datetime.now)
    trend_direction: str = "stable"  # improving, degrading, stable
    

@dataclass
class QualityIssueRecord:
    """품질 이슈 기록"""
    issue_id: str
    issue_type: DataQualityIssue
    severity: DataQualitySeverity
    description: str
    affected_records: int
    data_source: str
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataIntegrityValidator:
    """데이터 무결성 검증기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_rules = self._initialize_validation_rules()
        self.format_patterns = self._initialize_format_patterns()
    
    def _initialize_validation_rules(self) -> Dict[str, Dict]:
        """검증 규칙 초기화"""
        return {
            'channel_data': {
                'required_fields': ['channel_id', 'channel_name', 'subscriber_count'],
                'field_types': {
                    'channel_id': str,
                    'subscriber_count': int,
                    'view_count': int,
                    'video_count': int
                },
                'value_ranges': {
                    'subscriber_count': (0, 200000000),  # 최대 2억
                    'view_count': (0, 50000000000),      # 최대 500억
                    'video_count': (0, 100000)           # 최대 10만개
                },
                'relationships': {
                    'view_count_vs_subscribers': lambda v, s: v >= s * 10 if s > 0 else True
                }
            },
            'video_data': {
                'required_fields': ['video_id', 'title', 'channel_id'],
                'field_types': {
                    'video_id': str,
                    'title': str,
                    'view_count': int,
                    'like_count': int,
                    'duration_seconds': int
                },
                'value_ranges': {
                    'view_count': (0, 10000000000),      # 최대 100억
                    'like_count': (0, 50000000),         # 최대 5천만
                    'duration_seconds': (1, 86400)       # 1초~24시간
                },
                'relationships': {
                    'likes_vs_views': lambda l, v: l <= v * 0.2 if v > 0 else True
                }
            },
            'ppl_analysis': {
                'required_fields': ['video_id', 'probability_score', 'classification'],
                'field_types': {
                    'probability_score': float,
                    'confidence': float
                },
                'value_ranges': {
                    'probability_score': (0.0, 1.0),
                    'confidence': (0.0, 1.0)
                }
            }
        }
    
    def _initialize_format_patterns(self) -> Dict[str, str]:
        """형식 패턴 초기화"""
        return {
            'youtube_channel_id': r'^UC[a-zA-Z0-9_-]{22}$',
            'youtube_video_id': r'^[a-zA-Z0-9_-]{11}$',
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'url': r'^https?://[^\s]+$',
            'iso_datetime': r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            'korean_text': r'^[가-힣\s\w\d\p{P}]*$'
        }
    
    def validate_record(
        self, 
        record: Dict[str, Any], 
        data_type: str
    ) -> Tuple[bool, List[QualityIssueRecord]]:
        """개별 레코드 검증"""
        
        issues = []
        rules = self.validation_rules.get(data_type)
        
        if not rules:
            return True, []
        
        try:
            # 1. 필수 필드 검증
            missing_fields = self._check_required_fields(record, rules.get('required_fields', []))
            if missing_fields:
                issues.append(QualityIssueRecord(
                    issue_id=self._generate_issue_id(record, 'missing_fields'),
                    issue_type=DataQualityIssue.MISSING_VALUES,
                    severity=DataQualitySeverity.CRITICAL,
                    description=f"Missing required fields: {missing_fields}",
                    affected_records=1,
                    data_source=data_type,
                    metadata={'missing_fields': missing_fields}
                ))
            
            # 2. 데이터 타입 검증
            type_issues = self._check_data_types(record, rules.get('field_types', {}))
            issues.extend(type_issues)
            
            # 3. 값 범위 검증
            range_issues = self._check_value_ranges(record, rules.get('value_ranges', {}))
            issues.extend(range_issues)
            
            # 4. 관계형 검증
            relationship_issues = self._check_relationships(record, rules.get('relationships', {}))
            issues.extend(relationship_issues)
            
            # 5. 형식 검증
            format_issues = self._check_format_patterns(record, data_type)
            issues.extend(format_issues)
            
            return len(issues) == 0, issues
            
        except Exception as e:
            self.logger.error(f"레코드 검증 오류: {str(e)}")
            issues.append(QualityIssueRecord(
                issue_id=self._generate_issue_id(record, 'validation_error'),
                issue_type=DataQualityIssue.INTEGRITY_VIOLATION,
                severity=DataQualitySeverity.HIGH,
                description=f"Validation error: {str(e)}",
                affected_records=1,
                data_source=data_type
            ))
            return False, issues
    
    def _check_required_fields(self, record: Dict, required_fields: List[str]) -> List[str]:
        """필수 필드 확인"""
        missing = []
        for field in required_fields:
            if field not in record or record[field] is None or record[field] == '':
                missing.append(field)
        return missing
    
    def _check_data_types(self, record: Dict, field_types: Dict[str, type]) -> List[QualityIssueRecord]:
        """데이터 타입 확인"""
        issues = []
        
        for field, expected_type in field_types.items():
            if field in record and record[field] is not None:
                value = record[field]
                
                # 타입 변환 시도
                try:
                    if expected_type == int and isinstance(value, str):
                        int(value)
                    elif expected_type == float and isinstance(value, (str, int)):
                        float(value)
                    elif not isinstance(value, expected_type):
                        issues.append(QualityIssueRecord(
                            issue_id=self._generate_issue_id(record, f'type_{field}'),
                            issue_type=DataQualityIssue.INVALID_FORMAT,
                            severity=DataQualitySeverity.MEDIUM,
                            description=f"Invalid type for {field}: expected {expected_type.__name__}, got {type(value).__name__}",
                            affected_records=1,
                            data_source='validation',
                            metadata={'field': field, 'expected_type': expected_type.__name__, 'actual_value': str(value)}
                        ))
                except (ValueError, TypeError):
                    issues.append(QualityIssueRecord(
                        issue_id=self._generate_issue_id(record, f'convert_{field}'),
                        issue_type=DataQualityIssue.INVALID_FORMAT,
                        severity=DataQualitySeverity.HIGH,
                        description=f"Cannot convert {field} to {expected_type.__name__}: {value}",
                        affected_records=1,
                        data_source='validation',
                        metadata={'field': field, 'value': str(value)}
                    ))
        
        return issues
    
    def _check_value_ranges(self, record: Dict, value_ranges: Dict[str, Tuple]) -> List[QualityIssueRecord]:
        """값 범위 확인"""
        issues = []
        
        for field, (min_val, max_val) in value_ranges.items():
            if field in record and record[field] is not None:
                try:
                    value = float(record[field])
                    if not (min_val <= value <= max_val):
                        severity = DataQualitySeverity.HIGH if value < 0 else DataQualitySeverity.MEDIUM
                        issues.append(QualityIssueRecord(
                            issue_id=self._generate_issue_id(record, f'range_{field}'),
                            issue_type=DataQualityIssue.OUTLIER_DETECTED,
                            severity=severity,
                            description=f"Value out of range for {field}: {value} (expected {min_val}-{max_val})",
                            affected_records=1,
                            data_source='validation',
                            metadata={'field': field, 'value': value, 'range': (min_val, max_val)}
                        ))
                except (ValueError, TypeError):
                    # 타입 변환 실패는 타입 검증에서 처리됨
                    pass
        
        return issues
    
    def _check_relationships(self, record: Dict, relationships: Dict[str, callable]) -> List[QualityIssueRecord]:
        """관계형 검증"""
        issues = []
        
        for relationship_name, validation_func in relationships.items():
            try:
                # 관계형 검증 함수의 파라미터 추출
                if relationship_name == 'view_count_vs_subscribers':
                    view_count = record.get('view_count', 0)
                    subscriber_count = record.get('subscriber_count', 0)
                    
                    if not validation_func(view_count, subscriber_count):
                        issues.append(QualityIssueRecord(
                            issue_id=self._generate_issue_id(record, f'rel_{relationship_name}'),
                            issue_type=DataQualityIssue.INCONSISTENT_DATA,
                            severity=DataQualitySeverity.MEDIUM,
                            description=f"Relationship violation: {relationship_name}",
                            affected_records=1,
                            data_source='validation',
                            metadata={
                                'relationship': relationship_name,
                                'view_count': view_count,
                                'subscriber_count': subscriber_count
                            }
                        ))
                
                elif relationship_name == 'likes_vs_views':
                    like_count = record.get('like_count', 0)
                    view_count = record.get('view_count', 0)
                    
                    if not validation_func(like_count, view_count):
                        issues.append(QualityIssueRecord(
                            issue_id=self._generate_issue_id(record, f'rel_{relationship_name}'),
                            issue_type=DataQualityIssue.INCONSISTENT_DATA,
                            severity=DataQualitySeverity.LOW,
                            description=f"Unusual like-to-view ratio: {relationship_name}",
                            affected_records=1,
                            data_source='validation',
                            metadata={
                                'relationship': relationship_name,
                                'like_count': like_count,
                                'view_count': view_count
                            }
                        ))
                        
            except Exception as e:
                self.logger.warning(f"관계형 검증 오류 {relationship_name}: {str(e)}")
        
        return issues
    
    def _check_format_patterns(self, record: Dict, data_type: str) -> List[QualityIssueRecord]:
        """형식 패턴 확인"""
        issues = []
        
        format_checks = {
            'channel_data': [
                ('channel_id', 'youtube_channel_id'),
                ('custom_url', 'url')
            ],
            'video_data': [
                ('video_id', 'youtube_video_id'),
                ('thumbnail_url', 'url')
            ]
        }
        
        checks = format_checks.get(data_type, [])
        
        for field, pattern_name in checks:
            if field in record and record[field]:
                value = str(record[field])
                pattern = self.format_patterns.get(pattern_name)
                
                if pattern and not re.match(pattern, value):
                    issues.append(QualityIssueRecord(
                        issue_id=self._generate_issue_id(record, f'format_{field}'),
                        issue_type=DataQualityIssue.INVALID_FORMAT,
                        severity=DataQualitySeverity.MEDIUM,
                        description=f"Invalid format for {field}: {value}",
                        affected_records=1,
                        data_source='validation',
                        metadata={'field': field, 'value': value, 'pattern': pattern_name}
                    ))
        
        return issues
    
    def _generate_issue_id(self, record: Dict, issue_type: str) -> str:
        """이슈 ID 생성"""
        identifier = f"{record.get('channel_id', '')}{record.get('video_id', '')}{issue_type}"
        return hashlib.md5(identifier.encode()).hexdigest()[:16]


class DuplicateDetector:
    """중복 감지 및 제거기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.deduplication_strategies = self._initialize_deduplication_strategies()
    
    def _initialize_deduplication_strategies(self) -> Dict[str, Dict]:
        """중복 제거 전략 초기화"""
        return {
            'exact_match': {
                'description': '완전 일치 중복',
                'key_fields': ['channel_id', 'video_id'],
                'threshold': 1.0
            },
            'fuzzy_match': {
                'description': '유사 중복',
                'key_fields': ['channel_name', 'title'],
                'threshold': 0.9
            },
            'content_similarity': {
                'description': '콘텐츠 유사도 기반',
                'key_fields': ['title', 'description'],
                'threshold': 0.85
            }
        }
    
    def detect_duplicates(
        self, 
        records: List[Dict[str, Any]], 
        strategy: str = 'exact_match'
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """중복 감지"""
        
        strategy_config = self.deduplication_strategies.get(strategy)
        if not strategy_config:
            raise ValueError(f"Unknown deduplication strategy: {strategy}")
        
        try:
            if strategy == 'exact_match':
                return self._detect_exact_duplicates(records, strategy_config)
            elif strategy == 'fuzzy_match':
                return self._detect_fuzzy_duplicates(records, strategy_config)
            elif strategy == 'content_similarity':
                return self._detect_content_similarity_duplicates(records, strategy_config)
            
        except Exception as e:
            self.logger.error(f"중복 감지 오류: {str(e)}")
            return records, []
    
    def _detect_exact_duplicates(
        self, 
        records: List[Dict], 
        config: Dict
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """완전 일치 중복 감지"""
        
        seen_keys = set()
        unique_records = []
        duplicate_issues = []
        key_fields = config['key_fields']
        
        for record in records:
            # 키 생성
            key_values = []
            for field in key_fields:
                value = record.get(field, '')
                key_values.append(str(value))
            
            record_key = '|'.join(key_values)
            
            if record_key in seen_keys:
                # 중복 발견
                duplicate_issues.append(QualityIssueRecord(
                    issue_id=hashlib.md5(record_key.encode()).hexdigest()[:16],
                    issue_type=DataQualityIssue.DUPLICATE_RECORDS,
                    severity=DataQualitySeverity.MEDIUM,
                    description=f"Exact duplicate found: {record_key}",
                    affected_records=1,
                    data_source='deduplication',
                    metadata={'duplicate_key': record_key, 'key_fields': key_fields}
                ))
            else:
                seen_keys.add(record_key)
                unique_records.append(record)
        
        return unique_records, duplicate_issues
    
    def _detect_fuzzy_duplicates(
        self, 
        records: List[Dict], 
        config: Dict
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """유사 중복 감지"""
        
        unique_records = []
        duplicate_issues = []
        threshold = config['threshold']
        
        for i, record1 in enumerate(records):
            is_duplicate = False
            
            for j, record2 in enumerate(unique_records):
                similarity = self._calculate_text_similarity(
                    record1, record2, config['key_fields']
                )
                
                if similarity >= threshold:
                    is_duplicate = True
                    duplicate_issues.append(QualityIssueRecord(
                        issue_id=f"fuzzy_{i}_{j}",
                        issue_type=DataQualityIssue.DUPLICATE_RECORDS,
                        severity=DataQualitySeverity.LOW,
                        description=f"Fuzzy duplicate detected (similarity: {similarity:.2f})",
                        affected_records=1,
                        data_source='deduplication',
                        metadata={'similarity_score': similarity, 'threshold': threshold}
                    ))
                    break
            
            if not is_duplicate:
                unique_records.append(record1)
        
        return unique_records, duplicate_issues
    
    def _detect_content_similarity_duplicates(
        self, 
        records: List[Dict], 
        config: Dict
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """콘텐츠 유사도 기반 중복 감지"""
        
        # 간단한 구현 (실제로는 더 정교한 NLP 기법 사용)
        return self._detect_fuzzy_duplicates(records, config)
    
    def _calculate_text_similarity(
        self, 
        record1: Dict, 
        record2: Dict, 
        fields: List[str]
    ) -> float:
        """텍스트 유사도 계산"""
        
        similarities = []
        
        for field in fields:
            text1 = str(record1.get(field, '')).lower().strip()
            text2 = str(record2.get(field, '')).lower().strip()
            
            if not text1 or not text2:
                similarities.append(0.0)
                continue
            
            # Jaccard 유사도 계산
            set1 = set(text1.split())
            set2 = set(text2.split())
            
            if not set1 and not set2:
                similarities.append(1.0)
            elif not set1 or not set2:
                similarities.append(0.0)
            else:
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                similarities.append(intersection / union)
        
        return np.mean(similarities) if similarities else 0.0


class OutlierDetector:
    """이상치 탐지기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_outliers(
        self, 
        data: List[Dict[str, Any]], 
        numeric_fields: List[str],
        method: str = 'iqr'
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """이상치 탐지"""
        
        if method == 'iqr':
            return self._detect_iqr_outliers(data, numeric_fields)
        elif method == 'zscore':
            return self._detect_zscore_outliers(data, numeric_fields)
        elif method == 'isolation_forest':
            return self._detect_isolation_forest_outliers(data, numeric_fields)
        else:
            raise ValueError(f"Unknown outlier detection method: {method}")
    
    def _detect_iqr_outliers(
        self, 
        data: List[Dict], 
        numeric_fields: List[str]
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """IQR 방법을 사용한 이상치 탐지"""
        
        clean_data = []
        outlier_issues = []
        
        for field in numeric_fields:
            # 필드 값 추출
            values = []
            for record in data:
                if field in record and record[field] is not None:
                    try:
                        values.append(float(record[field]))
                    except (ValueError, TypeError):
                        continue
            
            if len(values) < 4:  # IQR 계산을 위한 최소 데이터
                continue
            
            # IQR 계산
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # 이상치 식별
            for record in data:
                if field in record and record[field] is not None:
                    try:
                        value = float(record[field])
                        if value < lower_bound or value > upper_bound:
                            outlier_issues.append(QualityIssueRecord(
                                issue_id=f"outlier_{field}_{hash(str(record))}",
                                issue_type=DataQualityIssue.OUTLIER_DETECTED,
                                severity=DataQualitySeverity.MEDIUM,
                                description=f"IQR outlier in {field}: {value} (bounds: {lower_bound:.2f}-{upper_bound:.2f})",
                                affected_records=1,
                                data_source='outlier_detection',
                                metadata={
                                    'field': field,
                                    'value': value,
                                    'lower_bound': lower_bound,
                                    'upper_bound': upper_bound,
                                    'q1': q1,
                                    'q3': q3,
                                    'iqr': iqr
                                }
                            ))
                        else:
                            clean_data.append(record)
                    except (ValueError, TypeError):
                        continue
        
        return clean_data, outlier_issues
    
    def _detect_zscore_outliers(
        self, 
        data: List[Dict], 
        numeric_fields: List[str]
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """Z-Score 방법을 사용한 이상치 탐지"""
        
        clean_data = []
        outlier_issues = []
        threshold = 3.0  # 표준편차 3배
        
        for field in numeric_fields:
            values = []
            for record in data:
                if field in record and record[field] is not None:
                    try:
                        values.append(float(record[field]))
                    except (ValueError, TypeError):
                        continue
            
            if len(values) < 2:
                continue
            
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if std_val == 0:  # 표준편차가 0이면 이상치 없음
                continue
            
            for record in data:
                if field in record and record[field] is not None:
                    try:
                        value = float(record[field])
                        z_score = abs((value - mean_val) / std_val)
                        
                        if z_score > threshold:
                            outlier_issues.append(QualityIssueRecord(
                                issue_id=f"zscore_{field}_{hash(str(record))}",
                                issue_type=DataQualityIssue.OUTLIER_DETECTED,
                                severity=DataQualitySeverity.MEDIUM,
                                description=f"Z-score outlier in {field}: {value} (z-score: {z_score:.2f})",
                                affected_records=1,
                                data_source='outlier_detection',
                                metadata={
                                    'field': field,
                                    'value': value,
                                    'z_score': z_score,
                                    'mean': mean_val,
                                    'std': std_val,
                                    'threshold': threshold
                                }
                            ))
                        else:
                            clean_data.append(record)
                    except (ValueError, TypeError):
                        continue
        
        return clean_data, outlier_issues
    
    def _detect_isolation_forest_outliers(
        self, 
        data: List[Dict], 
        numeric_fields: List[str]
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """Isolation Forest를 사용한 이상치 탐지 (간단한 구현)"""
        
        # 실제 구현에서는 scikit-learn의 IsolationForest 사용
        # 여기서는 통계적 방법으로 근사
        return self._detect_iqr_outliers(data, numeric_fields)


class DataLifecycleManager:
    """데이터 라이프사이클 관리기"""
    
    def __init__(self, db_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path or ":memory:"
        self.retention_policies = self._initialize_retention_policies()
        self._initialize_database()
    
    def _initialize_retention_policies(self) -> Dict[str, Dict]:
        """보존 정책 초기화"""
        return {
            'channel_data': {
                'retention_days': 365,      # 1년 보존
                'archive_after_days': 180,  # 6개월 후 아카이브
                'cleanup_frequency': 'weekly'
            },
            'video_data': {
                'retention_days': 180,      # 6개월 보존
                'archive_after_days': 90,   # 3개월 후 아카이브
                'cleanup_frequency': 'daily'
            },
            'ppl_analysis': {
                'retention_days': 90,       # 3개월 보존
                'archive_after_days': 30,   # 1개월 후 아카이브
                'cleanup_frequency': 'daily'
            },
            'quality_issues': {
                'retention_days': 730,      # 2년 보존 (감사용)
                'archive_after_days': 365,  # 1년 후 아카이브
                'cleanup_frequency': 'monthly'
            }
        }
    
    def _initialize_database(self):
        """데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 데이터 라이프사이클 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_lifecycle (
                    id TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    archived_at TIMESTAMP NULL,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"데이터베이스 초기화 오류: {str(e)}")
    
    def track_data_access(self, data_id: str, data_type: str):
        """데이터 접근 추적"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 기존 레코드 확인
            cursor.execute(
                'SELECT access_count FROM data_lifecycle WHERE id = ? AND data_type = ?',
                (data_id, data_type)
            )
            result = cursor.fetchone()
            
            if result:
                # 기존 레코드 업데이트
                cursor.execute('''
                    UPDATE data_lifecycle 
                    SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                    WHERE id = ? AND data_type = ?
                ''', (data_id, data_type))
            else:
                # 새 레코드 생성
                cursor.execute('''
                    INSERT INTO data_lifecycle (id, data_type)
                    VALUES (?, ?)
                ''', (data_id, data_type))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"데이터 접근 추적 오류: {str(e)}")
    
    def cleanup_stale_data(self, data_type: str = None) -> Dict[str, int]:
        """오래된 데이터 정리"""
        
        cleanup_stats = {
            'archived_count': 0,
            'deleted_count': 0,
            'error_count': 0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            policies_to_process = (
                {data_type: self.retention_policies[data_type]} 
                if data_type and data_type in self.retention_policies
                else self.retention_policies
            )
            
            for dtype, policy in policies_to_process.items():
                retention_days = policy['retention_days']
                archive_days = policy['archive_after_days']
                
                # 아카이브 대상 식별
                cursor.execute('''
                    SELECT id FROM data_lifecycle 
                    WHERE data_type = ? 
                    AND status = 'active'
                    AND created_at < datetime('now', '-{} days')
                    AND archived_at IS NULL
                '''.format(archive_days), (dtype,))
                
                archive_candidates = cursor.fetchall()
                
                for (data_id,) in archive_candidates:
                    # 아카이브 처리
                    if self._archive_data(data_id, dtype):
                        cursor.execute('''
                            UPDATE data_lifecycle 
                            SET archived_at = CURRENT_TIMESTAMP, status = 'archived'
                            WHERE id = ? AND data_type = ?
                        ''', (data_id, dtype))
                        cleanup_stats['archived_count'] += 1
                    else:
                        cleanup_stats['error_count'] += 1
                
                # 삭제 대상 식별
                cursor.execute('''
                    SELECT id FROM data_lifecycle 
                    WHERE data_type = ? 
                    AND created_at < datetime('now', '-{} days')
                '''.format(retention_days), (dtype,))
                
                delete_candidates = cursor.fetchall()
                
                for (data_id,) in delete_candidates:
                    # 데이터 삭제
                    if self._delete_data(data_id, dtype):
                        cursor.execute('''
                            DELETE FROM data_lifecycle 
                            WHERE id = ? AND data_type = ?
                        ''', (data_id, dtype))
                        cleanup_stats['deleted_count'] += 1
                    else:
                        cleanup_stats['error_count'] += 1
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"데이터 정리 오류: {str(e)}")
            cleanup_stats['error_count'] += 1
        
        return cleanup_stats
    
    def _archive_data(self, data_id: str, data_type: str) -> bool:
        """데이터 아카이브"""
        # 실제 구현에서는 클라우드 스토리지 등으로 이동
        self.logger.info(f"아카이브: {data_type}:{data_id}")
        return True
    
    def _delete_data(self, data_id: str, data_type: str) -> bool:
        """데이터 삭제"""
        # 실제 구현에서는 실제 데이터 삭제
        self.logger.info(f"삭제: {data_type}:{data_id}")
        return True
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """데이터 통계 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # 데이터 타입별 통계
            cursor.execute('''
                SELECT data_type, status, COUNT(*) as count
                FROM data_lifecycle 
                GROUP BY data_type, status
            ''')
            
            for data_type, status, count in cursor.fetchall():
                if data_type not in stats:
                    stats[data_type] = {}
                stats[data_type][status] = count
            
            # 전체 통계
            cursor.execute('SELECT COUNT(*) FROM data_lifecycle')
            total_records = cursor.fetchone()[0]
            
            cursor.execute('SELECT AVG(access_count) FROM data_lifecycle')
            avg_access = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'total_records': total_records,
                'average_access_count': avg_access,
                'by_type_and_status': stats,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"통계 조회 오류: {str(e)}")
            return {}


class DataQualityManager:
    """종합 데이터 품질 관리자"""
    
    def __init__(self, db_path: str = None):
        self.logger = logging.getLogger(__name__)
        
        # 컴포넌트 초기화
        self.integrity_validator = DataIntegrityValidator()
        self.duplicate_detector = DuplicateDetector()
        self.outlier_detector = OutlierDetector()
        self.lifecycle_manager = DataLifecycleManager(db_path)
        
        # 품질 지표 추적
        self.quality_metrics = {}
        self.quality_issues = []
        
        # 목표 품질 지표 (99% 신뢰도 목표)
        self.target_metrics = {
            'data_completeness': 0.99,     # 99% 완성도
            'data_accuracy': 0.99,         # 99% 정확도  
            'data_consistency': 0.98,      # 98% 일관성
            'duplicate_rate': 0.01,        # 1% 이하 중복률
            'outlier_rate': 0.02,          # 2% 이하 이상치율
            'freshness_score': 0.95        # 95% 데이터 신선도
        }
    
    def process_data_batch(
        self, 
        data_batch: List[Dict[str, Any]], 
        data_type: str,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """데이터 배치 처리"""
        
        options = options or {}
        start_time = datetime.now()
        
        try:
            self.logger.info(f"데이터 배치 처리 시작: {len(data_batch)}개 레코드, 타입: {data_type}")
            
            processing_results = {
                'input_count': len(data_batch),
                'output_count': 0,
                'quality_issues': [],
                'processing_time_seconds': 0,
                'quality_score': 0.0,
                'recommendations': []
            }
            
            current_data = data_batch.copy()
            
            # 1. 데이터 무결성 검증
            if options.get('validate_integrity', True):
                validated_data, integrity_issues = self._validate_batch_integrity(current_data, data_type)
                current_data = validated_data
                processing_results['quality_issues'].extend(integrity_issues)
            
            # 2. 중복 제거
            if options.get('remove_duplicates', True):
                dedup_strategy = options.get('dedup_strategy', 'exact_match')
                deduplicated_data, duplicate_issues = self.duplicate_detector.detect_duplicates(
                    current_data, dedup_strategy
                )
                current_data = deduplicated_data
                processing_results['quality_issues'].extend(duplicate_issues)
            
            # 3. 이상치 탐지
            if options.get('detect_outliers', True):
                numeric_fields = options.get('numeric_fields', ['subscriber_count', 'view_count', 'video_count'])
                outlier_method = options.get('outlier_method', 'iqr')
                clean_data, outlier_issues = self.outlier_detector.detect_outliers(
                    current_data, numeric_fields, outlier_method
                )
                # 이상치는 플래그만 하고 제거하지 않음
                processing_results['quality_issues'].extend(outlier_issues)
            
            # 4. 데이터 라이프사이클 추적
            for record in current_data:
                record_id = record.get('channel_id') or record.get('video_id') or str(hash(str(record)))
                self.lifecycle_manager.track_data_access(record_id, data_type)
            
            # 5. 품질 지표 계산
            quality_score = self._calculate_quality_score(
                processing_results['input_count'],
                len(current_data),
                processing_results['quality_issues']
            )
            
            # 6. 결과 준비
            processing_results.update({
                'output_count': len(current_data),
                'processing_time_seconds': (datetime.now() - start_time).total_seconds(),
                'quality_score': quality_score,
                'recommendations': self._generate_quality_recommendations(processing_results['quality_issues'])
            })
            
            # 7. 품질 지표 업데이트
            self._update_quality_metrics(data_type, processing_results)
            
            self.logger.info(
                f"데이터 배치 처리 완료: {processing_results['input_count']} → "
                f"{processing_results['output_count']} (품질점수: {quality_score:.3f})"
            )
            
            return {
                'processed_data': current_data,
                'processing_results': processing_results
            }
            
        except Exception as e:
            self.logger.error(f"데이터 배치 처리 오류: {str(e)}")
            return {
                'processed_data': [],
                'processing_results': {
                    'error': str(e),
                    'input_count': len(data_batch),
                    'output_count': 0,
                    'quality_score': 0.0
                }
            }
    
    def _validate_batch_integrity(
        self, 
        data: List[Dict], 
        data_type: str
    ) -> Tuple[List[Dict], List[QualityIssueRecord]]:
        """배치 무결성 검증"""
        
        valid_records = []
        all_issues = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 병렬 검증
            futures = []
            for record in data:
                future = executor.submit(
                    self.integrity_validator.validate_record, 
                    record, 
                    data_type
                )
                futures.append((future, record))
            
            for future, record in futures:
                try:
                    is_valid, issues = future.result(timeout=30)
                    if is_valid:
                        valid_records.append(record)
                    all_issues.extend(issues)
                except Exception as e:
                    self.logger.warning(f"검증 실패: {str(e)}")
                    # 검증 실패 시 포함 (관대한 정책)
                    valid_records.append(record)
        
        return valid_records, all_issues
    
    def _calculate_quality_score(
        self, 
        input_count: int, 
        output_count: int, 
        issues: List[QualityIssueRecord]
    ) -> float:
        """품질 점수 계산"""
        
        if input_count == 0:
            return 1.0
        
        # 기본 점수 (데이터 보존율)
        preservation_rate = output_count / input_count
        
        # 이슈 심각도별 페널티
        severity_penalties = {
            DataQualitySeverity.CRITICAL: 0.1,
            DataQualitySeverity.HIGH: 0.05,
            DataQualitySeverity.MEDIUM: 0.02,
            DataQualitySeverity.LOW: 0.01,
            DataQualitySeverity.INFO: 0.005
        }
        
        total_penalty = 0
        for issue in issues:
            penalty = severity_penalties.get(issue.severity, 0.01)
            total_penalty += penalty
        
        # 품질 점수 계산 (0.0 ~ 1.0)
        quality_score = preservation_rate - (total_penalty / input_count)
        return max(0.0, min(1.0, quality_score))
    
    def _generate_quality_recommendations(
        self, 
        issues: List[QualityIssueRecord]
    ) -> List[str]:
        """품질 개선 권장사항 생성"""
        
        recommendations = []
        issue_counts = Counter(issue.issue_type for issue in issues)
        
        # 이슈 빈도별 권장사항
        for issue_type, count in issue_counts.most_common():
            if count > 5:  # 빈발 이슈만 권장사항 생성
                if issue_type == DataQualityIssue.MISSING_VALUES:
                    recommendations.append(f"필수 필드 누락 {count}건 - 데이터 수집 프로세스 점검 필요")
                elif issue_type == DataQualityIssue.DUPLICATE_RECORDS:
                    recommendations.append(f"중복 레코드 {count}건 - 중복 제거 프로세스 강화 필요")
                elif issue_type == DataQualityIssue.OUTLIER_DETECTED:
                    recommendations.append(f"이상치 {count}건 - 데이터 수집 범위 재검토 필요")
                elif issue_type == DataQualityIssue.INVALID_FORMAT:
                    recommendations.append(f"형식 오류 {count}건 - 입력 검증 로직 강화 필요")
        
        return recommendations
    
    def _update_quality_metrics(self, data_type: str, processing_results: Dict):
        """품질 지표 업데이트"""
        
        timestamp = datetime.now()
        
        # 데이터 완성도
        completeness = processing_results['output_count'] / processing_results['input_count'] if processing_results['input_count'] > 0 else 1.0
        
        # 정확도 (이슈 기반)
        critical_issues = len([i for i in processing_results['quality_issues'] if i.severity == DataQualitySeverity.CRITICAL])
        accuracy = 1.0 - (critical_issues / processing_results['input_count']) if processing_results['input_count'] > 0 else 1.0
        
        # 중복률
        duplicate_issues = len([i for i in processing_results['quality_issues'] if i.issue_type == DataQualityIssue.DUPLICATE_RECORDS])
        duplicate_rate = duplicate_issues / processing_results['input_count'] if processing_results['input_count'] > 0 else 0.0
        
        # 이상치율
        outlier_issues = len([i for i in processing_results['quality_issues'] if i.issue_type == DataQualityIssue.OUTLIER_DETECTED])
        outlier_rate = outlier_issues / processing_results['input_count'] if processing_results['input_count'] > 0 else 0.0
        
        # 메트릭 저장
        self.quality_metrics[data_type] = {
            'data_completeness': QualityMetric(
                metric_name='data_completeness',
                current_value=completeness,
                target_value=self.target_metrics['data_completeness'],
                threshold_warning=0.95,
                threshold_critical=0.90,
                measurement_time=timestamp
            ),
            'data_accuracy': QualityMetric(
                metric_name='data_accuracy',
                current_value=accuracy,
                target_value=self.target_metrics['data_accuracy'],
                threshold_warning=0.95,
                threshold_critical=0.90,
                measurement_time=timestamp
            ),
            'duplicate_rate': QualityMetric(
                metric_name='duplicate_rate',
                current_value=duplicate_rate,
                target_value=self.target_metrics['duplicate_rate'],
                threshold_warning=0.02,
                threshold_critical=0.05,
                measurement_time=timestamp
            ),
            'outlier_rate': QualityMetric(
                metric_name='outlier_rate',
                current_value=outlier_rate,
                target_value=self.target_metrics['outlier_rate'],
                threshold_warning=0.03,
                threshold_critical=0.05,
                measurement_time=timestamp
            )
        }
    
    def get_quality_dashboard(self) -> Dict[str, Any]:
        """품질 대시보드 데이터 생성"""
        
        dashboard_data = {
            'overall_quality_score': 0.0,
            'target_achievement': {},
            'quality_trends': {},
            'top_issues': [],
            'recommendations': [],
            'data_statistics': self.lifecycle_manager.get_data_statistics(),
            'last_updated': datetime.now().isoformat()
        }
        
        # 전체 품질 점수 계산
        if self.quality_metrics:
            all_scores = []
            for data_type, metrics in self.quality_metrics.items():
                type_scores = [m.current_value for m in metrics.values() 
                             if m.metric_name in ['data_completeness', 'data_accuracy']]
                if type_scores:
                    all_scores.extend(type_scores)
            
            if all_scores:
                dashboard_data['overall_quality_score'] = np.mean(all_scores)
        
        # 목표 달성률
        for target_name, target_value in self.target_metrics.items():
            achieved_count = 0
            total_count = 0
            
            for data_type, metrics in self.quality_metrics.items():
                if target_name in metrics:
                    metric = metrics[target_name]
                    total_count += 1
                    
                    # 비율 메트릭은 역방향 계산
                    if target_name in ['duplicate_rate', 'outlier_rate']:
                        if metric.current_value <= target_value:
                            achieved_count += 1
                    else:
                        if metric.current_value >= target_value:
                            achieved_count += 1
            
            if total_count > 0:
                dashboard_data['target_achievement'][target_name] = {
                    'achievement_rate': achieved_count / total_count,
                    'target_value': target_value,
                    'achieved_count': achieved_count,
                    'total_count': total_count
                }
        
        # 상위 이슈
        recent_issues = [issue for issue in self.quality_issues 
                        if (datetime.now() - issue.detected_at).days <= 7]
        
        issue_summary = Counter()
        for issue in recent_issues:
            issue_summary[f"{issue.issue_type.value}_{issue.severity.value}"] += 1
        
        dashboard_data['top_issues'] = [
            {'issue_pattern': pattern, 'count': count}
            for pattern, count in issue_summary.most_common(10)
        ]
        
        # 권장사항 (최근 이슈 기반)
        dashboard_data['recommendations'] = self._generate_quality_recommendations(recent_issues)
        
        return dashboard_data
    
    def run_quality_audit(self, data_type: str = None) -> Dict[str, Any]:
        """품질 감사 실행"""
        
        audit_results = {
            'audit_timestamp': datetime.now().isoformat(),
            'data_types_audited': [],
            'overall_status': 'PASS',
            'critical_issues_count': 0,
            'recommendations': [],
            'compliance_score': 0.0
        }
        
        try:
            # 데이터 정리 실행
            cleanup_stats = self.lifecycle_manager.cleanup_stale_data(data_type)
            audit_results['cleanup_stats'] = cleanup_stats
            
            # 품질 지표 평가
            compliance_scores = []
            critical_issues = 0
            
            metrics_to_audit = (
                {data_type: self.quality_metrics[data_type]} 
                if data_type and data_type in self.quality_metrics
                else self.quality_metrics
            )
            
            for dtype, metrics in metrics_to_audit.items():
                audit_results['data_types_audited'].append(dtype)
                
                for metric_name, metric in metrics.items():
                    # 임계값 확인
                    if metric.current_value < metric.threshold_critical:
                        critical_issues += 1
                        audit_results['overall_status'] = 'FAIL'
                    elif metric.current_value < metric.threshold_warning:
                        if audit_results['overall_status'] == 'PASS':
                            audit_results['overall_status'] = 'WARNING'
                    
                    # 목표 대비 달성률 계산
                    if metric_name in ['duplicate_rate', 'outlier_rate']:
                        achievement = min(1.0, metric.target_value / max(metric.current_value, 0.001))
                    else:
                        achievement = min(1.0, metric.current_value / metric.target_value)
                    
                    compliance_scores.append(achievement)
            
            audit_results['critical_issues_count'] = critical_issues
            audit_results['compliance_score'] = np.mean(compliance_scores) if compliance_scores else 0.0
            
            # 감사 권장사항
            if critical_issues > 0:
                audit_results['recommendations'].append("즉시 조치 필요한 임계값 위반 이슈 해결")
            
            if audit_results['compliance_score'] < 0.95:
                audit_results['recommendations'].append("품질 목표 달성을 위한 프로세스 개선 필요")
            
            if cleanup_stats['error_count'] > 0:
                audit_results['recommendations'].append("데이터 정리 프로세스 점검 필요")
            
            self.logger.info(
                f"품질 감사 완료: {audit_results['overall_status']} "
                f"(점수: {audit_results['compliance_score']:.3f})"
            )
            
            return audit_results
            
        except Exception as e:
            self.logger.error(f"품질 감사 오류: {str(e)}")
            audit_results.update({
                'overall_status': 'ERROR',
                'error': str(e)
            })
            return audit_results