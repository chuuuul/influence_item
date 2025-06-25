#!/usr/bin/env python3
"""
암호화 키 관리 시스템
"""

import os
import json
import base64
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime, timedelta

class KeyManager:
    """암호화 키 관리자"""
    
    def __init__(self, key_store_path: str = "keys"):
        self.key_store_path = Path(key_store_path)
        self.key_store_path.mkdir(exist_ok=True, mode=0o700)
        
        # 마스터 키 경로
        self.master_key_file = self.key_store_path / ".master_key"
        
        # 마스터 키 로드 또는 생성
        self.master_key = self._load_or_create_master_key()
    
    def _load_or_create_master_key(self) -> bytes:
        """마스터 키 로드 또는 생성"""
        if self.master_key_file.exists():
            with open(self.master_key_file, 'rb') as f:
                return f.read()
        else:
            # 새 마스터 키 생성
            master_key = Fernet.generate_key()
            
            # 파일에 저장 (제한된 권한)
            with open(self.master_key_file, 'wb') as f:
                f.write(master_key)
            
            os.chmod(self.master_key_file, 0o600)
            return master_key
    
    def create_key(self, key_name: str, key_type: str = "fernet") -> str:
        """새 키 생성"""
        if key_type == "fernet":
            key = Fernet.generate_key()
        elif key_type == "random":
            key = secrets.token_urlsafe(32).encode()
        else:
            raise ValueError(f"Unsupported key type: {key_type}")
        
        # 키 메타데이터
        metadata = {
            "name": key_name,
            "type": key_type,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
        }
        
        # 키 암호화
        fernet = Fernet(self.master_key)
        encrypted_key = fernet.encrypt(key)
        
        # 키 저장
        key_file = self.key_store_path / f"{key_name}.key"
        key_data = {
            "metadata": metadata,
            "encrypted_key": base64.b64encode(encrypted_key).decode()
        }
        
        with open(key_file, 'w') as f:
            json.dump(key_data, f, indent=2)
        
        os.chmod(key_file, 0o600)
        
        return base64.b64encode(key).decode()
    
    def get_key(self, key_name: str) -> bytes:
        """키 조회"""
        key_file = self.key_store_path / f"{key_name}.key"
        
        if not key_file.exists():
            raise FileNotFoundError(f"Key not found: {key_name}")
        
        with open(key_file, 'r') as f:
            key_data = json.load(f)
        
        # 만료 확인
        expires_at = datetime.fromisoformat(key_data["metadata"]["expires_at"])
        if datetime.now() > expires_at:
            raise ValueError(f"Key expired: {key_name}")
        
        # 키 복호화
        fernet = Fernet(self.master_key)
        encrypted_key = base64.b64decode(key_data["encrypted_key"])
        key = fernet.decrypt(encrypted_key)
        
        return key
    
    def rotate_key(self, key_name: str) -> str:
        """키 회전"""
        # 기존 키 백업
        old_key_file = self.key_store_path / f"{key_name}.key"
        if old_key_file.exists():
            backup_file = self.key_store_path / f"{key_name}.key.backup.{int(datetime.now().timestamp())}"
            old_key_file.rename(backup_file)
        
        # 새 키 생성
        return self.create_key(key_name)
    
    def list_keys(self) -> list:
        """키 목록 조회"""
        keys = []
        for key_file in self.key_store_path.glob("*.key"):
            if key_file.name.startswith("."):
                continue
                
            with open(key_file, 'r') as f:
                key_data = json.load(f)
            
            keys.append({
                "name": key_data["metadata"]["name"],
                "type": key_data["metadata"]["type"],
                "created_at": key_data["metadata"]["created_at"],
                "expires_at": key_data["metadata"]["expires_at"]
            })
        
        return keys

# 사용 예시
if __name__ == "__main__":
    km = KeyManager()
    
    # 필수 키들 생성
    keys_to_create = [
        ("database_encryption", "fernet"),
        ("session_secret", "random"),
        ("api_signing", "random")
    ]
    
    for key_name, key_type in keys_to_create:
        try:
            key = km.create_key(key_name, key_type)
            print(f"Created key '{key_name}': {key[:20]}...")
        except Exception as e:
            print(f"Error creating key '{key_name}': {e}")
    
    # 키 목록 출력
    print("\nCurrent keys:")
    for key_info in km.list_keys():
        print(f"  {key_info['name']} ({key_info['type']}) - Created: {key_info['created_at']}")
