#!/usr/bin/env python3
"""
고급 장애 복구 및 로드 밸런싱 관리자

이 스크립트는 다중 지역 배포에서 서버 상태를 모니터링하고
자동으로 트래픽을 건강한 서버로 리디렉션합니다.
"""

import asyncio
import aiohttp
import json
import time
import logging
import os
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ServerHealth:
    """서버 건강 상태 정보"""
    region: str
    endpoint: str
    is_healthy: bool
    response_time_ms: float
    last_check: datetime
    error_count: int
    consecutive_failures: int
    load_percentage: float
    memory_usage: float
    cpu_usage: float

@dataclass
class LoadBalancerConfig:
    """로드 밸런서 설정"""
    health_check_interval: int = 30  # seconds
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    max_response_time_ms: float = 5000
    max_load_percentage: float = 80
    failover_cooldown: int = 300  # seconds

class FailoverManager:
    """장애 복구 관리자"""
    
    def __init__(self, config_file: str = None):
        self.config = LoadBalancerConfig()
        self.servers: Dict[str, ServerHealth] = {}
        self.last_failover: Dict[str, datetime] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        
        # 설정 파일 로드
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        
        # 서버 목록 초기화
        self.initialize_servers()
    
    def load_config(self, config_file: str):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    
            logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    
    def initialize_servers(self):
        """서버 목록 초기화"""
        # 환경변수 또는 기본값으로 서버 목록 구성
        regions = [
            {
                "region": "us-east-1",
                "endpoint": os.getenv("US_EAST_ENDPOINT", "http://localhost:8501"),
                "gpu_endpoint": os.getenv("US_EAST_GPU_ENDPOINT", "http://localhost:8001")
            },
            {
                "region": "ap-northeast-2", 
                "endpoint": os.getenv("AP_NE2_ENDPOINT", "http://localhost:8502"),
                "gpu_endpoint": os.getenv("AP_NE2_GPU_ENDPOINT", "http://localhost:8002")
            },
            {
                "region": "eu-west-1",
                "endpoint": os.getenv("EU_WEST_ENDPOINT", "http://localhost:8503"),
                "gpu_endpoint": os.getenv("EU_WEST_GPU_ENDPOINT", "http://localhost:8003")
            }
        ]
        
        for region_config in regions:
            region = region_config["region"]
            
            # CPU 서버 추가
            self.servers[f"{region}-cpu"] = ServerHealth(
                region=region,
                endpoint=region_config["endpoint"],
                is_healthy=True,
                response_time_ms=0,
                last_check=datetime.now(),
                error_count=0,
                consecutive_failures=0,
                load_percentage=0,
                memory_usage=0,
                cpu_usage=0
            )
            
            # GPU 서버 추가
            self.servers[f"{region}-gpu"] = ServerHealth(
                region=region,
                endpoint=region_config["gpu_endpoint"],
                is_healthy=True,
                response_time_ms=0,
                last_check=datetime.now(),
                error_count=0,
                consecutive_failures=0,
                load_percentage=0,
                memory_usage=0,
                cpu_usage=0
            )
        
        logger.info(f"Initialized {len(self.servers)} servers for monitoring")

    async def start_monitoring(self):
        """모니터링 시작"""
        if self.running:
            logger.warning("Monitoring is already running")
            return
        
        self.running = True
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        logger.info("Starting failover monitoring...")
        
        try:
            while self.running:
                await self.check_all_servers()
                await self.update_load_balancer_config()
                await asyncio.sleep(self.config.health_check_interval)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            await self.stop_monitoring()

    async def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Monitoring stopped")

    async def check_all_servers(self):
        """모든 서버 상태 확인"""
        tasks = []
        for server_id, server in self.servers.items():
            task = asyncio.create_task(self.check_server_health(server_id, server))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def check_server_health(self, server_id: str, server: ServerHealth):
        """개별 서버 상태 확인"""
        try:
            start_time = time.time()
            
            # CPU 서버는 일반 헬스체크, GPU 서버는 GPU 상태 확인
            if "gpu" in server_id:
                health_endpoint = f"{server.endpoint}/health"
            else:
                health_endpoint = f"{server.endpoint}/_stcore/health"
            
            async with self.session.get(health_endpoint) as response:
                response_time = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    # 성공적인 응답
                    server.response_time_ms = response_time
                    server.consecutive_failures = 0
                    
                    # 상세 상태 정보 수집
                    await self.collect_server_metrics(server_id, server)
                    
                    # 건강 상태 판단
                    server.is_healthy = (
                        response_time <= self.config.max_response_time_ms and
                        server.load_percentage <= self.config.max_load_percentage
                    )
                    
                    if server.is_healthy:
                        logger.debug(f"✅ {server_id}: Healthy (RT: {response_time:.2f}ms)")
                    else:
                        logger.warning(f"⚠️ {server_id}: Degraded performance")
                        
                else:
                    # 비정상 응답
                    await self.handle_server_failure(server_id, server, f"HTTP {response.status}")
                    
        except asyncio.TimeoutError:
            await self.handle_server_failure(server_id, server, "Timeout")
        except Exception as e:
            await self.handle_server_failure(server_id, server, str(e))
        
        server.last_check = datetime.now()

    async def collect_server_metrics(self, server_id: str, server: ServerHealth):
        """서버 메트릭 수집"""
        try:
            # 메트릭 엔드포인트에서 상세 정보 수집
            metrics_endpoint = f"{server.endpoint}/api/metrics"
            
            async with self.session.get(metrics_endpoint) as response:
                if response.status == 200:
                    metrics_data = await response.json()
                    
                    server.cpu_usage = metrics_data.get("cpu_usage", 0)
                    server.memory_usage = metrics_data.get("memory_usage", 0)
                    server.load_percentage = metrics_data.get("load_percentage", 0)
                    
        except Exception as e:
            logger.debug(f"Could not collect metrics for {server_id}: {e}")

    async def handle_server_failure(self, server_id: str, server: ServerHealth, error: str):
        """서버 장애 처리"""
        server.error_count += 1
        server.consecutive_failures += 1
        server.response_time_ms = 0
        
        logger.error(f"❌ {server_id}: Failure #{server.consecutive_failures} - {error}")
        
        # 연속 실패 임계값 확인
        if server.consecutive_failures >= self.config.unhealthy_threshold:
            if server.is_healthy:
                logger.critical(f"🚨 {server_id}: Marked as UNHEALTHY")
                server.is_healthy = False
                await self.trigger_failover(server_id, server)

    async def trigger_failover(self, failed_server_id: str, failed_server: ServerHealth):
        """장애 복구 트리거"""
        region = failed_server.region
        
        # 쿨다운 기간 확인
        if region in self.last_failover:
            time_since_last = datetime.now() - self.last_failover[region]
            if time_since_last.seconds < self.config.failover_cooldown:
                logger.info(f"Failover cooldown active for {region}")
                return
        
        # 같은 지역의 다른 서버 또는 다른 지역 서버 찾기
        backup_servers = self.find_backup_servers(failed_server_id, region)
        
        if backup_servers:
            await self.execute_failover(failed_server_id, backup_servers)
            self.last_failover[region] = datetime.now()
        else:
            logger.critical(f"🚨 No backup servers available for {failed_server_id}")
            await self.send_critical_alert(failed_server_id, failed_server)

    def find_backup_servers(self, failed_server_id: str, region: str) -> List[str]:
        """백업 서버 찾기"""
        backup_servers = []
        
        # 1. 같은 지역의 다른 서버 찾기
        for server_id, server in self.servers.items():
            if (server_id != failed_server_id and 
                server.region == region and 
                server.is_healthy):
                backup_servers.append(server_id)
        
        # 2. 다른 지역의 건강한 서버 찾기
        if not backup_servers:
            for server_id, server in self.servers.items():
                if (server_id != failed_server_id and 
                    server.region != region and 
                    server.is_healthy):
                    backup_servers.append(server_id)
        
        # 응답 시간 기준으로 정렬
        backup_servers.sort(key=lambda x: self.servers[x].response_time_ms)
        
        return backup_servers

    async def execute_failover(self, failed_server_id: str, backup_servers: List[str]):
        """실제 장애 복구 실행"""
        logger.info(f"🔄 Executing failover from {failed_server_id} to {backup_servers[0]}")
        
        try:
            # Nginx 설정 업데이트
            await self.update_nginx_upstream(failed_server_id, backup_servers[0])
            
            # DNS 업데이트 (필요시)
            await self.update_dns_records(failed_server_id, backup_servers[0])
            
            # 로드 밸런서 설정 리로드
            await self.reload_load_balancer()
            
            logger.info(f"✅ Failover completed: {failed_server_id} -> {backup_servers[0]}")
            
        except Exception as e:
            logger.error(f"❌ Failover failed: {e}")

    async def update_nginx_upstream(self, failed_server: str, backup_server: str):
        """Nginx 업스트림 설정 업데이트"""
        try:
            # nginx.conf 파일에서 실패한 서버를 backup_server로 교체
            nginx_config_path = Path(__file__).parent.parent / "nginx.global.conf"
            
            with open(nginx_config_path, 'r') as f:
                config_content = f.read()
            
            failed_server_info = self.servers[failed_server]
            backup_server_info = self.servers[backup_server]
            
            # 서버 엔드포인트 교체
            failed_endpoint = failed_server_info.endpoint.replace("http://", "").replace("https://", "")
            backup_endpoint = backup_server_info.endpoint.replace("http://", "").replace("https://", "")
            
            updated_config = config_content.replace(failed_endpoint, backup_endpoint)
            
            # 임시 파일에 저장
            temp_config_path = nginx_config_path.with_suffix('.tmp')
            with open(temp_config_path, 'w') as f:
                f.write(updated_config)
            
            # 설정 파일 유효성 검사
            result = subprocess.run(
                ["nginx", "-t", "-c", str(temp_config_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # 유효한 설정이면 적용
                temp_config_path.replace(nginx_config_path)
                logger.info(f"Updated Nginx upstream: {failed_server} -> {backup_server}")
            else:
                logger.error(f"Invalid Nginx config: {result.stderr}")
                temp_config_path.unlink()
                
        except Exception as e:
            logger.error(f"Failed to update Nginx upstream: {e}")

    async def update_dns_records(self, failed_server: str, backup_server: str):
        """DNS 레코드 업데이트 (클라우드 DNS 서비스 사용)"""
        # AWS Route 53, CloudFlare DNS 등의 API 호출
        # 실제 구현은 사용하는 DNS 서비스에 따라 달라짐
        logger.info(f"DNS update required: {failed_server} -> {backup_server}")

    async def reload_load_balancer(self):
        """로드 밸런서 설정 리로드"""
        try:
            # Nginx 리로드
            result = subprocess.run(
                ["nginx", "-s", "reload"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Load balancer configuration reloaded")
            else:
                logger.error(f"Failed to reload load balancer: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error reloading load balancer: {e}")

    async def update_load_balancer_config(self):
        """로드 밸런서 설정 업데이트"""
        # 서버 상태에 따라 가중치 조정
        weights = self.calculate_server_weights()
        
        # 새로운 설정 생성
        config_updates = {}
        for server_id, weight in weights.items():
            if weight > 0:
                config_updates[server_id] = {
                    "weight": weight,
                    "max_fails": self.config.unhealthy_threshold,
                    "fail_timeout": self.config.failover_cooldown
                }
        
        # 설정 파일에 반영 (실제 구현 필요)
        logger.debug(f"Updated load balancer weights: {config_updates}")

    def calculate_server_weights(self) -> Dict[str, int]:
        """서버 가중치 계산"""
        weights = {}
        
        for server_id, server in self.servers.items():
            if server.is_healthy:
                # 응답 시간과 부하를 고려한 가중치 계산
                response_factor = max(0, (5000 - server.response_time_ms) / 5000)
                load_factor = max(0, (100 - server.load_percentage) / 100)
                
                weight = int((response_factor * load_factor) * 100)
                weights[server_id] = max(1, weight)  # 최소 가중치 1
            else:
                weights[server_id] = 0  # 비정상 서버는 가중치 0
        
        return weights

    async def send_critical_alert(self, failed_server_id: str, server: ServerHealth):
        """위험 알림 발송"""
        alert_message = {
            "timestamp": datetime.now().isoformat(),
            "severity": "CRITICAL",
            "server_id": failed_server_id,
            "region": server.region,
            "endpoint": server.endpoint,
            "consecutive_failures": server.consecutive_failures,
            "last_error": "No backup servers available"
        }
        
        # 알림 채널로 전송 (Slack, 이메일 등)
        await self.send_alert_notification(alert_message)

    async def send_alert_notification(self, alert: Dict):
        """알림 발송"""
        try:
            # Slack 웹훅 또는 이메일 발송
            webhook_url = os.getenv("SLACK_WEBHOOK_URL")
            
            if webhook_url:
                message = {
                    "text": f"🚨 Server Alert: {alert['server_id']} is down!",
                    "attachments": [
                        {
                            "color": "danger",
                            "fields": [
                                {"title": "Server", "value": alert['server_id'], "short": True},
                                {"title": "Region", "value": alert['region'], "short": True},
                                {"title": "Failures", "value": str(alert['consecutive_failures']), "short": True},
                                {"title": "Time", "value": alert['timestamp'], "short": True}
                            ]
                        }
                    ]
                }
                
                async with self.session.post(webhook_url, json=message) as response:
                    if response.status == 200:
                        logger.info("Alert notification sent successfully")
                    else:
                        logger.error(f"Failed to send alert: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error sending alert notification: {e}")

    def get_status_report(self) -> Dict:
        """상태 보고서 생성"""
        healthy_count = sum(1 for s in self.servers.values() if s.is_healthy)
        total_count = len(self.servers)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": f"{healthy_count}/{total_count}",
            "servers": {}
        }
        
        for server_id, server in self.servers.items():
            report["servers"][server_id] = {
                "region": server.region,
                "endpoint": server.endpoint,
                "is_healthy": server.is_healthy,
                "response_time_ms": server.response_time_ms,
                "load_percentage": server.load_percentage,
                "consecutive_failures": server.consecutive_failures,
                "last_check": server.last_check.isoformat()
            }
        
        return report

async def main():
    """메인 실행 함수"""
    config_file = os.getenv("FAILOVER_CONFIG", "failover_config.json")
    
    manager = FailoverManager(config_file)
    
    try:
        await manager.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Shutting down failover manager...")
    finally:
        await manager.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())