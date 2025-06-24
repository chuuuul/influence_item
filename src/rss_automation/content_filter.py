"""
컨텐츠 필터링 시스템

PRD 2.2 요구사항:
- 미디어 채널은 영상 제목에 등록된 연예인 이름 포함된 경우만 수집
- YouTube 쇼츠는 분석 대상에서 명시적으로 제외
- PPL 콘텐츠 사전 필터링
"""

import re
import sqlite3
import logging
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
import json
from datetime import datetime


@dataclass
class CelebrityInfo:
    """연예인 정보"""
    name: str
    aliases: List[str]  # 별명, 예명 등
    group_name: Optional[str] = None
    is_active: bool = True


@dataclass
class FilterResult:
    """필터링 결과"""
    passed: bool
    reason: str
    confidence: float
    matched_names: List[str] = None


class ContentFilter:
    """컨텐츠 필터링 시스템"""
    
    def __init__(self, db_path: str = "influence_item.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._setup_database()
        self._load_celebrity_data()
        self._load_filter_patterns()
    
    def _setup_database(self) -> None:
        """데이터베이스 테이블 설정"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 연예인 정보 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS celebrities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    aliases TEXT,  -- JSON array
                    group_name TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 필터링 패턴 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filter_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL CHECK (pattern_type IN ('celebrity_name', 'shorts_indicator', 'ppl_keyword')),
                    pattern TEXT NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 필터링 로그 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filter_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    video_title TEXT,
                    filter_type TEXT NOT NULL,
                    filter_result TEXT NOT NULL CHECK (filter_result IN ('pass', 'block')),
                    reason TEXT,
                    confidence REAL,
                    matched_patterns TEXT,  -- JSON array
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            
            # 기본 데이터 삽입
            self._insert_default_data(cursor)
            conn.commit()
    
    def _insert_default_data(self, cursor) -> None:
        """기본 데이터 삽입"""
        # 기본 연예인 데이터 (예시)
        default_celebrities = [
            # 개인 연예인
            ("강민경", json.dumps(["걍밍경", "민경", "강민경"]), "다비치"),
            ("아이유", json.dumps(["IU", "이지은", "아이유", "지은이"]), None),
            ("유재석", json.dumps(["유느님", "재석", "유재석", "개그맨"]), None),
            ("송강호", json.dumps(["송강호", "강호"]), None),
            ("박서준", json.dumps(["서준", "박서준"]), None),
            ("김고은", json.dumps(["고은", "김고은"]), None),
            
            # 그룹 멤버들
            ("RM", json.dumps(["김남준", "남준", "RM", "랩몬"]), "BTS"),
            ("진", json.dumps(["김석진", "석진", "진"]), "BTS"),
            ("슈가", json.dumps(["민윤기", "윤기", "슈가", "SUGA"]), "BTS"),
            ("제이홉", json.dumps(["정호석", "호석", "제이홉", "J-Hope"]), "BTS"),
            ("지민", json.dumps(["박지민", "지민"]), "BTS"),
            ("뷔", json.dumps(["김태형", "태형", "뷔", "V"]), "BTS"),
            ("정국", json.dumps(["전정국", "정국", "황금막내"]), "BTS"),
            
            # 블랙핑크
            ("지수", json.dumps(["김지수", "지수"]), "BLACKPINK"),
            ("제니", json.dumps(["김제니", "제니"]), "BLACKPINK"),
            ("로제", json.dumps(["박채영", "로제", "ROSÉ"]), "BLACKPINK"),
            ("리사", json.dumps(["라리사", "리사", "LISA"]), "BLACKPINK"),
        ]
        
        for name, aliases, group in default_celebrities:
            cursor.execute("""
                INSERT OR IGNORE INTO celebrities (name, aliases, group_name)
                VALUES (?, ?, ?)
            """, (name, aliases, group))
        
        # 기본 필터링 패턴
        default_patterns = [
            # 쇼츠 지시어
            ("shorts_indicator", r"#shorts", "YouTube 쇼츠 해시태그"),
            ("shorts_indicator", r"shorts", "제목에 shorts 포함"),
            ("shorts_indicator", r"쇼츠", "제목에 쇼츠 포함"),
            ("shorts_indicator", r"60초", "60초 이하 영상 지시"),
            
            # PPL 키워드
            ("ppl_keyword", r"협찬", "협찬 표시"),
            ("ppl_keyword", r"광고", "광고 표시"),
            ("ppl_keyword", r"AD", "AD 표시"),
            ("ppl_keyword", r"sponsored", "스폰서드 표시"),
            ("ppl_keyword", r"제품제공", "제품제공 표시"),
            ("ppl_keyword", r"유료광고", "유료광고 표시"),
        ]
        
        for pattern_type, pattern, description in default_patterns:
            cursor.execute("""
                INSERT OR IGNORE INTO filter_patterns (pattern_type, pattern, description)
                VALUES (?, ?, ?)
            """, (pattern_type, pattern, description))
    
    def _load_celebrity_data(self) -> None:
        """연예인 데이터 로드"""
        self.celebrities = {}
        self.celebrity_patterns = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name, aliases, group_name FROM celebrities 
                    WHERE is_active = TRUE
                """)
                
                for row in cursor.fetchall():
                    name = row[0]
                    aliases = json.loads(row[1]) if row[1] else []
                    group_name = row[2]
                    
                    # 모든 이름 변형을 패턴으로 생성
                    all_names = [name] + aliases
                    if group_name:
                        all_names.append(group_name)
                    
                    for alias in all_names:
                        # 정확한 매칭을 위한 패턴 생성
                        pattern = rf"\b{re.escape(alias)}\b"
                        self.celebrity_patterns.append((pattern, name, alias))
                        
                        # 공백 없이도 매칭되도록
                        if len(alias) > 1:
                            pattern_no_space = re.escape(alias)
                            self.celebrity_patterns.append((pattern_no_space, name, alias))
                    
                    self.celebrities[name] = CelebrityInfo(
                        name=name,
                        aliases=aliases,
                        group_name=group_name
                    )
                    
        except Exception as e:
            self.logger.error(f"연예인 데이터 로드 실패: {str(e)}")
    
    def _load_filter_patterns(self) -> None:
        """필터링 패턴 로드"""
        self.shorts_patterns = []
        self.ppl_patterns = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT pattern_type, pattern FROM filter_patterns 
                    WHERE is_active = TRUE
                """)
                
                for row in cursor.fetchall():
                    pattern_type, pattern = row
                    compiled_pattern = re.compile(pattern, re.IGNORECASE)
                    
                    if pattern_type == 'shorts_indicator':
                        self.shorts_patterns.append(compiled_pattern)
                    elif pattern_type == 'ppl_keyword':
                        self.ppl_patterns.append(compiled_pattern)
                        
        except Exception as e:
            self.logger.error(f"필터링 패턴 로드 실패: {str(e)}")
    
    def has_celebrity_name(self, text: str) -> bool:
        """텍스트에 연예인 이름이 포함되어 있는지 확인"""
        try:
            matched_names = self.find_celebrity_names(text)
            return len(matched_names) > 0
        except Exception as e:
            self.logger.error(f"연예인 이름 확인 실패: {str(e)}")
            return False
    
    def find_celebrity_names(self, text: str) -> List[str]:
        """텍스트에서 발견된 연예인 이름 목록 반환"""
        matched_names = set()
        
        try:
            for pattern, celebrity_name, alias in self.celebrity_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_names.add(celebrity_name)
                    
        except Exception as e:
            self.logger.error(f"연예인 이름 검색 실패: {str(e)}")
        
        return list(matched_names)
    
    def is_shorts_content(self, title: str, description: str = "") -> FilterResult:
        """쇼츠 콘텐츠 여부 확인"""
        combined_text = f"{title} {description}".lower()
        matched_patterns = []
        
        try:
            for pattern in self.shorts_patterns:
                if pattern.search(combined_text):
                    matched_patterns.append(pattern.pattern)
            
            if matched_patterns:
                return FilterResult(
                    passed=False,
                    reason=f"쇼츠 지시어 발견: {', '.join(matched_patterns)}",
                    confidence=0.9,
                    matched_names=matched_patterns
                )
            
            return FilterResult(
                passed=True,
                reason="쇼츠 지시어 없음",
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"쇼츠 콘텐츠 확인 실패: {str(e)}")
            return FilterResult(
                passed=True,
                reason="확인 실패",
                confidence=0.0
            )
    
    def is_ppl_content(self, title: str, description: str = "") -> FilterResult:
        """PPL 콘텐츠 여부 확인"""
        combined_text = f"{title} {description}".lower()
        matched_patterns = []
        
        try:
            for pattern in self.ppl_patterns:
                if pattern.search(combined_text):
                    matched_patterns.append(pattern.pattern)
            
            if matched_patterns:
                return FilterResult(
                    passed=False,
                    reason=f"PPL 키워드 발견: {', '.join(matched_patterns)}",
                    confidence=0.8,
                    matched_names=matched_patterns
                )
            
            return FilterResult(
                passed=True,
                reason="PPL 키워드 없음",
                confidence=0.7
            )
            
        except Exception as e:
            self.logger.error(f"PPL 콘텐츠 확인 실패: {str(e)}")
            return FilterResult(
                passed=True,
                reason="확인 실패",
                confidence=0.0
            )
    
    def filter_for_media_channel(self, title: str, description: str = "") -> FilterResult:
        """미디어 채널용 필터링 (연예인 이름 포함 여부)"""
        try:
            matched_names = self.find_celebrity_names(title)
            
            if matched_names:
                return FilterResult(
                    passed=True,
                    reason=f"연예인 이름 발견: {', '.join(matched_names)}",
                    confidence=0.9,
                    matched_names=matched_names
                )
            
            # 제목에서 찾지 못한 경우 설명에서도 확인
            if description:
                desc_matches = self.find_celebrity_names(description)
                if desc_matches:
                    return FilterResult(
                        passed=True,
                        reason=f"설명에서 연예인 이름 발견: {', '.join(desc_matches)}",
                        confidence=0.7,
                        matched_names=desc_matches
                    )
            
            return FilterResult(
                passed=False,
                reason="연예인 이름 미포함",
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"미디어 채널 필터링 실패: {str(e)}")
            return FilterResult(
                passed=False,
                reason="필터링 실패",
                confidence=0.0
            )
    
    def comprehensive_filter(self, title: str, description: str = "", 
                           channel_type: str = "personal") -> FilterResult:
        """종합 필터링"""
        try:
            # 1. 쇼츠 콘텐츠 확인
            shorts_result = self.is_shorts_content(title, description)
            if not shorts_result.passed:
                self._log_filter_result(None, title, "shorts_filter", "block", 
                                      shorts_result.reason, shorts_result.confidence, 
                                      shorts_result.matched_names)
                return shorts_result
            
            # 2. PPL 콘텐츠 확인
            ppl_result = self.is_ppl_content(title, description)
            if not ppl_result.passed:
                self._log_filter_result(None, title, "ppl_filter", "block",
                                      ppl_result.reason, ppl_result.confidence,
                                      ppl_result.matched_names)
                return ppl_result
            
            # 3. 미디어 채널인 경우 연예인 이름 확인
            if channel_type == "media":
                celebrity_result = self.filter_for_media_channel(title, description)
                if not celebrity_result.passed:
                    self._log_filter_result(None, title, "celebrity_filter", "block",
                                          celebrity_result.reason, celebrity_result.confidence,
                                          celebrity_result.matched_names)
                    return celebrity_result
                
                # 성공 로그
                self._log_filter_result(None, title, "celebrity_filter", "pass",
                                      celebrity_result.reason, celebrity_result.confidence,
                                      celebrity_result.matched_names)
            
            # 모든 필터를 통과
            final_result = FilterResult(
                passed=True,
                reason="모든 필터 통과",
                confidence=0.9
            )
            
            self._log_filter_result(None, title, "comprehensive_filter", "pass",
                                  final_result.reason, final_result.confidence, None)
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"종합 필터링 실패: {str(e)}")
            return FilterResult(
                passed=False,
                reason="필터링 오류",
                confidence=0.0
            )
    
    def _log_filter_result(self, video_id: Optional[str], video_title: str,
                          filter_type: str, result: str, reason: str,
                          confidence: float, matched_patterns: Optional[List[str]]) -> None:
        """필터링 결과 로그 기록"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO filter_logs 
                    (video_id, video_title, filter_type, filter_result, reason, 
                     confidence, matched_patterns)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    video_id, video_title, filter_type, result, reason, 
                    confidence, json.dumps(matched_patterns) if matched_patterns else None
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"필터링 로그 기록 실패: {str(e)}")
    
    def add_celebrity(self, name: str, aliases: List[str], group_name: Optional[str] = None) -> bool:
        """연예인 추가"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO celebrities (name, aliases, group_name, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (name, json.dumps(aliases), group_name))
                conn.commit()
                
                # 메모리에서도 업데이트
                self._load_celebrity_data()
                
                self.logger.info(f"연예인 추가됨: {name}")
                return True
                
        except Exception as e:
            self.logger.error(f"연예인 추가 실패: {str(e)}")
            return False
    
    def add_filter_pattern(self, pattern_type: str, pattern: str, description: str = "") -> bool:
        """필터링 패턴 추가"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO filter_patterns (pattern_type, pattern, description)
                    VALUES (?, ?, ?)
                """, (pattern_type, pattern, description))
                conn.commit()
                
                # 메모리에서도 업데이트
                self._load_filter_patterns()
                
                self.logger.info(f"필터링 패턴 추가됨: {pattern_type} - {pattern}")
                return True
                
        except Exception as e:
            self.logger.error(f"필터링 패턴 추가 실패: {str(e)}")
            return False
    
    def get_filter_statistics(self, days: int = 7) -> Dict[str, Any]:
        """필터링 통계 조회"""
        stats = {
            'total_filtered': 0,
            'filter_breakdown': {},
            'celebrity_matches': {},
            'daily_stats': []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 필터 유형별 통계
                cursor.execute("""
                    SELECT filter_type, filter_result, COUNT(*) as count
                    FROM filter_logs
                    WHERE DATE(created_at) >= DATE('now', '-{} days')
                    GROUP BY filter_type, filter_result
                """.format(days))
                
                for row in cursor.fetchall():
                    filter_type, result, count = row
                    if filter_type not in stats['filter_breakdown']:
                        stats['filter_breakdown'][filter_type] = {'pass': 0, 'block': 0}
                    stats['filter_breakdown'][filter_type][result] = count
                    
                    if result == 'block':
                        stats['total_filtered'] += count
                
                # 연예인별 매칭 통계
                cursor.execute("""
                    SELECT reason, COUNT(*) as count
                    FROM filter_logs
                    WHERE filter_type = 'celebrity_filter' 
                    AND filter_result = 'pass'
                    AND DATE(created_at) >= DATE('now', '-{} days')
                    GROUP BY reason
                    ORDER BY count DESC
                    LIMIT 10
                """.format(days))
                
                for row in cursor.fetchall():
                    reason, count = row
                    stats['celebrity_matches'][reason] = count
                
        except Exception as e:
            self.logger.error(f"필터링 통계 조회 실패: {str(e)}")
        
        return stats