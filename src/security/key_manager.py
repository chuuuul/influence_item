"""
API 키 암호화 및 관리 시스템

API 키와 민감한 설정을 안전하게 저장하고 관리합니다.
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import time

logger = logging.getLogger(__name__)


class KeyManager:
    """API 키 암호화 및 관리 클래스"""
    
    def __init__(self, master_key: Optional[str] = None, storage_path: Optional[Path] = None):
        """
        Args:
            master_key: 마스터 키 (없으면 환경변수에서 로드)
            storage_path: 암호화된 키 저장 경로
        """
        # 로깅 상태 추적 (반복 메시지 방지) - 먼저 초기화
        self._logged_warnings = set()
        self._logged_errors = set()
        
        self.master_key = master_key or os.getenv("MASTER_KEY", "")
        self.storage_path = storage_path or Path("config/encrypted_keys.json")
        self.cipher_suite = self._initialize_cipher()
        self.key_cache = {}
        self.cache_ttl = 300  # 5분 캐시
        
        # 저장 디렉토리 생성
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug("API 키 관리 시스템 초기화 완료")
    
    def _initialize_cipher(self) -> Fernet:
        """암호화 도구 초기화"""
        if not self.master_key:
            # 마스터 키가 없으면 생성
            self.master_key = self._generate_master_key()
            # 마스터 키 경고는 한 번만 표시
            if "master_key_generated" not in self._logged_warnings:
                logger.warning("마스터 키가 생성되었습니다. 환경변수 MASTER_KEY를 설정하세요.")
                self._logged_warnings.add("master_key_generated")
        
        # 마스터 키에서 암호화 키 유도
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'influence_item_salt',  # 프로덕션에서는 랜덤 salt 사용
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def _generate_master_key(self) -> str:
        """마스터 키 생성"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def encrypt_key(self, key_name: str, key_value: str) -> bool:
        """
        API 키 암호화 저장
        
        Args:
            key_name: 키 이름
            key_value: 암호화할 키 값
            
        Returns:
            성공 여부
        """
        try:
            # 기존 데이터 로드
            encrypted_data = self._load_encrypted_data()
            
            # 키 암호화
            encrypted_key = self.cipher_suite.encrypt(key_value.encode()).decode()
            
            # 메타데이터와 함께 저장
            encrypted_data[key_name] = {
                "encrypted_value": encrypted_key,
                "created_at": int(time.time()),
                "last_accessed": None
            }
            
            # 파일에 저장
            with open(self.storage_path, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            logger.info(f"API 키 '{key_name}' 암호화 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"API 키 암호화 저장 실패: {str(e)}")
            return False
    
    def decrypt_key(self, key_name: str) -> Optional[str]:
        """
        API 키 복호화 조회
        
        Args:
            key_name: 키 이름
            
        Returns:
            복호화된 키 값 또는 None
        """
        try:
            # 캐시 확인
            if key_name in self.key_cache:
                cached_data = self.key_cache[key_name]
                if time.time() - cached_data["timestamp"] < self.cache_ttl:
                    logger.debug(f"API 키 '{key_name}' 캐시에서 로드")
                    return cached_data["value"]
            
            # 암호화된 데이터 로드
            encrypted_data = self._load_encrypted_data()
            
            if key_name not in encrypted_data:
                # 반복적인 키 부재 경고 방지
                warning_key = f"key_not_found_{key_name}"
                if warning_key not in self._logged_warnings:
                    logger.warning(f"API 키 '{key_name}'을 찾을 수 없습니다")
                    self._logged_warnings.add(warning_key)
                return None
            
            # 키 복호화
            encrypted_key = encrypted_data[key_name]["encrypted_value"]
            decrypted_key = self.cipher_suite.decrypt(encrypted_key.encode()).decode()
            
            # 캐시에 저장
            self.key_cache[key_name] = {
                "value": decrypted_key,
                "timestamp": time.time()
            }
            
            # 마지막 접근 시간 업데이트
            encrypted_data[key_name]["last_accessed"] = int(time.time())
            with open(self.storage_path, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            logger.debug(f"API 키 '{key_name}' 복호화 완료")
            return decrypted_key
            
        except Exception as e:
            # 반복적인 복호화 실패 에러 방지
            error_key = f"decrypt_failed_{key_name}"
            if error_key not in self._logged_errors:
                logger.error(f"API 키 복호화 실패: {str(e)}")
                self._logged_errors.add(error_key)
            return None
    
    def _load_encrypted_data(self) -> Dict[str, Any]:
        """암호화된 데이터 파일 로드"""
        if not self.storage_path.exists():
            return {}
        
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"암호화된 데이터 로드 실패: {str(e)}")
            return {}
    
    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """저장된 키 목록 조회 (메타데이터만)"""
        encrypted_data = self._load_encrypted_data()
        
        result = {}
        for key_name, data in encrypted_data.items():
            result[key_name] = {
                "created_at": data.get("created_at"),
                "last_accessed": data.get("last_accessed"),
                "has_value": bool(data.get("encrypted_value"))
            }
        
        return result
    
    def delete_key(self, key_name: str) -> bool:
        """API 키 삭제"""
        try:
            encrypted_data = self._load_encrypted_data()
            
            if key_name not in encrypted_data:
                logger.warning(f"삭제할 키 '{key_name}'을 찾을 수 없습니다")
                return False
            
            del encrypted_data[key_name]
            
            # 캐시에서도 제거
            if key_name in self.key_cache:
                del self.key_cache[key_name]
            
            # 파일 업데이트
            with open(self.storage_path, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            logger.info(f"API 키 '{key_name}' 삭제 완료")
            return True
            
        except Exception as e:
            logger.error(f"API 키 삭제 실패: {str(e)}")
            return False
    
    def rotate_key(self, key_name: str, new_key_value: str) -> bool:
        """API 키 로테이션"""
        try:
            # 기존 키 백업
            old_key = self.decrypt_key(key_name)
            if old_key:
                backup_name = f"{key_name}_backup_{int(time.time())}"
                self.encrypt_key(backup_name, old_key)
                logger.info(f"기존 키를 '{backup_name}'으로 백업했습니다")
            
            # 새 키 저장
            success = self.encrypt_key(key_name, new_key_value)
            if success:
                # 캐시 클리어 (로테이션 후 새 키가 바로 로드되도록)
                if key_name in self.key_cache:
                    del self.key_cache[key_name]
                logger.info(f"API 키 '{key_name}' 로테이션 완료")
            
            return success
            
        except Exception as e:
            logger.error(f"API 키 로테이션 실패: {str(e)}")
            return False
    
    def clear_cache(self) -> None:
        """키 캐시 클리어"""
        self.key_cache.clear()
        logger.debug("키 캐시 클리어 완료")
    
    def get_api_key_safe(self, key_name: str, fallback_env_var: Optional[str] = None) -> str:
        """
        안전한 API 키 조회 (암호화된 저장소 우선, 환경변수 폴백)
        
        Args:
            key_name: 키 이름
            fallback_env_var: 폴백 환경변수명
            
        Returns:
            API 키 값
        """
        # 1. 암호화된 저장소에서 시도
        encrypted_key = self.decrypt_key(key_name)
        if encrypted_key:
            return encrypted_key
        
        # 2. 환경변수에서 폴백
        if fallback_env_var:
            env_key = os.getenv(fallback_env_var)
            if env_key:
                logger.info(f"환경변수 '{fallback_env_var}'에서 키 로드")
                return env_key
        
        # 3. 기본 환경변수 시도
        env_key = os.getenv(key_name.upper())
        if env_key:
            logger.info(f"환경변수 '{key_name.upper()}'에서 키 로드")
            return env_key
        
        # 반복적인 키 부재 경고 방지
        warning_key = f"safe_key_not_found_{key_name}"
        if warning_key not in self._logged_warnings:
            logger.warning(f"API 키 '{key_name}'을 찾을 수 없습니다")
            self._logged_warnings.add(warning_key)
        return ""


# 전역 키 매니저 인스턴스
_key_manager = None

def get_key_manager() -> KeyManager:
    """키 매니저 싱글톤 인스턴스 반환"""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    
    # 로깅 상태 추적 변수가 없으면 추가 (하위 호환성)
    if not hasattr(_key_manager, '_logged_warnings'):
        _key_manager._logged_warnings = set()
    if not hasattr(_key_manager, '_logged_errors'):
        _key_manager._logged_errors = set()
    
    return _key_manager