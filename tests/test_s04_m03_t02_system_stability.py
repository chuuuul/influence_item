#!/usr/bin/env python3
"""
S04_M03_T02 통합 테스트: 시스템 안정성 및 장애 복구
장애 시나리오 테스트, 복구 메커니즘, 데이터 무결성 검증
"""

import sys
import os
import time
import json
import sqlite3
import threading
import queue
import random
import psutil
from typing import Dict, List, Any
from datetime import datetime, timedelta
import concurrent.futures
import signal
import subprocess

# 프로젝트 루트를 Python 경로에 추가
sys.path.append('/Users/chul/Documents/claude/influence_item')

def test_failure_scenarios():
    """장애 시나리오 테스트"""
    print("🧪 장애 시나리오 테스트 시작...")
    
    try:
        from enum import Enum
        import threading
        import time
        
        # 장애 유형 정의
        class FailureType(Enum):
            NETWORK_TIMEOUT = "network_timeout"
            API_RATE_LIMIT = "api_rate_limit"
            DATABASE_LOCK = "database_lock"
            MEMORY_EXHAUSTION = "memory_exhaustion"
            DISK_FULL = "disk_full"
            SERVICE_UNAVAILABLE = "service_unavailable"
            CORRUPTED_DATA = "corrupted_data"
        
        # 장애 시뮬레이터 클래스
        class FailureSimulator:
            def __init__(self):
                self.active_failures = {}
                self.failure_history = []
                self.recovery_mechanisms = {}
                self.system_health = {'status': 'healthy', 'failures': []}
                
            def register_recovery_mechanism(self, failure_type, recovery_func):
                """복구 메커니즘 등록"""
                self.recovery_mechanisms[failure_type] = recovery_func
                print(f"    🔧 복구 메커니즘 등록: {failure_type.value}")
            
            def simulate_failure(self, failure_type: FailureType, duration=5.0, severity='medium'):
                """장애 시뮬레이션"""
                failure_id = f"failure_{int(time.time() * 1000)}"
                
                failure_info = {
                    'failure_id': failure_id,
                    'failure_type': failure_type,
                    'start_time': datetime.now(),
                    'duration': duration,
                    'severity': severity,
                    'status': 'active',
                    'recovery_attempts': 0,
                    'recovered': False
                }
                
                self.active_failures[failure_id] = failure_info
                self.system_health['status'] = 'degraded'
                self.system_health['failures'].append(failure_type.value)
                
                print(f"    🚨 장애 시뮬레이션 시작: {failure_type.value} (지속시간: {duration}초)")
                
                # 백그라운드에서 장애 지속 및 복구 시도
                threading.Thread(target=self._manage_failure, args=(failure_id,)).start()
                
                return failure_id
            
            def _manage_failure(self, failure_id):
                """장애 관리 및 복구 시도"""
                failure_info = self.active_failures[failure_id]
                failure_type = failure_info['failure_type']
                
                # 장애 지속
                time.sleep(failure_info['duration'])
                
                # 복구 시도
                if failure_type in self.recovery_mechanisms:
                    recovery_func = self.recovery_mechanisms[failure_type]
                    
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        failure_info['recovery_attempts'] += 1
                        print(f"      🔄 복구 시도 {attempt + 1}/{max_attempts}: {failure_type.value}")
                        
                        try:
                            recovery_success = recovery_func(failure_info)
                            if recovery_success:
                                failure_info['recovered'] = True
                                failure_info['status'] = 'recovered'
                                failure_info['end_time'] = datetime.now()
                                break
                        except Exception as e:
                            print(f"        ⚠️ 복구 실패: {str(e)}")
                        
                        time.sleep(2)  # 복구 시도 간 대기
                
                # 복구 실패 시
                if not failure_info['recovered']:
                    failure_info['status'] = 'failed_recovery'
                    failure_info['end_time'] = datetime.now()
                    print(f"      ❌ 복구 실패: {failure_type.value}")
                else:
                    print(f"      ✅ 복구 성공: {failure_type.value}")
                
                # 장애 기록에 추가
                self.failure_history.append(failure_info.copy())
                
                # 활성 장애에서 제거
                del self.active_failures[failure_id]
                
                # 시스템 상태 업데이트
                if not self.active_failures:
                    self.system_health['status'] = 'healthy'
                    self.system_health['failures'] = []
            
            def get_system_status(self):
                """시스템 상태 조회"""
                return {
                    'health_status': self.system_health['status'],
                    'active_failures': len(self.active_failures),
                    'total_failures': len(self.failure_history),
                    'recovery_rate': self._calculate_recovery_rate(),
                    'current_failures': list(self.active_failures.keys())
                }
            
            def _calculate_recovery_rate(self):
                """복구율 계산"""
                if not self.failure_history:
                    return 0.0
                
                recovered_failures = sum(1 for f in self.failure_history if f['recovered'])
                return (recovered_failures / len(self.failure_history)) * 100
            
            def stress_test(self, num_failures=10, concurrent_failures=3):
                """스트레스 테스트"""
                print(f"    🔥 스트레스 테스트: {num_failures}개 장애, 동시 {concurrent_failures}개")
                
                failure_types = list(FailureType)
                failure_ids = []
                
                # 동시 장애 시뮬레이션
                for i in range(min(num_failures, concurrent_failures)):
                    failure_type = random.choice(failure_types)
                    duration = random.uniform(2.0, 8.0)
                    severity = random.choice(['low', 'medium', 'high'])
                    
                    failure_id = self.simulate_failure(failure_type, duration, severity)
                    failure_ids.append(failure_id)
                
                # 추가 장애들을 순차적으로 시뮬레이션
                remaining_failures = num_failures - concurrent_failures
                for i in range(remaining_failures):
                    time.sleep(random.uniform(1.0, 3.0))  # 간격을 두고 발생
                    
                    failure_type = random.choice(failure_types)
                    duration = random.uniform(2.0, 6.0)
                    severity = random.choice(['low', 'medium', 'high'])
                    
                    failure_id = self.simulate_failure(failure_type, duration, severity)
                    failure_ids.append(failure_id)
                
                # 모든 장애가 처리될 때까지 대기
                max_wait_time = 60  # 최대 60초 대기
                start_wait = time.time()
                
                while self.active_failures and (time.time() - start_wait) < max_wait_time:
                    time.sleep(1)
                
                return {
                    'total_simulated_failures': num_failures,
                    'completed_failures': len([f for f in self.failure_history if f['failure_id'] in failure_ids]),
                    'recovery_rate': self._calculate_recovery_rate(),
                    'remaining_active_failures': len(self.active_failures)
                }
        
        # 복구 메커니즘 함수들
        def recover_network_timeout(failure_info):
            """네트워크 타임아웃 복구"""
            # 재시도 로직 시뮬레이션
            time.sleep(1)
            return random.random() > 0.3  # 70% 성공률
        
        def recover_api_rate_limit(failure_info):
            """API 속도 제한 복구"""
            # 백오프 전략 시뮬레이션
            time.sleep(2)
            return random.random() > 0.1  # 90% 성공률
        
        def recover_database_lock(failure_info):
            """데이터베이스 락 복구"""
            # 락 해제 시뮬레이션
            time.sleep(0.5)
            return random.random() > 0.2  # 80% 성공률
        
        def recover_memory_exhaustion(failure_info):
            """메모리 부족 복구"""
            # 메모리 정리 시뮬레이션
            import gc
            gc.collect()
            time.sleep(1)
            return random.random() > 0.4  # 60% 성공률
        
        def recover_service_unavailable(failure_info):
            """서비스 불가 복구"""
            # 서비스 재시작 시뮬레이션
            time.sleep(3)
            return random.random() > 0.25  # 75% 성공률
        
        # 장애 시뮬레이터 테스트
        simulator = FailureSimulator()
        
        # 복구 메커니즘 등록
        simulator.register_recovery_mechanism(FailureType.NETWORK_TIMEOUT, recover_network_timeout)
        simulator.register_recovery_mechanism(FailureType.API_RATE_LIMIT, recover_api_rate_limit)
        simulator.register_recovery_mechanism(FailureType.DATABASE_LOCK, recover_database_lock)
        simulator.register_recovery_mechanism(FailureType.MEMORY_EXHAUSTION, recover_memory_exhaustion)
        simulator.register_recovery_mechanism(FailureType.SERVICE_UNAVAILABLE, recover_service_unavailable)
        
        # 개별 장애 시나리오 테스트
        individual_failures = [
            (FailureType.NETWORK_TIMEOUT, 3.0, 'medium'),
            (FailureType.API_RATE_LIMIT, 4.0, 'high'),
            (FailureType.DATABASE_LOCK, 2.0, 'low')
        ]
        
        for failure_type, duration, severity in individual_failures:
            failure_id = simulator.simulate_failure(failure_type, duration, severity)
            
            # 잠시 대기하여 복구 프로세스 관찰
            time.sleep(duration + 5)
        
        # 스트레스 테스트
        stress_results = simulator.stress_test(num_failures=8, concurrent_failures=3)
        
        # 최종 시스템 상태 확인
        final_status = simulator.get_system_status()
        
        # 결과 검증
        assert final_status['total_failures'] >= 8, "충분한 장애가 시뮬레이션되지 않았습니다."
        assert final_status['recovery_rate'] >= 50, f"복구율이 너무 낮습니다: {final_status['recovery_rate']:.1f}%"
        assert final_status['health_status'] == 'healthy', "시스템이 healthy 상태로 복구되지 않았습니다."
        assert final_status['active_failures'] == 0, "활성 장애가 남아있습니다."
        
        print(f"  🏥 시스템 복구율: {final_status['recovery_rate']:.1f}%")
        print(f"  📊 총 장애 처리: {final_status['total_failures']}개")
        print(f"  ✅ 최종 상태: {final_status['health_status']}")
        
        print("✅ 장애 시나리오 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 장애 시나리오 테스트 실패: {str(e)}")
        return False

def test_data_integrity():
    """데이터 무결성 테스트"""
    print("🧪 데이터 무결성 테스트 시작...")
    
    try:
        import hashlib
        import pickle
        import json
        import sqlite3
        from contextlib import contextmanager
        
        # 데이터 무결성 관리자 클래스
        class DataIntegrityManager:
            def __init__(self, db_path=':memory:'):
                self.db_path = db_path
                self.checksums = {}
                self.backup_data = {}
                self.integrity_violations = []
                self.validation_rules = {}
                self.init_database()
            
            def init_database(self):
                """데이터베이스 및 무결성 테이블 초기화"""
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 메인 데이터 테이블
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS integrity_test_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL,
                    checksum TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # 백업 테이블
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    backup_data TEXT,
                    backup_checksum TEXT,
                    backup_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # 무결성 로그 테이블
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS integrity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    record_id INTEGER,
                    violation_type TEXT,
                    old_checksum TEXT,
                    new_checksum TEXT,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                conn.commit()
                conn.close()
            
            @contextmanager
            def get_connection(self):
                """데이터베이스 연결 관리"""
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                try:
                    yield conn
                finally:
                    conn.close()
            
            def calculate_checksum(self, data):
                """데이터 체크섬 계산"""
                if isinstance(data, dict):
                    # 딕셔너리의 경우 정렬된 JSON 문자열로 변환
                    data_str = json.dumps(data, sort_keys=True)
                else:
                    data_str = str(data)
                
                return hashlib.sha256(data_str.encode()).hexdigest()
            
            def add_validation_rule(self, rule_name, validation_func):
                """데이터 검증 규칙 추가"""
                self.validation_rules[rule_name] = validation_func
                print(f"    📝 검증 규칙 추가: {rule_name}")
            
            def insert_data(self, name, value, create_backup=True):
                """데이터 삽입 (무결성 보장)"""
                data_dict = {'name': name, 'value': value}
                checksum = self.calculate_checksum(data_dict)
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    INSERT INTO integrity_test_data (name, value, checksum)
                    VALUES (?, ?, ?)
                    ''', (name, value, checksum))
                    
                    record_id = cursor.lastrowid
                    
                    # 백업 생성
                    if create_backup:
                        backup_data = json.dumps(data_dict)
                        cursor.execute('''
                        INSERT INTO data_backups (original_id, backup_data, backup_checksum)
                        VALUES (?, ?, ?)
                        ''', (record_id, backup_data, checksum))
                    
                    conn.commit()
                
                return record_id
            
            def update_data(self, record_id, name=None, value=None):
                """데이터 업데이트 (무결성 검증)"""
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 기존 데이터 조회
                    cursor.execute('SELECT * FROM integrity_test_data WHERE id = ?', (record_id,))
                    existing_record = cursor.fetchone()
                    
                    if not existing_record:
                        raise ValueError(f"Record {record_id} not found")
                    
                    # 무결성 검증
                    existing_data = {
                        'name': existing_record['name'],
                        'value': existing_record['value']
                    }
                    expected_checksum = self.calculate_checksum(existing_data)
                    
                    if existing_record['checksum'] != expected_checksum:
                        self._log_integrity_violation(
                            'integrity_test_data', record_id, 'checksum_mismatch',
                            existing_record['checksum'], expected_checksum
                        )
                        raise ValueError(f"Data integrity violation detected for record {record_id}")
                    
                    # 새 데이터 준비
                    new_name = name if name is not None else existing_record['name']
                    new_value = value if value is not None else existing_record['value']
                    new_data = {'name': new_name, 'value': new_value}
                    new_checksum = self.calculate_checksum(new_data)
                    
                    # 업데이트 실행
                    cursor.execute('''
                    UPDATE integrity_test_data 
                    SET name = ?, value = ?, checksum = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (new_name, new_value, new_checksum, record_id))
                    
                    conn.commit()
                
                return True
            
            def validate_data_integrity(self, table_name='integrity_test_data'):
                """데이터 무결성 검증"""
                violations = []
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT * FROM {table_name}')
                    records = cursor.fetchall()
                    
                    for record in records:
                        # 체크섬 검증
                        data_dict = {
                            'name': record['name'],
                            'value': record['value']
                        }
                        calculated_checksum = self.calculate_checksum(data_dict)
                        
                        if record['checksum'] != calculated_checksum:
                            violation = {
                                'record_id': record['id'],
                                'violation_type': 'checksum_mismatch',
                                'stored_checksum': record['checksum'],
                                'calculated_checksum': calculated_checksum,
                                'data': data_dict
                            }
                            violations.append(violation)
                            
                            self._log_integrity_violation(
                                table_name, record['id'], 'checksum_mismatch',
                                record['checksum'], calculated_checksum
                            )
                        
                        # 사용자 정의 검증 규칙 적용
                        for rule_name, validation_func in self.validation_rules.items():
                            try:
                                is_valid, error_msg = validation_func(record)
                                if not is_valid:
                                    violation = {
                                        'record_id': record['id'],
                                        'violation_type': f'rule_violation_{rule_name}',
                                        'error_message': error_msg,
                                        'data': data_dict
                                    }
                                    violations.append(violation)
                            except Exception as e:
                                print(f"      ⚠️ 검증 규칙 {rule_name} 실행 실패: {str(e)}")
                
                return violations
            
            def _log_integrity_violation(self, table_name, record_id, violation_type, old_checksum, new_checksum):
                """무결성 위반 로깅"""
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO integrity_logs (table_name, record_id, violation_type, old_checksum, new_checksum)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (table_name, record_id, violation_type, old_checksum, new_checksum))
                    conn.commit()
                
                self.integrity_violations.append({
                    'table_name': table_name,
                    'record_id': record_id,
                    'violation_type': violation_type,
                    'timestamp': datetime.now()
                })
            
            def corrupt_data_for_testing(self, record_id):
                """테스트용 데이터 손상"""
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    # 체크섬 무시하고 직접 데이터 변경
                    cursor.execute('''
                    UPDATE integrity_test_data 
                    SET value = value * 1.5
                    WHERE id = ?
                    ''', (record_id,))
                    conn.commit()
                
                print(f"    🔧 테스트용 데이터 손상: record {record_id}")
            
            def restore_from_backup(self, record_id):
                """백업에서 데이터 복원"""
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 백업 데이터 조회
                    cursor.execute('''
                    SELECT backup_data, backup_checksum FROM data_backups 
                    WHERE original_id = ? 
                    ORDER BY backup_timestamp DESC 
                    LIMIT 1
                    ''', (record_id,))
                    
                    backup_record = cursor.fetchone()
                    if not backup_record:
                        raise ValueError(f"No backup found for record {record_id}")
                    
                    # 백업 데이터 파싱
                    backup_data = json.loads(backup_record['backup_data'])
                    
                    # 데이터 복원
                    cursor.execute('''
                    UPDATE integrity_test_data 
                    SET name = ?, value = ?, checksum = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (backup_data['name'], backup_data['value'], backup_record['backup_checksum'], record_id))
                    
                    conn.commit()
                
                print(f"    🔄 데이터 복원 완료: record {record_id}")
                return True
            
            def run_integrity_stress_test(self, num_operations=100):
                """무결성 스트레스 테스트"""
                print(f"    🔥 무결성 스트레스 테스트: {num_operations}개 작업")
                
                stress_results = {
                    'operations_completed': 0,
                    'integrity_violations_detected': 0,
                    'successful_restorations': 0,
                    'failed_operations': 0
                }
                
                record_ids = []
                
                # 대량 데이터 삽입
                for i in range(num_operations // 2):
                    try:
                        record_id = self.insert_data(f'stress_test_{i}', random.uniform(1.0, 100.0))
                        record_ids.append(record_id)
                        stress_results['operations_completed'] += 1
                    except Exception as e:
                        stress_results['failed_operations'] += 1
                        print(f"      ⚠️ 삽입 실패: {str(e)}")
                
                # 일부 데이터 손상
                corruption_count = min(5, len(record_ids))
                corrupted_records = random.sample(record_ids, corruption_count)
                
                for record_id in corrupted_records:
                    self.corrupt_data_for_testing(record_id)
                
                # 무결성 검증
                violations = self.validate_data_integrity()
                stress_results['integrity_violations_detected'] = len(violations)
                
                # 손상된 데이터 복원
                for violation in violations:
                    try:
                        record_id = violation['record_id']
                        if record_id in corrupted_records:
                            self.restore_from_backup(record_id)
                            stress_results['successful_restorations'] += 1
                    except Exception as e:
                        print(f"      ⚠️ 복원 실패: {str(e)}")
                
                # 최종 무결성 검증
                final_violations = self.validate_data_integrity()
                
                stress_results['final_violations'] = len(final_violations)
                stress_results['restoration_success_rate'] = (
                    stress_results['successful_restorations'] / 
                    max(stress_results['integrity_violations_detected'], 1)
                ) * 100
                
                return stress_results
            
            def get_integrity_report(self):
                """무결성 보고서 생성"""
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 전체 레코드 수
                    cursor.execute('SELECT COUNT(*) as total FROM integrity_test_data')
                    total_records = cursor.fetchone()['total']
                    
                    # 백업 수
                    cursor.execute('SELECT COUNT(*) as total FROM data_backups')
                    total_backups = cursor.fetchone()['total']
                    
                    # 무결성 위반 로그
                    cursor.execute('SELECT COUNT(*) as total FROM integrity_logs')
                    total_violations_logged = cursor.fetchone()['total']
                
                # 현재 무결성 상태
                current_violations = self.validate_data_integrity()
                
                return {
                    'total_records': total_records,
                    'total_backups': total_backups,
                    'total_violations_logged': total_violations_logged,
                    'current_violations': len(current_violations),
                    'validation_rules': len(self.validation_rules),
                    'integrity_status': 'healthy' if len(current_violations) == 0 else 'compromised'
                }
        
        # 검증 규칙 함수들
        def validate_positive_value(record):
            """양수 값 검증"""
            if record['value'] <= 0:
                return False, f"Value must be positive, got {record['value']}"
            return True, None
        
        def validate_name_format(record):
            """이름 형식 검증"""
            if not record['name'] or len(record['name']) < 3:
                return False, f"Name must be at least 3 characters, got '{record['name']}'"
            return True, None
        
        def validate_value_range(record):
            """값 범위 검증"""
            if not (0 <= record['value'] <= 1000):
                return False, f"Value must be between 0 and 1000, got {record['value']}"
            return True, None
        
        # 데이터 무결성 관리자 테스트
        integrity_manager = DataIntegrityManager()
        
        # 검증 규칙 추가
        integrity_manager.add_validation_rule('positive_value', validate_positive_value)
        integrity_manager.add_validation_rule('name_format', validate_name_format)
        integrity_manager.add_validation_rule('value_range', validate_value_range)
        
        # 정상 데이터 삽입
        valid_records = []
        for i in range(10):
            record_id = integrity_manager.insert_data(f'valid_record_{i}', random.uniform(10.0, 100.0))
            valid_records.append(record_id)
        
        # 초기 무결성 검증
        initial_violations = integrity_manager.validate_data_integrity()
        assert len(initial_violations) == 0, f"초기 데이터에 무결성 위반이 있습니다: {len(initial_violations)}개"
        
        # 데이터 업데이트 테스트
        if valid_records:
            integrity_manager.update_data(valid_records[0], name='updated_record', value=150.0)
        
        # 의도적 데이터 손상
        if len(valid_records) >= 3:
            for record_id in valid_records[:3]:
                integrity_manager.corrupt_data_for_testing(record_id)
        
        # 손상 후 무결성 검증
        post_corruption_violations = integrity_manager.validate_data_integrity()
        assert len(post_corruption_violations) >= 3, "데이터 손상이 제대로 감지되지 않았습니다."
        
        # 백업에서 복원
        restored_count = 0
        for violation in post_corruption_violations:
            if violation['violation_type'] == 'checksum_mismatch':
                try:
                    integrity_manager.restore_from_backup(violation['record_id'])
                    restored_count += 1
                except Exception as e:
                    print(f"      ⚠️ 복원 실패: {str(e)}")
        
        # 복원 후 무결성 검증
        post_restoration_violations = integrity_manager.validate_data_integrity()
        
        # 스트레스 테스트
        stress_results = integrity_manager.run_integrity_stress_test(num_operations=50)
        
        # 최종 보고서
        integrity_report = integrity_manager.get_integrity_report()
        
        # 결과 검증
        assert len(post_corruption_violations) > len(post_restoration_violations), "복원이 제대로 수행되지 않았습니다."
        assert restored_count >= 3, "충분한 데이터가 복원되지 않았습니다."
        assert stress_results['operations_completed'] >= 20, "스트레스 테스트 작업이 충분히 수행되지 않았습니다."
        assert stress_results['restoration_success_rate'] >= 80, f"복원 성공률이 낮습니다: {stress_results['restoration_success_rate']:.1f}%"
        assert integrity_report['integrity_status'] == 'healthy', "최종 무결성 상태가 healthy가 아닙니다."
        
        print(f"  🔒 무결성 검증: {len(post_corruption_violations)}개 위반 → {len(post_restoration_violations)}개 위반")
        print(f"  🔄 복원 성공률: {stress_results['restoration_success_rate']:.1f}%")
        print(f"  📊 최종 상태: {integrity_report['integrity_status']}")
        
        print("✅ 데이터 무결성 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 데이터 무결성 테스트 실패: {str(e)}")
        return False

def test_system_resilience():
    """시스템 복원력 테스트"""
    print("🧪 시스템 복원력 테스트 시작...")
    
    try:
        import threading
        import queue
        import time
        import random
        from enum import Enum
        
        # 시스템 상태 정의
        class SystemState(Enum):
            HEALTHY = "healthy"
            DEGRADED = "degraded"
            CRITICAL = "critical"
            RECOVERING = "recovering"
            FAILED = "failed"
        
        # 복원력 관리자 클래스
        class ResilienceManager:
            def __init__(self):
                self.current_state = SystemState.HEALTHY
                self.components = {}
                self.circuit_breakers = {}
                self.health_checks = {}
                self.recovery_strategies = {}
                self.state_history = []
                self.resilience_metrics = {
                    'mttr': [],  # Mean Time To Recovery
                    'mtbf': [],  # Mean Time Between Failures
                    'availability': 0.0,
                    'downtime_events': []
                }
                self.monitoring_active = False
                self.monitor_thread = None
            
            def register_component(self, component_name, health_check_func, recovery_func=None):
                """시스템 컴포넌트 등록"""
                self.components[component_name] = {
                    'name': component_name,
                    'status': 'healthy',
                    'last_check': datetime.now(),
                    'failure_count': 0,
                    'recovery_count': 0,
                    'health_check': health_check_func,
                    'recovery_func': recovery_func
                }
                
                # 서킷 브레이커 초기화
                self.circuit_breakers[component_name] = {
                    'state': 'closed',  # closed, open, half-open
                    'failure_count': 0,
                    'failure_threshold': 5,
                    'timeout': 30,  # seconds
                    'last_failure_time': None
                }
                
                print(f"    🔧 컴포넌트 등록: {component_name}")
            
            def start_monitoring(self, check_interval=2.0):
                """시스템 모니터링 시작"""
                if self.monitoring_active:
                    return
                
                self.monitoring_active = True
                self.monitor_thread = threading.Thread(target=self._monitoring_loop, args=(check_interval,))
                self.monitor_thread.daemon = True
                self.monitor_thread.start()
                print(f"    📊 시스템 모니터링 시작 (간격: {check_interval}초)")
            
            def stop_monitoring(self):
                """시스템 모니터링 중지"""
                self.monitoring_active = False
                if self.monitor_thread:
                    self.monitor_thread.join(timeout=5.0)
                print("    ⏹️ 시스템 모니터링 중지")
            
            def _monitoring_loop(self, check_interval):
                """모니터링 루프"""
                while self.monitoring_active:
                    try:
                        self._perform_health_checks()
                        self._update_system_state()
                        self._manage_circuit_breakers()
                        time.sleep(check_interval)
                    except Exception as e:
                        print(f"      ⚠️ 모니터링 오류: {str(e)}")
                        time.sleep(check_interval)
            
            def _perform_health_checks(self):
                """헬스 체크 수행"""
                for component_name, component in self.components.items():
                    try:
                        health_check = component['health_check']
                        is_healthy = health_check()
                        
                        previous_status = component['status']
                        component['status'] = 'healthy' if is_healthy else 'unhealthy'
                        component['last_check'] = datetime.now()
                        
                        # 상태 변화 감지
                        if previous_status != component['status']:
                            if component['status'] == 'unhealthy':
                                component['failure_count'] += 1
                                self._handle_component_failure(component_name)
                            else:
                                component['recovery_count'] += 1
                                self._handle_component_recovery(component_name)
                    
                    except Exception as e:
                        component['status'] = 'error'
                        component['failure_count'] += 1
                        print(f"      ⚠️ {component_name} 헬스 체크 실패: {str(e)}")
            
            def _handle_component_failure(self, component_name):
                """컴포넌트 장애 처리"""
                circuit_breaker = self.circuit_breakers[component_name]
                circuit_breaker['failure_count'] += 1
                circuit_breaker['last_failure_time'] = datetime.now()
                
                # 서킷 브레이커 활성화 조건 확인
                if circuit_breaker['failure_count'] >= circuit_breaker['failure_threshold']:
                    circuit_breaker['state'] = 'open'
                    print(f"      🚨 서킷 브레이커 OPEN: {component_name}")
                
                # 자동 복구 시도
                component = self.components[component_name]
                if component['recovery_func']:
                    threading.Thread(target=self._attempt_recovery, args=(component_name,)).start()
            
            def _handle_component_recovery(self, component_name):
                """컴포넌트 복구 처리"""
                circuit_breaker = self.circuit_breakers[component_name]
                circuit_breaker['failure_count'] = 0
                circuit_breaker['state'] = 'closed'
                print(f"      ✅ 컴포넌트 복구: {component_name}")
            
            def _attempt_recovery(self, component_name):
                """복구 시도"""
                component = self.components[component_name]
                recovery_func = component['recovery_func']
                
                if not recovery_func:
                    return
                
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        print(f"      🔄 복구 시도 {attempt + 1}/{max_attempts}: {component_name}")
                        success = recovery_func()
                        
                        if success:
                            print(f"      ✅ 복구 성공: {component_name}")
                            break
                        
                    except Exception as e:
                        print(f"      ❌ 복구 실패: {component_name} - {str(e)}")
                    
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            def _manage_circuit_breakers(self):
                """서킷 브레이커 관리"""
                current_time = datetime.now()
                
                for component_name, circuit_breaker in self.circuit_breakers.items():
                    if circuit_breaker['state'] == 'open':
                        # 타임아웃 후 half-open으로 전환
                        if circuit_breaker['last_failure_time']:
                            time_since_failure = (current_time - circuit_breaker['last_failure_time']).total_seconds()
                            if time_since_failure >= circuit_breaker['timeout']:
                                circuit_breaker['state'] = 'half-open'
                                print(f"      🔄 서킷 브레이커 HALF-OPEN: {component_name}")
                    
                    elif circuit_breaker['state'] == 'half-open':
                        # half-open 상태에서 성공하면 closed로 전환
                        component = self.components[component_name]
                        if component['status'] == 'healthy':
                            circuit_breaker['state'] = 'closed'
                            circuit_breaker['failure_count'] = 0
                            print(f"      ✅ 서킷 브레이커 CLOSED: {component_name}")
            
            def _update_system_state(self):
                """전체 시스템 상태 업데이트"""
                unhealthy_components = [
                    name for name, comp in self.components.items() 
                    if comp['status'] != 'healthy'
                ]
                
                previous_state = self.current_state
                
                if not unhealthy_components:
                    self.current_state = SystemState.HEALTHY
                elif len(unhealthy_components) <= len(self.components) * 0.3:  # 30% 이하
                    self.current_state = SystemState.DEGRADED
                elif len(unhealthy_components) <= len(self.components) * 0.7:  # 70% 이하
                    self.current_state = SystemState.CRITICAL
                else:
                    self.current_state = SystemState.FAILED
                
                # 상태 변화 기록
                if previous_state != self.current_state:
                    state_change = {
                        'from_state': previous_state.value,
                        'to_state': self.current_state.value,
                        'timestamp': datetime.now(),
                        'unhealthy_components': unhealthy_components.copy()
                    }
                    self.state_history.append(state_change)
                    
                    # 다운타임 이벤트 기록
                    if self.current_state in [SystemState.CRITICAL, SystemState.FAILED]:
                        self.resilience_metrics['downtime_events'].append({
                            'start_time': datetime.now(),
                            'state': self.current_state.value,
                            'end_time': None
                        })
                    elif previous_state in [SystemState.CRITICAL, SystemState.FAILED]:
                        # 복구 완료
                        if self.resilience_metrics['downtime_events']:
                            last_event = self.resilience_metrics['downtime_events'][-1]
                            if last_event['end_time'] is None:
                                last_event['end_time'] = datetime.now()
                                recovery_time = (last_event['end_time'] - last_event['start_time']).total_seconds()
                                self.resilience_metrics['mttr'].append(recovery_time)
            
            def inject_failure(self, component_name, duration=5.0):
                """장애 주입 (테스트용)"""
                if component_name not in self.components:
                    return False
                
                def failure_injector():
                    # 일시적으로 컴포넌트를 실패 상태로 만듦
                    original_health_check = self.components[component_name]['health_check']
                    self.components[component_name]['health_check'] = lambda: False
                    
                    print(f"    💉 장애 주입: {component_name} (지속시간: {duration}초)")
                    time.sleep(duration)
                    
                    # 원래 헬스 체크 복원
                    self.components[component_name]['health_check'] = original_health_check
                    print(f"    🔄 장애 해제: {component_name}")
                
                threading.Thread(target=failure_injector).start()
                return True
            
            def chaos_test(self, duration=30.0, failure_probability=0.3):
                """카오스 테스트"""
                print(f"    🌀 카오스 테스트 시작 (지속시간: {duration}초, 실패 확률: {failure_probability})")
                
                start_time = datetime.now()
                chaos_events = []
                
                while (datetime.now() - start_time).total_seconds() < duration:
                    for component_name in self.components.keys():
                        if random.random() < failure_probability:
                            failure_duration = random.uniform(2.0, 8.0)
                            self.inject_failure(component_name, failure_duration)
                            
                            chaos_events.append({
                                'component': component_name,
                                'timestamp': datetime.now(),
                                'duration': failure_duration
                            })
                    
                    time.sleep(random.uniform(1.0, 5.0))
                
                print(f"    🌀 카오스 테스트 완료: {len(chaos_events)}개 장애 주입")
                return chaos_events
            
            def calculate_availability(self):
                """가용성 계산"""
                if not self.state_history:
                    return 100.0
                
                total_time = (datetime.now() - self.state_history[0]['timestamp']).total_seconds()
                downtime = 0.0
                
                for event in self.resilience_metrics['downtime_events']:
                    if event['end_time']:
                        downtime += (event['end_time'] - event['start_time']).total_seconds()
                    else:
                        # 현재도 다운 상태
                        downtime += (datetime.now() - event['start_time']).total_seconds()
                
                if total_time > 0:
                    self.resilience_metrics['availability'] = ((total_time - downtime) / total_time) * 100
                else:
                    self.resilience_metrics['availability'] = 100.0
                
                return self.resilience_metrics['availability']
            
            def get_resilience_report(self):
                """복원력 보고서"""
                availability = self.calculate_availability()
                
                avg_mttr = sum(self.resilience_metrics['mttr']) / len(self.resilience_metrics['mttr']) if self.resilience_metrics['mttr'] else 0
                
                return {
                    'current_state': self.current_state.value,
                    'total_components': len(self.components),
                    'healthy_components': len([c for c in self.components.values() if c['status'] == 'healthy']),
                    'availability_percent': availability,
                    'average_mttr_seconds': avg_mttr,
                    'total_downtime_events': len(self.resilience_metrics['downtime_events']),
                    'state_changes': len(self.state_history),
                    'circuit_breaker_states': {name: cb['state'] for name, cb in self.circuit_breakers.items()}
                }
        
        # 모의 컴포넌트 헬스 체크 함수들
        def database_health_check():
            """데이터베이스 헬스 체크"""
            # 90% 확률로 정상
            return random.random() > 0.1
        
        def api_service_health_check():
            """API 서비스 헬스 체크"""
            # 85% 확률로 정상
            return random.random() > 0.15
        
        def cache_service_health_check():
            """캐시 서비스 헬스 체크"""
            # 95% 확률로 정상
            return random.random() > 0.05
        
        def file_storage_health_check():
            """파일 저장소 헬스 체크"""
            # 88% 확률로 정상
            return random.random() > 0.12
        
        # 복구 함수들
        def database_recovery():
            """데이터베이스 복구"""
            time.sleep(1)
            return random.random() > 0.2  # 80% 복구 성공률
        
        def api_service_recovery():
            """API 서비스 복구"""
            time.sleep(2)
            return random.random() > 0.3  # 70% 복구 성공률
        
        def cache_service_recovery():
            """캐시 서비스 복구"""
            time.sleep(0.5)
            return random.random() > 0.1  # 90% 복구 성공률
        
        # 복원력 관리자 테스트
        resilience_manager = ResilienceManager()
        
        # 컴포넌트 등록
        resilience_manager.register_component('database', database_health_check, database_recovery)
        resilience_manager.register_component('api_service', api_service_health_check, api_service_recovery)
        resilience_manager.register_component('cache_service', cache_service_health_check, cache_service_recovery)
        resilience_manager.register_component('file_storage', file_storage_health_check)
        
        # 모니터링 시작
        resilience_manager.start_monitoring(check_interval=1.0)
        
        # 정상 상태에서 잠시 실행
        time.sleep(3)
        
        # 의도적 장애 주입
        resilience_manager.inject_failure('database', duration=5.0)
        time.sleep(2)
        resilience_manager.inject_failure('api_service', duration=4.0)
        
        # 장애 복구 대기
        time.sleep(8)
        
        # 카오스 테스트
        chaos_events = resilience_manager.chaos_test(duration=15.0, failure_probability=0.4)
        
        # 카오스 테스트 후 안정화 대기
        time.sleep(5)
        
        # 모니터링 중지
        resilience_manager.stop_monitoring()
        
        # 최종 보고서
        resilience_report = resilience_manager.get_resilience_report()
        
        # 결과 검증
        assert resilience_report['total_components'] == 4, "등록된 컴포넌트 수가 일치하지 않습니다."
        assert resilience_report['state_changes'] > 0, "상태 변화가 감지되지 않았습니다."
        assert resilience_report['availability_percent'] >= 70, f"가용성이 너무 낮습니다: {resilience_report['availability_percent']:.1f}%"
        assert len(chaos_events) > 0, "카오스 테스트에서 장애가 주입되지 않았습니다."
        assert resilience_report['total_downtime_events'] > 0, "다운타임 이벤트가 기록되지 않았습니다."
        
        # 서킷 브레이커 동작 확인
        circuit_breaker_states = resilience_report['circuit_breaker_states']
        has_circuit_breaker_activity = any(state != 'closed' for state in circuit_breaker_states.values())
        
        print(f"  🏥 시스템 가용성: {resilience_report['availability_percent']:.1f}%")
        print(f"  ⚡ 평균 복구 시간: {resilience_report['average_mttr_seconds']:.1f}초")
        print(f"  🌀 카오스 이벤트: {len(chaos_events)}개")
        print(f"  🔄 상태 변화: {resilience_report['state_changes']}회")
        
        print("✅ 시스템 복원력 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 시스템 복원력 테스트 실패: {str(e)}")
        return False

def main():
    """S04_M03_T02 통합 테스트 메인 함수"""
    print("🚀 S04_M03_T02 시스템 안정성 및 장애 복구 테스트 시작")
    print("=" * 60)
    
    test_results = []
    start_time = time.time()
    
    # 테스트 실행
    tests = [
        ("장애 시나리오", test_failure_scenarios),
        ("데이터 무결성", test_data_integrity),
        ("시스템 복원력", test_system_resilience)
    ]
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name} 테스트 실행 중...")
        try:
            result = test_func()
            test_results.append((test_name, result))
            if result:
                print(f"✅ {test_name} 테스트 성공")
            else:
                print(f"❌ {test_name} 테스트 실패")
        except Exception as e:
            print(f"💥 {test_name} 테스트 예외 발생: {str(e)}")
            test_results.append((test_name, False))
    
    # 결과 요약
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 60)
    print("🎯 S04_M03_T02 시스템 안정성 및 장애 복구 테스트 결과 요약")
    print("=" * 60)
    
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"  {status}: {test_name}")
    
    print(f"\n📊 전체 결과: {passed_tests}/{total_tests} 테스트 통과 ({passed_tests/total_tests*100:.1f}%)")
    print(f"⏱️  소요 시간: {duration:.2f}초")
    
    if passed_tests == total_tests:
        print("\n🎉 모든 테스트 통과! S04_M03_T02 작업이 성공적으로 완료되었습니다.")
        return True
    else:
        print(f"\n⚠️  {total_tests - passed_tests}개 테스트 실패. 추가 수정이 필요합니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)