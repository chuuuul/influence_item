"""
PPL 패턴 관리 시스템

패턴 추가, 수정, 삭제 및 버전 관리를 담당합니다.
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging
import shutil

from .pattern_definitions import PPLPattern


class PatternManager:
    """PPL 패턴 관리자"""
    
    def __init__(self, config_path: str = "config/ppl_patterns.json"):
        """
        Args:
            config_path: 패턴 설정 파일 경로
        """
        self.config_path = config_path
        self.backup_dir = "config/backups"
        self.logger = logging.getLogger(__name__)
        
        # 백업 디렉토리 생성
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def add_pattern(self, category: str, pattern: str, weight: float, 
                   description: str) -> bool:
        """새 패턴 추가"""
        try:
            # 현재 설정 로드
            config = self._load_config()
            
            # 백업 생성
            self._create_backup()
            
            # 패턴 추가 로직
            if "custom_patterns" not in config:
                config["custom_patterns"] = {}
            
            if category not in config["custom_patterns"]:
                config["custom_patterns"][category] = []
            
            new_pattern = {
                "pattern": pattern,
                "weight": weight,
                "category": category,
                "description": description,
                "added_date": datetime.now().isoformat(),
                "version": config.get("pattern_config", {}).get("version", "1.0")
            }
            
            config["custom_patterns"][category].append(new_pattern)
            
            # 설정 저장
            self._save_config(config)
            
            self.logger.info(f"패턴 추가 완료: {pattern} (카테고리: {category})")
            return True
            
        except Exception as e:
            self.logger.error(f"패턴 추가 실패: {e}")
            return False
    
    def remove_pattern(self, category: str, pattern: str) -> bool:
        """패턴 제거"""
        try:
            config = self._load_config()
            self._create_backup()
            
            if "custom_patterns" in config and category in config["custom_patterns"]:
                config["custom_patterns"][category] = [
                    p for p in config["custom_patterns"][category] 
                    if p["pattern"] != pattern
                ]
                
                # 빈 카테고리 제거
                if not config["custom_patterns"][category]:
                    del config["custom_patterns"][category]
                
                self._save_config(config)
                self.logger.info(f"패턴 제거 완료: {pattern}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"패턴 제거 실패: {e}")
            return False
    
    def update_pattern_weight(self, category: str, pattern: str, new_weight: float) -> bool:
        """패턴 가중치 업데이트"""
        try:
            config = self._load_config()
            self._create_backup()
            
            updated = False
            
            # 커스텀 패턴에서 검색
            if "custom_patterns" in config and category in config["custom_patterns"]:
                for p in config["custom_patterns"][category]:
                    if p["pattern"] == pattern:
                        p["weight"] = new_weight
                        p["last_modified"] = datetime.now().isoformat()
                        updated = True
                        break
            
            # 기본 패턴 가중치 오버라이드
            if not updated:
                if "pattern_overrides" not in config:
                    config["pattern_overrides"] = {}
                
                if category not in config["pattern_overrides"]:
                    config["pattern_overrides"][category] = {}
                
                config["pattern_overrides"][category][pattern] = {
                    "weight": new_weight,
                    "modified_date": datetime.now().isoformat()
                }
                updated = True
            
            if updated:
                self._save_config(config)
                self.logger.info(f"패턴 가중치 업데이트: {pattern} -> {new_weight}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"패턴 가중치 업데이트 실패: {e}")
            return False
    
    def get_pattern_statistics(self) -> Dict:
        """패턴 통계 정보 반환"""
        try:
            config = self._load_config()
            
            stats = {
                "total_categories": 0,
                "total_patterns": 0,
                "custom_patterns": 0,
                "pattern_overrides": 0,
                "categories": {},
                "last_updated": config.get("pattern_config", {}).get("last_updated", "unknown")
            }
            
            # 커스텀 패턴 통계
            if "custom_patterns" in config:
                for category, patterns in config["custom_patterns"].items():
                    stats["categories"][category] = len(patterns)
                    stats["custom_patterns"] += len(patterns)
                    stats["total_categories"] += 1
                    stats["total_patterns"] += len(patterns)
            
            # 오버라이드 통계
            if "pattern_overrides" in config:
                for category, overrides in config["pattern_overrides"].items():
                    stats["pattern_overrides"] += len(overrides)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"통계 생성 실패: {e}")
            return {}
    
    def validate_patterns(self) -> Dict:
        """패턴 유효성 검증"""
        try:
            config = self._load_config()
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "total_patterns": 0,
                "valid_patterns": 0
            }
            
            # 커스텀 패턴 검증
            if "custom_patterns" in config:
                for category, patterns in config["custom_patterns"].items():
                    for pattern in patterns:
                        validation_results["total_patterns"] += 1
                        
                        # 필수 필드 확인
                        required_fields = ["pattern", "weight", "category", "description"]
                        for field in required_fields:
                            if field not in pattern:
                                validation_results["errors"].append(
                                    f"패턴 '{pattern.get('pattern', 'unknown')}'에 필수 필드 '{field}' 누락"
                                )
                                validation_results["valid"] = False
                                continue
                        
                        # 가중치 범위 확인
                        if not 0.0 <= pattern["weight"] <= 1.0:
                            validation_results["warnings"].append(
                                f"패턴 '{pattern['pattern']}'의 가중치가 범위를 벗어남: {pattern['weight']}"
                            )
                        
                        # 패턴 중복 확인 (간단한 체크)
                        pattern_text = pattern["pattern"].lower()
                        if len(pattern_text) < 2:
                            validation_results["warnings"].append(
                                f"패턴 '{pattern['pattern']}'이 너무 짧음"
                            )
                        
                        if not validation_results["errors"]:
                            validation_results["valid_patterns"] += 1
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"패턴 검증 실패: {e}")
            return {"valid": False, "errors": [str(e)]}
    
    def export_patterns(self, export_path: str) -> bool:
        """패턴을 파일로 내보내기"""
        try:
            config = self._load_config()
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "version": config.get("pattern_config", {}).get("version", "1.0"),
                "patterns": config.get("custom_patterns", {}),
                "overrides": config.get("pattern_overrides", {}),
                "metadata": {
                    "total_patterns": sum(
                        len(patterns) for patterns in config.get("custom_patterns", {}).values()
                    ),
                    "total_categories": len(config.get("custom_patterns", {}))
                }
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"패턴 내보내기 완료: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"패턴 내보내기 실패: {e}")
            return False
    
    def import_patterns(self, import_path: str, merge: bool = True) -> bool:
        """패턴을 파일에서 가져오기"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            config = self._load_config()
            self._create_backup()
            
            if merge:
                # 기존 패턴과 병합
                if "custom_patterns" not in config:
                    config["custom_patterns"] = {}
                
                for category, patterns in import_data.get("patterns", {}).items():
                    if category not in config["custom_patterns"]:
                        config["custom_patterns"][category] = []
                    
                    # 중복 제거하면서 추가
                    existing_patterns = {p["pattern"] for p in config["custom_patterns"][category]}
                    for pattern in patterns:
                        if pattern["pattern"] not in existing_patterns:
                            config["custom_patterns"][category].append(pattern)
            else:
                # 완전 교체
                config["custom_patterns"] = import_data.get("patterns", {})
                config["pattern_overrides"] = import_data.get("overrides", {})
            
            self._save_config(config)
            self.logger.info(f"패턴 가져오기 완료: {import_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"패턴 가져오기 실패: {e}")
            return False
    
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"pattern_config": {"version": "1.0"}}
    
    def _save_config(self, config: Dict) -> None:
        """설정 파일 저장"""
        config["pattern_config"]["last_updated"] = datetime.now().isoformat()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def _create_backup(self) -> str:
        """현재 설정의 백업 생성"""
        if os.path.exists(self.config_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"ppl_patterns_{timestamp}.json")
            shutil.copy2(self.config_path, backup_path)
            return backup_path
        return ""
    
    def list_backups(self) -> List[str]:
        """백업 파일 목록 반환"""
        if not os.path.exists(self.backup_dir):
            return []
        
        backups = [f for f in os.listdir(self.backup_dir) if f.endswith('.json')]
        return sorted(backups, reverse=True)  # 최신순 정렬
    
    def restore_backup(self, backup_filename: str) -> bool:
        """백업에서 복원"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.config_path)
                self.logger.info(f"백업 복원 완료: {backup_filename}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"백업 복원 실패: {e}")
            return False