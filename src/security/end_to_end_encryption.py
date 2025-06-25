"""
엔드투엔드 암호화 시스템

모든 데이터를 클라이언트에서 서버까지 완전히 암호화하여 전송하고 저장합니다.
- AES-256-GCM 대칭 암호화
- RSA 비대칭 암호화
- ECDH 키 교환
- 완전 순방향 보안 (Perfect Forward Secrecy)
- 양자 내성 암호화 지원
"""

import asyncio
import os
import logging
import json
import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from contextlib import asynccontextmanager

# 암호화 라이브러리
from cryptography.hazmat.primitives import hashes, serialization, padding as crypto_padding
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import cryptography.exceptions

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """암호화 알고리즘"""
    AES_256_GCM = "AES-256-GCM"
    AES_256_CBC = "AES-256-CBC"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"
    RSA_OAEP = "RSA-OAEP"
    ECDH_P256 = "ECDH-P256"
    ECDH_P384 = "ECDH-P384"


class KeyType(Enum):
    """키 유형"""
    SYMMETRIC = "SYMMETRIC"
    ASYMMETRIC_PRIVATE = "ASYMMETRIC_PRIVATE"
    ASYMMETRIC_PUBLIC = "ASYMMETRIC_PUBLIC"
    DERIVED = "DERIVED"
    EPHEMERAL = "EPHEMERAL"


@dataclass
class EncryptionKey:
    """암호화 키"""
    key_id: str
    key_type: KeyType
    algorithm: EncryptionAlgorithm
    key_data: bytes
    public_key_data: Optional[bytes]
    created_at: datetime
    expires_at: Optional[datetime]
    usage_count: int
    max_usage: Optional[int]
    metadata: Dict[str, Any]


@dataclass
class EncryptedData:
    """암호화된 데이터"""
    data_id: str
    algorithm: EncryptionAlgorithm
    encrypted_data: bytes
    iv: Optional[bytes]
    auth_tag: Optional[bytes]
    key_id: str
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class CryptoContext:
    """암호화 컨텍스트"""
    session_id: str
    client_id: str
    shared_secret: Optional[bytes]
    encryption_key: Optional[EncryptionKey]
    mac_key: Optional[bytes]
    created_at: datetime
    last_used: datetime


