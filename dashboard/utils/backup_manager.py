"""
T05_S02_M02: 자동 백업 및 복구 시스템
운영 안정성을 위한 데이터베이스 백업 및 복구 기능
"""

import os
import sqlite3
import shutil
import gzip
import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import time

logger = logging.getLogger(__name__)


class BackupManager:
    """데이터베이스 백업 및 복구 관리자"""
    
    def __init__(self, db_path: str = "influence_item.db", backup_dir: str = "backups"):
        """
        Args:
            db_path: 원본 데이터베이스 파일 경로
            backup_dir: 백업 파일 저장 디렉토리
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # 백업 보존 정책
        self.retention_policy = {
            "daily": {"count": 7, "pattern": "daily_%Y%m%d_%H%M%S"},
            "weekly": {"count": 4, "pattern": "weekly_%Y_W%U"},
            "monthly": {"count": 12, "pattern": "monthly_%Y%m"}
        }
        
        self._lock = threading.Lock()
        
    def create_backup(self, backup_type: str = "manual", description: str = "") -> Dict[str, Any]:
        """
        백업 생성
        
        Args:
            backup_type: 백업 유형 (manual, daily, weekly, monthly)
            description: 백업 설명
            
        Returns:
            백업 결과 정보
        """
        try:
            with self._lock:
                start_time = time.time()
                timestamp = datetime.now()
                
                # 백업 파일명 생성
                if backup_type in self.retention_policy:
                    pattern = self.retention_policy[backup_type]["pattern"]
                    backup_name = timestamp.strftime(pattern)
                else:
                    backup_name = f"manual_{timestamp.strftime('%Y%m%d_%H%M%S')}"
                
                backup_file = self.backup_dir / f"{backup_name}.db.gz"
                metadata_file = self.backup_dir / f"{backup_name}.meta.json"
                
                # 원본 데이터베이스 크기 확인
                if not self.db_path.exists():
                    raise FileNotFoundError(f"Database file not found: {self.db_path}")
                
                original_size = self.db_path.stat().st_size
                
                # 데이터베이스 백업 (압축)
                with open(self.db_path, 'rb') as f_in:
                    with gzip.open(backup_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # 백업 파일 해시 계산
                backup_hash = self._calculate_file_hash(backup_file)
                compressed_size = backup_file.stat().st_size
                
                # 메타데이터 생성
                metadata = {
                    "backup_id": f"{backup_name}_{int(timestamp.timestamp())}",
                    "backup_type": backup_type,
                    "description": description,
                    "timestamp": timestamp.isoformat(),
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": compressed_size / original_size if original_size > 0 else 0,
                    "backup_file": str(backup_file),
                    "backup_hash": backup_hash,
                    "database_schema_version": self._get_schema_version(),
                    "record_counts": self._get_record_counts(),
                    "creation_time": time.time() - start_time
                }
                
                # 메타데이터 저장
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                # 백업 검증
                verification_result = self._verify_backup(backup_file, metadata)
                metadata["verification"] = verification_result
                
                # 메타데이터 재저장 (검증 결과 포함)
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                # 보존 정책 적용
                if backup_type in self.retention_policy:
                    self._apply_retention_policy(backup_type)
                
                logger.info(f"Backup created successfully: {backup_file}")
                return metadata
                
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return {"error": str(e), "success": False}
    
    def restore_backup(self, backup_id: str, target_db: str = None) -> Dict[str, Any]:
        """
        백업에서 복구
        
        Args:
            backup_id: 백업 ID 또는 백업 파일 패턴
            target_db: 복구할 대상 데이터베이스 (None이면 원본 복구)
            
        Returns:
            복구 결과 정보
        """
        try:
            start_time = time.time()
            
            # 백업 파일 찾기
            backup_file, metadata = self._find_backup(backup_id)
            if not backup_file:
                raise FileNotFoundError(f"Backup not found: {backup_id}")
            
            # 백업 파일 검증
            verification_result = self._verify_backup(backup_file, metadata)
            if not verification_result["valid"]:
                raise ValueError(f"Backup verification failed: {verification_result}")
            
            # 대상 데이터베이스 경로 설정
            target_path = Path(target_db) if target_db else self.db_path
            backup_original = target_path.with_suffix('.bak')
            
            # 기존 데이터베이스 백업 (복구 실패 시 롤백용)
            if target_path.exists():
                shutil.copy2(target_path, backup_original)
            
            try:
                # 압축된 백업 파일 복구
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(target_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # 복구된 데이터베이스 검증
                restore_verification = self._verify_restored_database(target_path, metadata)
                
                if restore_verification["valid"]:
                    # 성공 시 백업 파일 삭제
                    if backup_original.exists():
                        backup_original.unlink()
                    
                    restore_result = {
                        "success": True,
                        "backup_id": backup_id,
                        "restored_to": str(target_path),
                        "restore_time": time.time() - start_time,
                        "metadata": metadata,
                        "verification": restore_verification
                    }
                    
                    logger.info(f"Database restored successfully from backup: {backup_id}")
                    return restore_result
                else:
                    # 검증 실패 시 롤백
                    if backup_original.exists():
                        shutil.move(backup_original, target_path)
                    raise ValueError(f"Restored database verification failed: {restore_verification}")
                    
            except Exception as e:
                # 복구 실패 시 롤백
                if backup_original.exists():
                    shutil.move(backup_original, target_path)
                raise e
                
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return {"error": str(e), "success": False}
    
    def list_backups(self, backup_type: str = None) -> List[Dict[str, Any]]:
        """
        백업 목록 조회
        
        Args:
            backup_type: 특정 백업 유형만 조회 (None이면 전체)
            
        Returns:
            백업 목록
        """
        try:
            backups = []
            
            for meta_file in self.backup_dir.glob("*.meta.json"):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    if backup_type is None or metadata.get("backup_type") == backup_type:
                        # 백업 파일 존재 여부 확인
                        backup_file = Path(metadata.get("backup_file", ""))
                        metadata["file_exists"] = backup_file.exists() if backup_file else False
                        metadata["file_size_mb"] = round(metadata.get("compressed_size", 0) / 1024 / 1024, 2)
                        
                        backups.append(metadata)
                        
                except Exception as e:
                    logger.warning(f"Failed to read backup metadata {meta_file}: {e}")
            
            # 타임스탬프로 정렬 (최신순)
            backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def delete_backup(self, backup_id: str) -> bool:
        """
        백업 삭제
        
        Args:
            backup_id: 삭제할 백업 ID
            
        Returns:
            삭제 성공 여부
        """
        try:
            backup_file, metadata = self._find_backup(backup_id)
            if not backup_file:
                logger.warning(f"Backup not found for deletion: {backup_id}")
                return False
            
            # 백업 파일 삭제
            if backup_file.exists():
                backup_file.unlink()
            
            # 메타데이터 파일 삭제
            meta_file = backup_file.with_suffix('.meta.json')
            if meta_file.exists():
                meta_file.unlink()
            
            logger.info(f"Backup deleted: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False
    
    def get_backup_statistics(self) -> Dict[str, Any]:
        """백업 통계 정보 조회"""
        try:
            backups = self.list_backups()
            
            if not backups:
                return {"total_backups": 0}
            
            total_size = sum(b.get("compressed_size", 0) for b in backups)
            by_type = {}
            
            for backup in backups:
                backup_type = backup.get("backup_type", "unknown")
                if backup_type not in by_type:
                    by_type[backup_type] = {"count": 0, "size": 0}
                by_type[backup_type]["count"] += 1
                by_type[backup_type]["size"] += backup.get("compressed_size", 0)
            
            return {
                "total_backups": len(backups),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "latest_backup": backups[0].get("timestamp") if backups else None,
                "oldest_backup": backups[-1].get("timestamp") if backups else None,
                "by_type": by_type,
                "average_compression_ratio": sum(b.get("compression_ratio", 0) for b in backups) / len(backups)
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup statistics: {e}")
            return {"error": str(e)}
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """파일 해시 계산"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _get_schema_version(self) -> str:
        """데이터베이스 스키마 버전 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("PRAGMA user_version")
            version = cursor.fetchone()[0]
            conn.close()
            return str(version)
        except Exception as e:
            logger.warning(f"Failed to get schema version: {e}")
            return "unknown"
    
    def _get_record_counts(self) -> Dict[str, int]:
        """테이블별 레코드 수 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            counts = {}
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            
            conn.close()
            return counts
        except Exception as e:
            logger.warning(f"Failed to get record counts: {e}")
            return {}
    
    def _verify_backup(self, backup_file: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """백업 파일 검증"""
        try:
            # 파일 존재 여부
            if not backup_file.exists():
                return {"valid": False, "reason": "Backup file does not exist"}
            
            # 파일 크기 검증
            actual_size = backup_file.stat().st_size
            expected_size = metadata.get("compressed_size", 0)
            if actual_size != expected_size:
                return {"valid": False, "reason": f"Size mismatch: {actual_size} != {expected_size}"}
            
            # 해시 검증
            actual_hash = self._calculate_file_hash(backup_file)
            expected_hash = metadata.get("backup_hash", "")
            if actual_hash != expected_hash:
                return {"valid": False, "reason": f"Hash mismatch: {actual_hash} != {expected_hash}"}
            
            # 압축 파일 무결성 검증
            try:
                with gzip.open(backup_file, 'rb') as f:
                    # 파일의 일부를 읽어 압축이 제대로 되었는지 확인
                    f.read(1024)
            except Exception as e:
                return {"valid": False, "reason": f"Compression integrity failed: {e}"}
            
            return {"valid": True, "verified_at": datetime.now().isoformat()}
            
        except Exception as e:
            return {"valid": False, "reason": f"Verification error: {e}"}
    
    def _verify_restored_database(self, db_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """복구된 데이터베이스 검증"""
        try:
            # 데이터베이스 연결 테스트
            conn = sqlite3.connect(db_path)
            
            # 무결성 검사
            cursor = conn.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            if integrity_result != "ok":
                conn.close()
                return {"valid": False, "reason": f"Integrity check failed: {integrity_result}"}
            
            # 테이블 수 검증
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 레코드 수 검증 (가능한 경우)
            expected_counts = metadata.get("record_counts", {})
            for table in tables:
                if table in expected_counts:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    actual_count = cursor.fetchone()[0]
                    expected_count = expected_counts[table]
                    
                    # 약간의 차이는 허용 (백업 후 추가 데이터가 있을 수 있음)
                    if actual_count < expected_count:
                        conn.close()
                        return {"valid": False, "reason": f"Record count mismatch in {table}: {actual_count} < {expected_count}"}
            
            conn.close()
            return {"valid": True, "verified_at": datetime.now().isoformat(), "tables": len(tables)}
            
        except Exception as e:
            return {"valid": False, "reason": f"Database verification error: {e}"}
    
    def _find_backup(self, backup_id: str) -> tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """백업 ID로 백업 파일 찾기"""
        try:
            # 정확한 백업 ID로 찾기
            for meta_file in self.backup_dir.glob("*.meta.json"):
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if metadata.get("backup_id") == backup_id:
                    backup_file = Path(metadata.get("backup_file", ""))
                    return backup_file, metadata
            
            # 패턴 매칭으로 찾기
            for meta_file in self.backup_dir.glob("*.meta.json"):
                if backup_id in meta_file.stem:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    backup_file = Path(metadata.get("backup_file", ""))
                    return backup_file, metadata
            
            return None, None
            
        except Exception as e:
            logger.error(f"Failed to find backup: {e}")
            return None, None
    
    def _apply_retention_policy(self, backup_type: str):
        """보존 정책 적용"""
        try:
            if backup_type not in self.retention_policy:
                return
            
            backups = self.list_backups(backup_type)
            max_count = self.retention_policy[backup_type]["count"]
            
            if len(backups) > max_count:
                # 오래된 백업 삭제
                for backup in backups[max_count:]:
                    backup_id = backup.get("backup_id")
                    if backup_id:
                        self.delete_backup(backup_id)
                        logger.info(f"Deleted old backup due to retention policy: {backup_id}")
            
        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}")


# 전역 백업 매니저 인스턴스
_backup_manager = None


def get_backup_manager() -> BackupManager:
    """싱글톤 백업 매니저 반환"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager