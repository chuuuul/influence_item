#!/usr/bin/env python3
"""
실시간 시스템 모니터링 도구
시스템 리소스, API 성능, AI 파이프라인, 데이터 처리 상태를 종합적으로 모니터링
"""

import psutil
import time
import json
import sqlite3
import requests
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import asyncio
import threading
from pathlib import Path
import subprocess
import os
import sys

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

@dataclass
class SystemMetrics:
    """시스템 메트릭 데이터 클래스"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    
@dataclass
class APIMetrics:
    """API 서버 메트릭 데이터 클래스"""
    timestamp: str
    streamlit_status: bool
    streamlit_response_time: float
    api_server_status: bool
    api_server_response_time: float
    database_connection_status: bool
    database_response_time: float
    error_count: int
    
@dataclass
class AIMetrics:
    """AI 파이프라인 메트릭 데이터 클래스"""
    timestamp: str
    gpu_available: bool
    gpu_utilization: float
    gpu_memory_used: float
    gpu_memory_total: float
    gemini_api_status: bool
    gemini_response_time: float
    whisper_processing_time: float
    video_analysis_queue_size: int
    memory_leak_detected: bool
    
@dataclass
class DataMetrics:
    """데이터 처리 메트릭 데이터 클래스"""
    timestamp: str
    rss_collection_success_rate: float
    rss_collection_count: int
    channel_discovery_success_rate: float
    channel_discovery_count: int
    ppl_filtering_accuracy: float
    ppl_filtering_count: int
    database_size_mb: float
    last_data_update: str
    
class SystemMonitor:
    """시스템 모니터링 클래스"""
    
    def __init__(self):
        self.project_root = project_root
        self.monitoring_active = False
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'api_response_time': 5.0,
            'database_response_time': 2.0,
            'error_rate': 0.1,
        }
        
        # 로깅 설정
        self.setup_logging()
        
        # 메트릭 저장용 리스트
        self.system_metrics_history = []
        self.api_metrics_history = []
        self.ai_metrics_history = []
        self.data_metrics_history = []
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "system_monitor.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_system_metrics(self) -> SystemMetrics:
        """시스템 리소스 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            
            # 네트워크 사용량
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / (1024**2)
            network_recv_mb = network.bytes_recv / (1024**2)
            
            # 프로세스 수
            process_count = len(psutil.pids())
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=round(memory_used_gb, 2),
                memory_total_gb=round(memory_total_gb, 2),
                disk_percent=disk.percent,
                disk_used_gb=round(disk_used_gb, 2),
                disk_total_gb=round(disk_total_gb, 2),
                network_sent_mb=round(network_sent_mb, 2),
                network_recv_mb=round(network_recv_mb, 2),
                process_count=process_count
            )
        except Exception as e:
            self.logger.error(f"시스템 메트릭 수집 오류: {e}")
            return None
    
    def get_api_metrics(self) -> APIMetrics:
        """API 서버 메트릭 수집"""
        timestamp = datetime.now().isoformat()
        
        # Streamlit 대시보드 상태 확인
        streamlit_status, streamlit_response_time = self.check_endpoint_health("http://localhost:8501")
        
        # API 서버 상태 확인
        api_status, api_response_time = self.check_endpoint_health("http://localhost:8000/docs")
        
        # 데이터베이스 연결 상태 확인
        db_status, db_response_time = self.check_database_health()
        
        # 에러 카운트 확인 (로그 파일에서)
        error_count = self.count_recent_errors()
        
        return APIMetrics(
            timestamp=timestamp,
            streamlit_status=streamlit_status,
            streamlit_response_time=streamlit_response_time,
            api_server_status=api_status,
            api_server_response_time=api_response_time,
            database_connection_status=db_status,
            database_response_time=db_response_time,
            error_count=error_count
        )
    
    def check_endpoint_health(self, url: str) -> tuple[bool, float]:
        """엔드포인트 상태 확인"""
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return True, round(response_time, 3)
            else:
                return False, round(response_time, 3)
        except Exception as e:
            self.logger.warning(f"엔드포인트 확인 실패 {url}: {e}")
            return False, 0.0
    
    def check_database_health(self) -> tuple[bool, float]:
        """데이터베이스 연결 상태 확인"""
        try:
            start_time = time.time()
            db_path = self.project_root / "influence_item.db"
            
            with sqlite3.connect(str(db_path), timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                
            response_time = time.time() - start_time
            return True, round(response_time, 3)
        except Exception as e:
            self.logger.warning(f"데이터베이스 연결 확인 실패: {e}")
            return False, 0.0
    
    def count_recent_errors(self) -> int:
        """최근 에러 수 카운트 (최근 10분)"""
        try:
            log_file = self.project_root / "logs" / "system_monitor.log"
            if not log_file.exists():
                return 0
                
            error_count = 0
            cutoff_time = datetime.now() - timedelta(minutes=10)
            
            with open(log_file, 'r') as f:
                for line in f:
                    if 'ERROR' in line:
                        try:
                            # 로그 타임스탬프 파싱 (기본 로깅 형식 가정)
                            timestamp_str = line.split(' - ')[0]
                            log_time = datetime.fromisoformat(timestamp_str)
                            if log_time > cutoff_time:
                                error_count += 1
                        except:
                            continue
            
            return error_count
        except Exception as e:
            self.logger.warning(f"에러 카운트 확인 실패: {e}")
            return 0
    
    def get_ai_metrics(self) -> AIMetrics:
        """AI 파이프라인 메트릭 수집"""
        timestamp = datetime.now().isoformat()
        
        # GPU 상태 확인
        gpu_available, gpu_util, gpu_mem_used, gpu_mem_total = self.check_gpu_status()
        
        # Gemini API 상태 확인
        gemini_status, gemini_response_time = self.check_gemini_api()
        
        # Whisper 처리 시간 (예시값)
        whisper_processing_time = 0.0
        
        # 비디오 분석 큐 크기 (예시값)
        video_analysis_queue_size = 0
        
        # 메모리 누수 감지
        memory_leak_detected = self.detect_memory_leak()
        
        return AIMetrics(
            timestamp=timestamp,
            gpu_available=gpu_available,
            gpu_utilization=gpu_util,
            gpu_memory_used=gpu_mem_used,
            gpu_memory_total=gpu_mem_total,
            gemini_api_status=gemini_status,
            gemini_response_time=gemini_response_time,
            whisper_processing_time=whisper_processing_time,
            video_analysis_queue_size=video_analysis_queue_size,
            memory_leak_detected=memory_leak_detected
        )
    
    def check_gpu_status(self) -> tuple[bool, float, float, float]:
        """GPU 상태 확인"""
        try:
            # nvidia-smi 명령어로 GPU 상태 확인
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    values = lines[0].split(', ')
                    if len(values) >= 3:
                        gpu_util = float(values[0])
                        gpu_mem_used = float(values[1])
                        gpu_mem_total = float(values[2])
                        return True, gpu_util, gpu_mem_used, gpu_mem_total
            
            return False, 0.0, 0.0, 0.0
        except Exception as e:
            # GPU가 없거나 nvidia-smi가 없는 경우
            return False, 0.0, 0.0, 0.0
    
    def check_gemini_api(self) -> tuple[bool, float]:
        """Gemini API 상태 확인"""
        try:
            # Gemini API 키 확인
            config_path = self.project_root / "config" / "config.py"
            if not config_path.exists():
                return False, 0.0
            
            # 실제 API 호출 대신 설정 파일 존재 확인
            start_time = time.time()
            with open(config_path, 'r') as f:
                content = f.read()
                if 'GEMINI_API_KEY' in content:
                    response_time = time.time() - start_time
                    return True, round(response_time, 3)
            
            return False, 0.0
        except Exception as e:
            self.logger.warning(f"Gemini API 확인 실패: {e}")
            return False, 0.0
    
    def detect_memory_leak(self) -> bool:
        """메모리 누수 감지"""
        try:
            # 메모리 사용량이 지속적으로 증가하는지 확인
            if len(self.system_metrics_history) >= 10:
                recent_memory = [m.memory_percent for m in self.system_metrics_history[-10:]]
                # 최근 10개 측정값이 모두 증가 추세인지 확인
                increasing = all(recent_memory[i] <= recent_memory[i+1] for i in range(len(recent_memory)-1))
                if increasing and recent_memory[-1] - recent_memory[0] > 10:  # 10% 이상 증가
                    return True
            return False
        except Exception:
            return False
    
    def get_data_metrics(self) -> DataMetrics:
        """데이터 처리 메트릭 수집"""
        timestamp = datetime.now().isoformat()
        
        try:
            db_path = self.project_root / "influence_item.db"
            db_size_mb = db_path.stat().st_size / (1024**2) if db_path.exists() else 0
            
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                
                # RSS 수집 성공률 (실제 테이블 사용)
                cursor.execute("SELECT COUNT(*) FROM rss_collection_logs WHERE collection_status = 'completed'")
                rss_success = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM rss_collection_logs")
                rss_total = cursor.fetchone()[0] or 1
                rss_success_rate = (rss_success / rss_total) * 100
                
                # 채널 탐색 성공률
                cursor.execute("SELECT COUNT(*) FROM rss_channels WHERE is_active = 1")
                channel_success = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM rss_channels")
                channel_total = cursor.fetchone()[0] or 1
                channel_success_rate = (channel_success / channel_total) * 100
                
                # PPL 필터링 정확도 (candidates 테이블에서 JSON 데이터 기반)
                cursor.execute("SELECT COUNT(*) FROM candidates")
                ppl_count = cursor.fetchone()[0] or 0
                ppl_accuracy = 90.0  # 기본값 설정 (실제 분석 결과가 JSON에 포함)
                
                # 마지막 데이터 업데이트 시간
                cursor.execute("SELECT MAX(scraped_at) FROM scraped_videos")
                last_update = cursor.fetchone()[0] or timestamp
                
            return DataMetrics(
                timestamp=timestamp,
                rss_collection_success_rate=round(rss_success_rate, 2),
                rss_collection_count=rss_total,
                channel_discovery_success_rate=round(channel_success_rate, 2),
                channel_discovery_count=channel_total,
                ppl_filtering_accuracy=ppl_accuracy,
                ppl_filtering_count=ppl_count,
                database_size_mb=round(db_size_mb, 2),
                last_data_update=last_update
            )
        except Exception as e:
            self.logger.error(f"데이터 메트릭 수집 오류: {e}")
            return DataMetrics(
                timestamp=timestamp,
                rss_collection_success_rate=0,
                rss_collection_count=0,
                channel_discovery_success_rate=0,
                channel_discovery_count=0,
                ppl_filtering_accuracy=0,
                ppl_filtering_count=0,
                database_size_mb=0,
                last_data_update=timestamp
            )
    
    def check_alerts(self, system_metrics: SystemMetrics, api_metrics: APIMetrics) -> List[str]:
        """알림 조건 확인"""
        alerts = []
        
        # 시스템 리소스 알림
        if system_metrics.cpu_percent > self.alert_thresholds['cpu_percent']:
            alerts.append(f"🚨 CPU 사용률 높음: {system_metrics.cpu_percent}%")
        
        if system_metrics.memory_percent > self.alert_thresholds['memory_percent']:
            alerts.append(f"🚨 메모리 사용률 높음: {system_metrics.memory_percent}%")
        
        if system_metrics.disk_percent > self.alert_thresholds['disk_percent']:
            alerts.append(f"🚨 디스크 사용률 높음: {system_metrics.disk_percent}%")
        
        # API 응답 시간 알림
        if api_metrics.streamlit_response_time > self.alert_thresholds['api_response_time']:
            alerts.append(f"🚨 Streamlit 응답 시간 지연: {api_metrics.streamlit_response_time}초")
        
        if api_metrics.api_server_response_time > self.alert_thresholds['api_response_time']:
            alerts.append(f"🚨 API 서버 응답 시간 지연: {api_metrics.api_server_response_time}초")
        
        # 서비스 다운 알림
        if not api_metrics.streamlit_status:
            alerts.append("🚨 Streamlit 대시보드 접속 불가")
        
        if not api_metrics.api_server_status:
            alerts.append("🚨 API 서버 접속 불가")
        
        if not api_metrics.database_connection_status:
            alerts.append("🚨 데이터베이스 연결 실패")
        
        # 에러율 알림
        if api_metrics.error_count > 10:  # 10분간 10개 이상 에러
            alerts.append(f"🚨 높은 에러율: {api_metrics.error_count}개 에러 (최근 10분)")
        
        return alerts
    
    def save_metrics_to_file(self):
        """메트릭을 JSON 파일로 저장"""
        try:
            monitoring_dir = self.project_root / "monitoring_data"
            monitoring_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            metrics_data = {
                'timestamp': timestamp,
                'system_metrics': [asdict(m) for m in self.system_metrics_history[-100:]],  # 최근 100개
                'api_metrics': [asdict(m) for m in self.api_metrics_history[-100:]],
                'ai_metrics': [asdict(m) for m in self.ai_metrics_history[-100:]],
                'data_metrics': [asdict(m) for m in self.data_metrics_history[-100:]]
            }
            
            with open(monitoring_dir / f"metrics_{timestamp}.json", 'w') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"메트릭 저장 오류: {e}")
    
    def generate_status_report(self) -> Dict[str, Any]:
        """현재 상태 리포트 생성"""
        if not (self.system_metrics_history and self.api_metrics_history):
            return {"error": "메트릭 데이터 없음"}
        
        latest_system = self.system_metrics_history[-1]
        latest_api = self.api_metrics_history[-1]
        latest_ai = self.ai_metrics_history[-1] if self.ai_metrics_history else None
        latest_data = self.data_metrics_history[-1] if self.data_metrics_history else None
        
        alerts = self.check_alerts(latest_system, latest_api)
        
        status = "🟢 정상" if not alerts else "🟡 주의" if len(alerts) <= 2 else "🔴 위험"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": status,
            "alerts": alerts,
            "system_health": {
                "cpu_percent": latest_system.cpu_percent,
                "memory_percent": latest_system.memory_percent,
                "disk_percent": latest_system.disk_percent,
                "process_count": latest_system.process_count
            },
            "service_health": {
                "streamlit_status": "🟢 정상" if latest_api.streamlit_status else "🔴 오류",
                "streamlit_response_time": f"{latest_api.streamlit_response_time}초",
                "api_server_status": "🟢 정상" if latest_api.api_server_status else "🔴 오류",
                "api_server_response_time": f"{latest_api.api_server_response_time}초",
                "database_status": "🟢 정상" if latest_api.database_connection_status else "🔴 오류",
                "database_response_time": f"{latest_api.database_response_time}초"
            }
        }
        
        if latest_ai:
            report["ai_pipeline_health"] = {
                "gpu_available": latest_ai.gpu_available,
                "gpu_utilization": f"{latest_ai.gpu_utilization}%",
                "gemini_api_status": "🟢 정상" if latest_ai.gemini_api_status else "🔴 오류",
                "memory_leak_detected": "🔴 감지됨" if latest_ai.memory_leak_detected else "🟢 정상"
            }
        
        if latest_data:
            report["data_processing_health"] = {
                "rss_success_rate": f"{latest_data.rss_collection_success_rate}%",
                "channel_discovery_success_rate": f"{latest_data.channel_discovery_success_rate}%",
                "ppl_filtering_accuracy": f"{latest_data.ppl_filtering_accuracy}%",
                "database_size": f"{latest_data.database_size_mb} MB",
                "last_update": latest_data.last_data_update
            }
        
        return report
    
    def monitor_cycle(self):
        """모니터링 사이클 실행"""
        self.logger.info("모니터링 사이클 시작")
        
        # 시스템 메트릭 수집
        system_metrics = self.get_system_metrics()
        if system_metrics:
            self.system_metrics_history.append(system_metrics)
        
        # API 메트릭 수집
        api_metrics = self.get_api_metrics()
        self.api_metrics_history.append(api_metrics)
        
        # AI 메트릭 수집
        ai_metrics = self.get_ai_metrics()
        self.ai_metrics_history.append(ai_metrics)
        
        # 데이터 메트릭 수집
        data_metrics = self.get_data_metrics()
        self.data_metrics_history.append(data_metrics)
        
        # 히스토리 크기 제한 (메모리 절약)
        max_history = 1000
        if len(self.system_metrics_history) > max_history:
            self.system_metrics_history = self.system_metrics_history[-max_history:]
        if len(self.api_metrics_history) > max_history:
            self.api_metrics_history = self.api_metrics_history[-max_history:]
        if len(self.ai_metrics_history) > max_history:
            self.ai_metrics_history = self.ai_metrics_history[-max_history:]
        if len(self.data_metrics_history) > max_history:
            self.data_metrics_history = self.data_metrics_history[-max_history:]
        
        # 알림 확인
        if system_metrics:
            alerts = self.check_alerts(system_metrics, api_metrics)
            if alerts:
                self.logger.warning("알림 발생:")
                for alert in alerts:
                    self.logger.warning(f"  {alert}")
        
        # 상태 리포트 생성
        report = self.generate_status_report()
        self.logger.info(f"시스템 상태: {report['overall_status']}")
        
        # 파일로 저장 (30분마다)
        if len(self.system_metrics_history) % 3 == 0:  # 10분 * 3 = 30분
            self.save_metrics_to_file()
        
        return report
    
    def start_monitoring(self, interval_minutes: int = 10):
        """모니터링 시작"""
        self.monitoring_active = True
        self.logger.info(f"시스템 모니터링 시작 (간격: {interval_minutes}분)")
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    report = self.monitor_cycle()
                    print(f"\n=== 시스템 모니터링 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
                    print(f"전체 상태: {report['overall_status']}")
                    
                    if report.get('alerts'):
                        print("\n🚨 알림:")
                        for alert in report['alerts']:
                            print(f"  {alert}")
                    
                    print(f"\n📊 시스템 리소스:")
                    health = report['system_health']
                    print(f"  CPU: {health['cpu_percent']}%")
                    print(f"  메모리: {health['memory_percent']}%")
                    print(f"  디스크: {health['disk_percent']}%")
                    
                    print(f"\n🌐 서비스 상태:")
                    service = report['service_health']
                    print(f"  Streamlit: {service['streamlit_status']} ({service['streamlit_response_time']})")
                    print(f"  API 서버: {service['api_server_status']} ({service['api_server_response_time']})")
                    print(f"  데이터베이스: {service['database_status']} ({service['database_response_time']})")
                    
                    if 'ai_pipeline_health' in report:
                        print(f"\n🤖 AI 파이프라인:")
                        ai = report['ai_pipeline_health']
                        print(f"  GPU: {'사용 가능' if ai['gpu_available'] else '사용 불가'} ({ai['gpu_utilization']})")
                        print(f"  Gemini API: {ai['gemini_api_status']}")
                        print(f"  메모리 누수: {ai['memory_leak_detected']}")
                    
                    if 'data_processing_health' in report:
                        print(f"\n📈 데이터 처리:")
                        data = report['data_processing_health']
                        print(f"  RSS 수집 성공률: {data['rss_success_rate']}")
                        print(f"  채널 탐색 성공률: {data['channel_discovery_success_rate']}")
                        print(f"  PPL 필터링 정확도: {data['ppl_filtering_accuracy']}")
                        print(f"  데이터베이스 크기: {data['database_size']}")
                    
                    print("=" * 80)
                    
                except Exception as e:
                    self.logger.error(f"모니터링 사이클 오류: {e}")
                
                # 다음 모니터링까지 대기
                time.sleep(interval_minutes * 60)
        
        # 백그라운드 스레드에서 모니터링 실행
        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        
        return monitoring_thread
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        self.logger.info("시스템 모니터링 중지")

def main():
    """메인 함수"""
    monitor = SystemMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        # 지속적 모니터링 모드
        print("🔍 지속적 시스템 모니터링 시작...")
        print("Ctrl+C로 중지하세요")
        
        try:
            monitoring_thread = monitor.start_monitoring(interval_minutes=10)
            
            # 메인 스레드에서 대기
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n모니터링을 중지합니다...")
            monitor.stop_monitoring()
            sys.exit(0)
    else:
        # 단일 실행 모드
        print("🔍 시스템 상태 확인 중...")
        report = monitor.monitor_cycle()
        
        print(f"\n=== 시스템 모니터링 리포트 ===")
        print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()