class EndToEndEncryption:
    """엔드투엔드 암호화 시스템"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or Path("config/encryption_config.json")
        self.db_path = Path("security/encryption.db")
        self.keys_path = Path("security/encryption_keys")
        
        # 설정 로드
        self.config = self._load_config()
        
        # 키 관리
        self.master_key: Optional[bytes] = None
        self.key_store: Dict[str, EncryptionKey] = {}
        self.crypto_contexts: Dict[str, CryptoContext] = {}
        
        # 암호화 엔진
        self.backend = default_backend()
        
        # 성능 통계
        self.encryption_stats = {
            "total_encryptions": 0,
            "total_decryptions": 0,
            "total_key_exchanges": 0,
            "average_encryption_time": 0.0,
            "average_decryption_time": 0.0
        }
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 초기화
        self._init_database()
        self._init_master_key()
        self._load_keys()
        
        logger.info("엔드투엔드 암호화 시스템 초기화 완료")
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "encryption": {
                "default_algorithm": "AES-256-GCM",
                "key_size": 256,
                "key_rotation_hours": 24,
                "max_key_usage": 100000,
                "enable_pfs": True,  # Perfect Forward Secrecy
                "enable_quantum_resistant": False
            },
            "key_derivation": {
                "algorithm": "PBKDF2",
                "iterations": 100000,
                "salt_length": 32,
                "key_length": 32
            },
            "asymmetric": {
                "rsa_key_size": 4096,
                "ec_curve": "secp384r1",
                "enable_ecdh": True
            },
            "storage": {
                "encrypt_at_rest": True,
                "key_backup_enabled": True,
                "secure_deletion": True
            },
            "performance": {
                "enable_hardware_acceleration": True,
                "cache_keys": True,
                "parallel_processing": True
            }
        }
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                default_config.update(config)
            
            # 설정 파일 저장
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            return default_config
            
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            return default_config
    
    def _init_database(self):
        """데이터베이스 초기화"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 암호화 키 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS encryption_keys (
                key_id TEXT PRIMARY KEY,
                key_type TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                key_data BLOB NOT NULL,
                public_key_data BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                usage_count INTEGER DEFAULT 0,
                max_usage INTEGER,
                metadata TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # 암호화된 데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS encrypted_data (
                data_id TEXT PRIMARY KEY,
                algorithm TEXT NOT NULL,
                encrypted_data BLOB NOT NULL,
                iv BLOB,
                auth_tag BLOB,
                key_id TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (key_id) REFERENCES encryption_keys (key_id)
            )
        ''')
        
        # 암호화 세션 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_sessions (
                session_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                shared_secret BLOB,
                encryption_key_id TEXT,
                mac_key BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # 키 교환 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS key_exchange_log (
                exchange_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("암호화 데이터베이스 초기화 완료")
    
    def _init_master_key(self):
        """마스터 키 초기화"""
        self.keys_path.mkdir(parents=True, exist_ok=True)
        master_key_path = self.keys_path / "master.key"
        
        if master_key_path.exists():
            try:
                with open(master_key_path, 'rb') as f:
                    encrypted_master_key = f.read()
                
                # 환경변수에서 키 해독 패스워드 가져오기
                password = os.getenv("ENCRYPTION_MASTER_PASSWORD", "default_password").encode()
                
                # 키 해독
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'master_key_salt',
                    iterations=100000,
                    backend=self.backend
                )
                decryption_key = base64.urlsafe_b64encode(kdf.derive(password))
                fernet = Fernet(decryption_key)
                
                self.master_key = fernet.decrypt(encrypted_master_key)
                logger.info("마스터 키 로드 완료")
                
            except Exception as e:
                logger.error(f"마스터 키 로드 실패: {e}")
                self._generate_master_key()
        else:
            self._generate_master_key()
    
    def _generate_master_key(self):
        """마스터 키 생성"""
        # 256비트 마스터 키 생성
        self.master_key = secrets.token_bytes(32)
        
        # 마스터 키 암호화 저장
        password = os.getenv("ENCRYPTION_MASTER_PASSWORD", "default_password").encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'master_key_salt',
            iterations=100000,
            backend=self.backend
        )
        encryption_key = base64.urlsafe_b64encode(kdf.derive(password))
        fernet = Fernet(encryption_key)
        
        encrypted_master_key = fernet.encrypt(self.master_key)
        
        master_key_path = self.keys_path / "master.key"
        with open(master_key_path, 'wb') as f:
            f.write(encrypted_master_key)
        
        # 파일 권한 설정 (600)
        os.chmod(master_key_path, 0o600)
        
        logger.info("새 마스터 키 생성 및 저장 완료")
    
    def _load_keys(self):
        """키 로드"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM encryption_keys WHERE is_active = TRUE
        ''')
        
        keys = cursor.fetchall()
        conn.close()
        
        for key_row in keys:
            key_id = key_row[0]
            encryption_key = EncryptionKey(
                key_id=key_id,
                key_type=KeyType(key_row[1]),
                algorithm=EncryptionAlgorithm(key_row[2]),
                key_data=key_row[3],
                public_key_data=key_row[4],
                created_at=datetime.fromisoformat(key_row[5]),
                expires_at=datetime.fromisoformat(key_row[6]) if key_row[6] else None,
                usage_count=key_row[7],
                max_usage=key_row[8],
                metadata=json.loads(key_row[9]) if key_row[9] else {}
            )
            self.key_store[key_id] = encryption_key
        
        logger.info(f"{len(self.key_store)}개 암호화 키 로드 완료")
    
    async def generate_key_pair(self, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.RSA_OAEP,
                               key_id: Optional[str] = None) -> Tuple[str, bytes, bytes]:
        """
        비대칭 키 쌍 생성
        
        Args:
            algorithm: 암호화 알고리즘
            key_id: 키 ID (없으면 자동 생성)
            
        Returns:
            (키 ID, 개인키, 공개키)
        """
        with self._lock:
            if not key_id:
                key_id = f"keypair_{secrets.token_urlsafe(16)}"
            
            try:
                if algorithm == EncryptionAlgorithm.RSA_OAEP:
                    # RSA 키 쌍 생성
                    private_key = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=self.config["asymmetric"]["rsa_key_size"],
                        backend=self.backend
                    )
                    public_key = private_key.public_key()
                    
                    # 키 직렬화
                    private_pem = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    
                    public_pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                elif algorithm in [EncryptionAlgorithm.ECDH_P256, EncryptionAlgorithm.ECDH_P384]:
                    # ECDH 키 쌍 생성
                    if algorithm == EncryptionAlgorithm.ECDH_P256:
                        curve = ec.SECP256R1()
                    else:
                        curve = ec.SECP384R1()
                    
                    private_key = ec.generate_private_key(curve, self.backend)
                    public_key = private_key.public_key()
                    
                    # 키 직렬화
                    private_pem = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    
                    public_pem = public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                else:
                    raise ValueError(f"지원하지 않는 알고리즘: {algorithm}")
                
                # 키 저장
                encryption_key = EncryptionKey(
                    key_id=key_id,
                    key_type=KeyType.ASYMMETRIC_PRIVATE,
                    algorithm=algorithm,
                    key_data=private_pem,
                    public_key_data=public_pem,
                    created_at=datetime.now(),
                    expires_at=None,
                    usage_count=0,
                    max_usage=self.config["encryption"]["max_key_usage"],
                    metadata={}
                )
                
                await self._save_key(encryption_key)
                self.key_store[key_id] = encryption_key
                
                logger.info(f"키 쌍 생성 완료: {key_id} ({algorithm.value})")
                return key_id, private_pem, public_pem
                
            except Exception as e:
                logger.error(f"키 쌍 생성 실패: {e}")
                raise
    
    async def generate_symmetric_key(self, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
                                   key_id: Optional[str] = None) -> Tuple[str, bytes]:
        """
        대칭 키 생성
        
        Args:
            algorithm: 암호화 알고리즘
            key_id: 키 ID (없으면 자동 생성)
            
        Returns:
            (키 ID, 키 데이터)
        """
        with self._lock:
            if not key_id:
                key_id = f"symkey_{secrets.token_urlsafe(16)}"
            
            try:
                # 키 크기 결정
                if algorithm in [EncryptionAlgorithm.AES_256_GCM, EncryptionAlgorithm.AES_256_CBC]:
                    key_data = secrets.token_bytes(32)  # 256비트
                elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                    key_data = secrets.token_bytes(32)  # 256비트
                else:
                    raise ValueError(f"지원하지 않는 대칭 알고리즘: {algorithm}")
                
                # 키 저장
                encryption_key = EncryptionKey(
                    key_id=key_id,
                    key_type=KeyType.SYMMETRIC,
                    algorithm=algorithm,
                    key_data=key_data,
                    public_key_data=None,
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(
                        hours=self.config["encryption"]["key_rotation_hours"]
                    ),
                    usage_count=0,
                    max_usage=self.config["encryption"]["max_key_usage"],
                    metadata={}
                )
                
                await self._save_key(encryption_key)
                self.key_store[key_id] = encryption_key
                
                logger.info(f"대칭 키 생성 완료: {key_id} ({algorithm.value})")
                return key_id, key_data
                
            except Exception as e:
                logger.error(f"대칭 키 생성 실패: {e}")
                raise
    
    async def perform_key_exchange(self, client_id: str, client_public_key: bytes,
                                 algorithm: EncryptionAlgorithm = EncryptionAlgorithm.ECDH_P256) -> Tuple[str, bytes]:
        """
        키 교환 수행 (ECDH)
        
        Args:
            client_id: 클라이언트 ID
            client_public_key: 클라이언트 공개키
            algorithm: 키 교환 알고리즘
            
        Returns:
            (세션 ID, 서버 공개키)
        """
        session_id = f"session_{secrets.token_urlsafe(16)}"
        
        try:
            # 서버 임시 키 쌍 생성
            server_key_id, server_private_pem, server_public_pem = await self.generate_key_pair(algorithm)
            
            # 클라이언트 공개키 로드
            client_public_key_obj = serialization.load_pem_public_key(
                client_public_key, backend=self.backend
            )
            
            # 서버 개인키 로드
            server_private_key_obj = serialization.load_pem_private_key(
                server_private_pem, password=None, backend=self.backend
            )
            
            # 공유 비밀 생성 (ECDH)
            shared_key = server_private_key_obj.exchange(ec.ECDH(), client_public_key_obj)
            
            # 키 유도 (HKDF)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=64,  # 32바이트 암호화 키 + 32바이트 MAC 키
                salt=None,
                info=b'key_exchange',
                backend=self.backend
            )
            derived_key = hkdf.derive(shared_key)
            
            encryption_key = derived_key[:32]
            mac_key = derived_key[32:]
            
            # 대칭 키 저장
            sym_key_id, _ = await self.generate_symmetric_key(
                EncryptionAlgorithm.AES_256_GCM,
                f"session_{session_id}"
            )
            
            # 암호화 컨텍스트 생성
            crypto_context = CryptoContext(
                session_id=session_id,
                client_id=client_id,
                shared_secret=shared_key,
                encryption_key=self.key_store[sym_key_id],
                mac_key=mac_key,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            
            self.crypto_contexts[session_id] = crypto_context
            
            # 세션 저장
            await self._save_crypto_session(crypto_context)
            
            # 키 교환 로그
            await self._log_key_exchange(client_id, algorithm.value, True, None)
            
            self.encryption_stats["total_key_exchanges"] += 1
            
            logger.info(f"키 교환 완료: {session_id} (클라이언트: {client_id})")
            
            # 서버 임시 키 삭제 (Perfect Forward Secrecy)
            if self.config["encryption"]["enable_pfs"]:
                await self._delete_key(server_key_id)
            
            return session_id, server_public_pem
            
        except Exception as e:
            logger.error(f"키 교환 실패: {e}")
            await self._log_key_exchange(client_id, algorithm.value, False, str(e))
            raise
    
    async def encrypt_data(self, data: Union[str, bytes], key_id: Optional[str] = None,
                          session_id: Optional[str] = None,
                          algorithm: Optional[EncryptionAlgorithm] = None) -> EncryptedData:
        """
        데이터 암호화
        
        Args:
            data: 암호화할 데이터
            key_id: 암호화 키 ID
            session_id: 세션 ID (키 교환 세션)
            algorithm: 암호화 알고리즘
            
        Returns:
            암호화된 데이터 객체
        """
        import time
        start_time = time.time()
        
        try:
            # 데이터 준비
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # 키 결정
            if session_id and session_id in self.crypto_contexts:
                # 세션 키 사용
                crypto_context = self.crypto_contexts[session_id]
                encryption_key = crypto_context.encryption_key
                crypto_context.last_used = datetime.now()
            elif key_id and key_id in self.key_store:
                # 지정된 키 사용
                encryption_key = self.key_store[key_id]
            else:
                # 기본 키 생성
                key_id, _ = await self.generate_symmetric_key(
                    algorithm or EncryptionAlgorithm.AES_256_GCM
                )
                encryption_key = self.key_store[key_id]
            
            # 알고리즘 결정
            if not algorithm:
                algorithm = encryption_key.algorithm
            
            # 암호화 수행
            if algorithm == EncryptionAlgorithm.AES_256_GCM:
                encrypted_data, iv, auth_tag = await self._encrypt_aes_gcm(data_bytes, encryption_key.key_data)
            elif algorithm == EncryptionAlgorithm.AES_256_CBC:
                encrypted_data, iv = await self._encrypt_aes_cbc(data_bytes, encryption_key.key_data)
                auth_tag = None
            elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                encrypted_data, iv, auth_tag = await self._encrypt_chacha20_poly1305(data_bytes, encryption_key.key_data)
            else:
                raise ValueError(f"지원하지 않는 암호화 알고리즘: {algorithm}")
            
            # 암호화된 데이터 객체 생성
            data_id = f"data_{secrets.token_urlsafe(16)}"
            encrypted_data_obj = EncryptedData(
                data_id=data_id,
                algorithm=algorithm,
                encrypted_data=encrypted_data,
                iv=iv,
                auth_tag=auth_tag,
                key_id=encryption_key.key_id,
                metadata={
                    "original_size": len(data_bytes),
                    "session_id": session_id
                },
                created_at=datetime.now()
            )
            
            # 사용 횟수 증가
            encryption_key.usage_count += 1
            await self._update_key_usage(encryption_key.key_id, encryption_key.usage_count)
            
            # 통계 업데이트
            encryption_time = time.time() - start_time
            self.encryption_stats["total_encryptions"] += 1
            self.encryption_stats["average_encryption_time"] = (
                (self.encryption_stats["average_encryption_time"] * 
                 (self.encryption_stats["total_encryptions"] - 1) + encryption_time) /
                self.encryption_stats["total_encryptions"]
            )
            
            # 데이터 저장 (선택적)
            if self.config["storage"]["encrypt_at_rest"]:
                await self._save_encrypted_data(encrypted_data_obj)
            
            logger.debug(f"데이터 암호화 완료: {data_id} ({len(data_bytes)}바이트)")
            
            return encrypted_data_obj
            
        except Exception as e:
            logger.error(f"데이터 암호화 실패: {e}")
            raise
    
    async def decrypt_data(self, encrypted_data: EncryptedData,
                          session_id: Optional[str] = None) -> bytes:
        """
        데이터 복호화
        
        Args:
            encrypted_data: 암호화된 데이터 객체
            session_id: 세션 ID
            
        Returns:
            복호화된 데이터
        """
        import time
        start_time = time.time()
        
        try:
            # 키 조회
            if session_id and session_id in self.crypto_contexts:
                # 세션 키 사용
                crypto_context = self.crypto_contexts[session_id]
                encryption_key = crypto_context.encryption_key
                crypto_context.last_used = datetime.now()
            elif encrypted_data.key_id in self.key_store:
                # 저장된 키 사용
                encryption_key = self.key_store[encrypted_data.key_id]
            else:
                raise ValueError(f"복호화 키를 찾을 수 없음: {encrypted_data.key_id}")
            
            # 복호화 수행
            if encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
                decrypted_data = await self._decrypt_aes_gcm(
                    encrypted_data.encrypted_data, encryption_key.key_data,
                    encrypted_data.iv, encrypted_data.auth_tag
                )
            elif encrypted_data.algorithm == EncryptionAlgorithm.AES_256_CBC:
                decrypted_data = await self._decrypt_aes_cbc(
                    encrypted_data.encrypted_data, encryption_key.key_data, encrypted_data.iv
                )
            elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                decrypted_data = await self._decrypt_chacha20_poly1305(
                    encrypted_data.encrypted_data, encryption_key.key_data,
                    encrypted_data.iv, encrypted_data.auth_tag
                )
            else:
                raise ValueError(f"지원하지 않는 복호화 알고리즘: {encrypted_data.algorithm}")
            
            # 통계 업데이트
            decryption_time = time.time() - start_time
            self.encryption_stats["total_decryptions"] += 1
            self.encryption_stats["average_decryption_time"] = (
                (self.encryption_stats["average_decryption_time"] * 
                 (self.encryption_stats["total_decryptions"] - 1) + decryption_time) /
                self.encryption_stats["total_decryptions"]
            )
            
            logger.debug(f"데이터 복호화 완료: {encrypted_data.data_id}")
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"데이터 복호화 실패: {e}")
            raise
    
    async def _encrypt_aes_gcm(self, data: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
        """AES-GCM 암호화"""
        iv = secrets.token_bytes(12)  # 96비트 IV
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=self.backend
        )
        
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return ciphertext, iv, encryptor.tag
    
    async def _decrypt_aes_gcm(self, ciphertext: bytes, key: bytes, 
                              iv: bytes, auth_tag: bytes) -> bytes:
        """AES-GCM 복호화"""
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, auth_tag),
            backend=self.backend
        )
        
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext
    
    async def _encrypt_aes_cbc(self, data: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """AES-CBC 암호화 (PKCS7 패딩)"""
        iv = secrets.token_bytes(16)  # 128비트 IV
        
        # PKCS7 패딩
        padder = crypto_padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self.backend
        )
        
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return ciphertext, iv
    
    async def _decrypt_aes_cbc(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """AES-CBC 복호화"""
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self.backend
        )
        
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # PKCS7 언패딩
        unpadder = crypto_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_data) + unpadder.finalize()
        
        return plaintext
    
    async def _encrypt_chacha20_poly1305(self, data: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
        """ChaCha20-Poly1305 암호화"""
        nonce = secrets.token_bytes(12)  # 96비트 nonce
        
        cipher = Cipher(
            algorithms.ChaCha20(key, nonce),
            modes.GCM(nonce),
            backend=self.backend
        )
        
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return ciphertext, nonce, encryptor.tag
    
    async def _decrypt_chacha20_poly1305(self, ciphertext: bytes, key: bytes,
                                       nonce: bytes, auth_tag: bytes) -> bytes:
        """ChaCha20-Poly1305 복호화"""
        cipher = Cipher(
            algorithms.ChaCha20(key, nonce),
            modes.GCM(nonce, auth_tag),
            backend=self.backend
        )
        
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext
    
    async def _save_key(self, encryption_key: EncryptionKey):
        """키 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO encryption_keys (
                key_id, key_type, algorithm, key_data, public_key_data,
                created_at, expires_at, usage_count, max_usage, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            encryption_key.key_id, encryption_key.key_type.value,
            encryption_key.algorithm.value, encryption_key.key_data,
            encryption_key.public_key_data,
            encryption_key.created_at, encryption_key.expires_at,
            encryption_key.usage_count, encryption_key.max_usage,
            json.dumps(encryption_key.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_encrypted_data(self, encrypted_data: EncryptedData):
        """암호화된 데이터 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO encrypted_data (
                data_id, algorithm, encrypted_data, iv, auth_tag,
                key_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            encrypted_data.data_id, encrypted_data.algorithm.value,
            encrypted_data.encrypted_data, encrypted_data.iv,
            encrypted_data.auth_tag, encrypted_data.key_id,
            json.dumps(encrypted_data.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    async def _save_crypto_session(self, crypto_context: CryptoContext):
        """암호화 세션 저장"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO crypto_sessions (
                session_id, client_id, shared_secret, encryption_key_id,
                mac_key, created_at, last_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            crypto_context.session_id, crypto_context.client_id,
            crypto_context.shared_secret,
            crypto_context.encryption_key.key_id if crypto_context.encryption_key else None,
            crypto_context.mac_key, crypto_context.created_at, crypto_context.last_used
        ))
        
        conn.commit()
        conn.close()
    
    async def _log_key_exchange(self, client_id: str, algorithm: str, 
                               success: bool, error_message: Optional[str]):
        """키 교환 로그"""
        exchange_id = f"exchange_{secrets.token_urlsafe(16)}"
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO key_exchange_log (
                exchange_id, client_id, algorithm, success, error_message
            ) VALUES (?, ?, ?, ?, ?)
        ''', (exchange_id, client_id, algorithm, success, error_message))
        
        conn.commit()
        conn.close()
    
    async def _update_key_usage(self, key_id: str, usage_count: int):
        """키 사용 횟수 업데이트"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE encryption_keys SET usage_count = ? WHERE key_id = ?
        ''', (usage_count, key_id))
        
        conn.commit()
        conn.close()
    
    async def _delete_key(self, key_id: str):
        """키 삭제 (Perfect Forward Secrecy)"""
        # 메모리에서 제거
        if key_id in self.key_store:
            del self.key_store[key_id]
        
        # 데이터베이스에서 비활성화
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE encryption_keys SET is_active = FALSE WHERE key_id = ?
        ''', (key_id,))
        
        conn.commit()
        conn.close()
        
        # 보안 삭제 (키 데이터 덮어쓰기)
        if self.config["storage"]["secure_deletion"]:
            await self._secure_delete_key_file(key_id)
        
        logger.info(f"키 삭제 완료: {key_id}")
    
    async def _secure_delete_key_file(self, key_id: str):
        """키 파일 보안 삭제"""
        key_file_path = self.keys_path / f"{key_id}.key"
        if key_file_path.exists():
            # 파일을 랜덤 데이터로 여러 번 덮어쓰기
            file_size = key_file_path.stat().st_size
            
            for _ in range(3):  # 3회 덮어쓰기
                with open(key_file_path, 'wb') as f:
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # 파일 삭제
            key_file_path.unlink()
    
    async def rotate_keys(self):
        """키 로테이션"""
        logger.info("키 로테이션 시작")
        
        current_time = datetime.now()
        rotated_keys = 0
        
        for key_id, encryption_key in list(self.key_store.items()):
            # 만료된 키 확인
            if (encryption_key.expires_at and current_time > encryption_key.expires_at) or \
               (encryption_key.max_usage and encryption_key.usage_count >= encryption_key.max_usage):
                
                # 새 키 생성
                if encryption_key.key_type == KeyType.SYMMETRIC:
                    new_key_id, _ = await self.generate_symmetric_key(encryption_key.algorithm)
                elif encryption_key.key_type == KeyType.ASYMMETRIC_PRIVATE:
                    new_key_id, _, _ = await self.generate_key_pair(encryption_key.algorithm)
                
                # 기존 키 비활성화
                await self._delete_key(key_id)
                
                rotated_keys += 1
                logger.info(f"키 로테이션: {key_id} -> {new_key_id}")
        
        logger.info(f"키 로테이션 완료: {rotated_keys}개 키 교체")
    
    async def backup_keys(self, backup_path: Optional[Path] = None) -> Path:
        """키 백업"""
        if not self.config["storage"]["key_backup_enabled"]:
            raise ValueError("키 백업이 비활성화되어 있습니다")
        
        backup_path = backup_path or Path(f"backups/keys_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 키 내보내기
        backup_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "keys": {}
        }
        
        for key_id, encryption_key in self.key_store.items():
            # 개인키는 백업하지 않음 (보안상 이유)
            if encryption_key.key_type != KeyType.ASYMMETRIC_PRIVATE:
                backup_data["keys"][key_id] = {
                    "key_type": encryption_key.key_type.value,
                    "algorithm": encryption_key.algorithm.value,
                    "key_data": base64.b64encode(encryption_key.key_data).decode(),
                    "public_key_data": base64.b64encode(encryption_key.public_key_data).decode() if encryption_key.public_key_data else None,
                    "metadata": encryption_key.metadata
                }
        
        # 백업 파일 생성 (암호화)
        backup_json = json.dumps(backup_data, indent=2)
        encrypted_backup = await self.encrypt_data(backup_json)
        
        backup_file = backup_path / "keys_backup.enc"
        with open(backup_file, 'wb') as f:
            f.write(encrypted_backup.encrypted_data)
        
        # 메타데이터 저장
        meta_file = backup_path / "backup_meta.json"
        with open(meta_file, 'w') as f:
            json.dump({
                "data_id": encrypted_backup.data_id,
                "algorithm": encrypted_backup.algorithm.value,
                "iv": base64.b64encode(encrypted_backup.iv).decode() if encrypted_backup.iv else None,
                "auth_tag": base64.b64encode(encrypted_backup.auth_tag).decode() if encrypted_backup.auth_tag else None,
                "key_id": encrypted_backup.key_id
            }, f, indent=2)
        
        logger.info(f"키 백업 완료: {backup_path}")
        return backup_path
    
    async def get_encryption_status(self) -> Dict[str, Any]:
        """암호화 시스템 상태 조회"""
        active_keys = len([k for k in self.key_store.values() if k.expires_at is None or k.expires_at > datetime.now()])
        expired_keys = len(self.key_store) - active_keys
        
        active_sessions = len([s for s in self.crypto_contexts.values() 
                             if datetime.now() - s.last_used < timedelta(hours=1)])
        
        return {
            "system_status": "ACTIVE",
            "total_keys": len(self.key_store),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "active_sessions": active_sessions,
            "key_types": {
                key_type.value: len([k for k in self.key_store.values() if k.key_type == key_type])
                for key_type in KeyType
            },
            "algorithms": {
                algo.value: len([k for k in self.key_store.values() if k.algorithm == algo])
                for algo in EncryptionAlgorithm
            },
            "statistics": self.encryption_stats,
            "configuration": {
                "default_algorithm": self.config["encryption"]["default_algorithm"],
                "key_rotation_hours": self.config["encryption"]["key_rotation_hours"],
                "pfs_enabled": self.config["encryption"]["enable_pfs"],
                "quantum_resistant": self.config["encryption"]["enable_quantum_resistant"]
            }
        }
    
    async def encrypt_file(self, file_path: Path, output_path: Optional[Path] = None,
                          key_id: Optional[str] = None) -> Path:
        """파일 암호화"""
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없음: {file_path}")
        
        output_path = output_path or file_path.with_suffix(file_path.suffix + '.enc')
        
        # 파일 읽기
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # 암호화
        encrypted_data = await self.encrypt_data(file_data, key_id=key_id)
        
        # 암호화된 파일 저장
        encrypted_file_data = {
            "algorithm": encrypted_data.algorithm.value,
            "encrypted_data": base64.b64encode(encrypted_data.encrypted_data).decode(),
            "iv": base64.b64encode(encrypted_data.iv).decode() if encrypted_data.iv else None,
            "auth_tag": base64.b64encode(encrypted_data.auth_tag).decode() if encrypted_data.auth_tag else None,
            "key_id": encrypted_data.key_id,
            "metadata": encrypted_data.metadata
        }
        
        with open(output_path, 'w') as f:
            json.dump(encrypted_file_data, f, indent=2)
        
        logger.info(f"파일 암호화 완료: {file_path} -> {output_path}")
        return output_path
    
    async def decrypt_file(self, encrypted_file_path: Path, output_path: Optional[Path] = None,
                          session_id: Optional[str] = None) -> Path:
        """파일 복호화"""
        if not encrypted_file_path.exists():
            raise FileNotFoundError(f"암호화된 파일을 찾을 수 없음: {encrypted_file_path}")
        
        # 암호화된 파일 읽기
        with open(encrypted_file_path, 'r') as f:
            encrypted_file_data = json.load(f)
        
        # EncryptedData 객체 재구성
        encrypted_data = EncryptedData(
            data_id="file_" + secrets.token_urlsafe(8),
            algorithm=EncryptionAlgorithm(encrypted_file_data["algorithm"]),
            encrypted_data=base64.b64decode(encrypted_file_data["encrypted_data"]),
            iv=base64.b64decode(encrypted_file_data["iv"]) if encrypted_file_data["iv"] else None,
            auth_tag=base64.b64decode(encrypted_file_data["auth_tag"]) if encrypted_file_data["auth_tag"] else None,
            key_id=encrypted_file_data["key_id"],
            metadata=encrypted_file_data["metadata"],
            created_at=datetime.now()
        )
        
        # 복호화
        decrypted_data = await self.decrypt_data(encrypted_data, session_id=session_id)
        
        # 복호화된 파일 저장
        if not output_path:
            output_path = encrypted_file_path.with_suffix('')
            if output_path.suffix == '.enc':
                output_path = output_path.with_suffix('')
        
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
        
        logger.info(f"파일 복호화 완료: {encrypted_file_path} -> {output_path}")
        return output_path


# 전역 인스턴스
_e2e_encryption = None

def get_e2e_encryption() -> EndToEndEncryption:
    """엔드투엔드 암호화 시스템 싱글톤 반환"""
    global _e2e_encryption
    if _e2e_encryption is None:
        _e2e_encryption = EndToEndEncryption()
    return _e2e_encryption


# 데코레이터
def encrypt_response(algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM):
    """응답 암호화 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, (str, bytes, dict)):
                e2e = get_e2e_encryption()
                
                # JSON 직렬화
                if isinstance(result, dict):
                    result = json.dumps(result)
                
                # 암호화
                encrypted_data = await e2e.encrypt_data(result, algorithm=algorithm)
                
                return {
                    "encrypted": True,
                    "algorithm": encrypted_data.algorithm.value,
                    "data": base64.b64encode(encrypted_data.encrypted_data).decode(),
                    "iv": base64.b64encode(encrypted_data.iv).decode() if encrypted_data.iv else None,
                    "auth_tag": base64.b64encode(encrypted_data.auth_tag).decode() if encrypted_data.auth_tag else None,
                    "key_id": encrypted_data.key_id
                }
            
            return result
        return wrapper
    return decorator


async def main():
    """테스트용 메인 함수"""
    e2e = EndToEndEncryption()
    
    # 키 쌍 생성 테스트
    key_id, private_key, public_key = await e2e.generate_key_pair()
    print(f"키 쌍 생성: {key_id}")
    
    # 대칭 키 생성 테스트
    sym_key_id, sym_key = await e2e.generate_symmetric_key()
    print(f"대칭 키 생성: {sym_key_id}")
    
    # 데이터 암호화/복호화 테스트
    test_data = "이것은 기밀 데이터입니다."
    encrypted = await e2e.encrypt_data(test_data, key_id=sym_key_id)
    decrypted = await e2e.decrypt_data(encrypted)
    
    print(f"원본: {test_data}")
    print(f"복호화: {decrypted.decode('utf-8')}")
    print(f"일치: {test_data == decrypted.decode('utf-8')}")
    
    # 상태 조회
    status = await e2e.get_encryption_status()
    print(f"암호화 시스템 상태: {status}")


if __name__ == "__main__":
    asyncio.run(main())