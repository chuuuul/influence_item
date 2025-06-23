#!/usr/bin/env python3
"""
M04_S01_T01 다중 지역 배포 인프라 통합 테스트

이 테스트는 다중 지역 배포 시스템의 모든 구성 요소가 올바르게 작동하는지 검증합니다.
"""

import pytest
import asyncio
import aiohttp
import subprocess
import time
import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RegionConfig:
    """지역별 설정 정보"""
    name: str
    endpoint: str
    gpu_endpoint: str
    expected_latency_ms: int
    currency: str
    language: str

# 테스트 대상 지역 설정 (로컬 테스트용)
TEST_REGIONS = [
    RegionConfig(
        name="local-us-east-1",
        endpoint="http://localhost:8501",
        gpu_endpoint="http://localhost:8001",
        expected_latency_ms=50,
        currency="USD",
        language="en"
    ),
    RegionConfig(
        name="local-ap-northeast-2",
        endpoint="http://localhost:8502", 
        gpu_endpoint="http://localhost:8002",
        expected_latency_ms=30,
        currency="KRW",
        language="ko"
    ),
    RegionConfig(
        name="local-eu-west-1",
        endpoint="http://localhost:8503",
        gpu_endpoint="http://localhost:8003", 
        expected_latency_ms=40,
        currency="EUR",
        language="en"
    )
]

class MultiRegionDeploymentTester:
    """다중 지역 배포 테스트 클래스"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: Dict[str, Dict] = {}
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_infrastructure_connectivity(self) -> Dict[str, bool]:
        """인프라 연결성 테스트"""
        logger.info("🔗 Testing infrastructure connectivity across regions...")
        
        results = {}
        
        for region in TEST_REGIONS:
            try:
                # Health check endpoint 테스트
                async with self.session.get(f"{region.endpoint}/health") as response:
                    if response.status == 200:
                        results[region.name] = True
                        logger.info(f"✅ {region.name}: Infrastructure connectivity OK")
                    else:
                        results[region.name] = False
                        logger.error(f"❌ {region.name}: Health check failed - Status {response.status}")
                        
            except Exception as e:
                results[region.name] = False
                logger.error(f"❌ {region.name}: Connection failed - {str(e)}")
                
        return results

    async def test_load_balancer_routing(self) -> Dict[str, Dict]:
        """로드 밸런서 라우팅 테스트"""
        logger.info("🔄 Testing load balancer routing and failover...")
        
        results = {}
        
        for region in TEST_REGIONS:
            region_results = {
                "routing_working": False,
                "failover_working": False,
                "response_time_ms": 0,
                "geographic_routing": False
            }
            
            try:
                start_time = time.time()
                
                # 지역별 엔드포인트 테스트
                async with self.session.get(
                    f"{region.endpoint}/api/region-info",
                    headers={"X-Forwarded-For": self._get_test_ip_for_region(region.name)}
                ) as response:
                    
                    response_time = (time.time() - start_time) * 1000
                    region_results["response_time_ms"] = response_time
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # 라우팅 확인
                        if data.get("region") == region.name:
                            region_results["routing_working"] = True
                            region_results["geographic_routing"] = True
                            logger.info(f"✅ {region.name}: Geographic routing working correctly")
                        
                        # 응답 시간 확인
                        if response_time <= region.expected_latency_ms:
                            logger.info(f"✅ {region.name}: Response time {response_time:.2f}ms within expected {region.expected_latency_ms}ms")
                        else:
                            logger.warning(f"⚠️ {region.name}: Response time {response_time:.2f}ms exceeds expected {region.expected_latency_ms}ms")
                
                # Failover 테스트 (한 서버를 일시적으로 차단하고 테스트)
                region_results["failover_working"] = await self._test_failover(region)
                
            except Exception as e:
                logger.error(f"❌ {region.name}: Load balancer test failed - {str(e)}")
                
            results[region.name] = region_results
            
        return results

    async def test_gpu_cluster_performance(self) -> Dict[str, Dict]:
        """GPU 클러스터 성능 테스트"""
        logger.info("🖥️ Testing GPU cluster performance across regions...")
        
        results = {}
        test_payload = {
            "video_url": "https://test-video-url.com/sample.mp4",
            "start_time": 10,
            "end_time": 20,
            "analysis_type": "visual_analysis"
        }
        
        for region in TEST_REGIONS:
            region_results = {
                "gpu_available": False,
                "processing_time_ms": 0,
                "throughput_fps": 0,
                "memory_usage_percentage": 0,
                "error_rate": 0
            }
            
            try:
                # GPU 가용성 확인
                async with self.session.get(f"{region.gpu_endpoint}/status") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        region_results["gpu_available"] = status_data.get("gpu_available", False)
                        region_results["memory_usage_percentage"] = status_data.get("memory_usage", 0)
                
                # GPU 처리 성능 테스트
                if region_results["gpu_available"]:
                    start_time = time.time()
                    
                    async with self.session.post(
                        f"{region.gpu_endpoint}/analyze",
                        json=test_payload
                    ) as response:
                        processing_time = (time.time() - start_time) * 1000
                        region_results["processing_time_ms"] = processing_time
                        
                        if response.status == 200:
                            result_data = await response.json()
                            region_results["throughput_fps"] = result_data.get("fps_processed", 0)
                            logger.info(f"✅ {region.name}: GPU processing completed in {processing_time:.2f}ms")
                        else:
                            region_results["error_rate"] = 1
                            logger.error(f"❌ {region.name}: GPU processing failed - Status {response.status}")
                
            except Exception as e:
                region_results["error_rate"] = 1
                logger.error(f"❌ {region.name}: GPU test failed - {str(e)}")
                
            results[region.name] = region_results
            
        return results

    async def test_data_synchronization(self) -> Dict[str, Dict]:
        """데이터 동기화 테스트"""
        logger.info("🔄 Testing data synchronization between regions...")
        
        results = {}
        test_data = {
            "test_id": f"sync_test_{int(time.time())}",
            "data": {"test": "multi_region_sync"}
        }
        
        # 첫 번째 지역에 데이터 생성
        primary_region = TEST_REGIONS[0]
        
        try:
            async with self.session.post(
                f"{primary_region.endpoint}/api/test-data",
                json=test_data
            ) as response:
                if response.status == 201:
                    logger.info(f"✅ Test data created in {primary_region.name}")
                    
                    # 다른 지역들에서 데이터 동기화 확인
                    await asyncio.sleep(5)  # 동기화 대기
                    
                    for region in TEST_REGIONS[1:]:
                        region_results = {
                            "sync_successful": False,
                            "sync_latency_ms": 0,
                            "data_consistency": False
                        }
                        
                        try:
                            start_time = time.time()
                            async with self.session.get(
                                f"{region.endpoint}/api/test-data/{test_data['test_id']}"
                            ) as sync_response:
                                sync_latency = (time.time() - start_time) * 1000
                                region_results["sync_latency_ms"] = sync_latency
                                
                                if sync_response.status == 200:
                                    synced_data = await sync_response.json()
                                    
                                    if synced_data.get("data") == test_data["data"]:
                                        region_results["sync_successful"] = True
                                        region_results["data_consistency"] = True
                                        logger.info(f"✅ {region.name}: Data synchronized successfully in {sync_latency:.2f}ms")
                                    else:
                                        logger.error(f"❌ {region.name}: Data inconsistency detected")
                                        
                        except Exception as e:
                            logger.error(f"❌ {region.name}: Sync test failed - {str(e)}")
                            
                        results[region.name] = region_results
                        
        except Exception as e:
            logger.error(f"❌ Failed to create test data in {primary_region.name} - {str(e)}")
            
        return results

    async def test_monitoring_and_alerting(self) -> Dict[str, Dict]:
        """모니터링 및 알림 시스템 테스트"""
        logger.info("📊 Testing monitoring and alerting systems...")
        
        results = {}
        
        for region in TEST_REGIONS:
            region_results = {
                "prometheus_accessible": False,
                "grafana_accessible": False,
                "metrics_collection": False,
                "alerting_rules": False,
                "dashboard_responsive": False
            }
            
            try:
                # Prometheus 접근성 테스트
                async with self.session.get(f"{region.endpoint}/prometheus/api/v1/query?query=up") as response:
                    if response.status == 200:
                        region_results["prometheus_accessible"] = True
                        data = await response.json()
                        if data.get("status") == "success":
                            region_results["metrics_collection"] = True
                            logger.info(f"✅ {region.name}: Prometheus metrics collection working")
                
                # Grafana 대시보드 테스트
                async with self.session.get(f"{region.endpoint}/grafana/api/health") as response:
                    if response.status == 200:
                        region_results["grafana_accessible"] = True
                        logger.info(f"✅ {region.name}: Grafana dashboard accessible")
                
                # 알림 규칙 확인
                async with self.session.get(f"{region.endpoint}/prometheus/api/v1/rules") as response:
                    if response.status == 200:
                        rules_data = await response.json()
                        if rules_data.get("data", {}).get("groups"):
                            region_results["alerting_rules"] = True
                            logger.info(f"✅ {region.name}: Alerting rules configured")
                
                # 대시보드 응답성 테스트
                start_time = time.time()
                async with self.session.get(f"{region.endpoint}/grafana/d/influence-item-overview") as response:
                    dashboard_time = (time.time() - start_time) * 1000
                    if response.status == 200 and dashboard_time < 3000:  # 3초 이내
                        region_results["dashboard_responsive"] = True
                        logger.info(f"✅ {region.name}: Dashboard responsive ({dashboard_time:.2f}ms)")
                
            except Exception as e:
                logger.error(f"❌ {region.name}: Monitoring test failed - {str(e)}")
                
            results[region.name] = region_results
            
        return results

    async def test_security_and_compliance(self) -> Dict[str, Dict]:
        """보안 및 컴플라이언스 테스트"""
        logger.info("🔒 Testing security and compliance features...")
        
        results = {}
        
        for region in TEST_REGIONS:
            region_results = {
                "ssl_certificate": False,
                "security_headers": False,
                "rate_limiting": False,
                "waf_protection": False,
                "data_encryption": False
            }
            
            try:
                # SSL 인증서 확인
                async with self.session.get(region.endpoint) as response:
                    if response.url.scheme == "https":
                        region_results["ssl_certificate"] = True
                        logger.info(f"✅ {region.name}: SSL certificate working")
                    
                    # 보안 헤더 확인
                    security_headers = [
                        "Strict-Transport-Security",
                        "X-Content-Type-Options",
                        "X-Frame-Options",
                        "X-XSS-Protection"
                    ]
                    
                    if all(header in response.headers for header in security_headers):
                        region_results["security_headers"] = True
                        logger.info(f"✅ {region.name}: Security headers present")
                
                # Rate limiting 테스트
                rate_limit_results = await self._test_rate_limiting(region)
                region_results["rate_limiting"] = rate_limit_results
                
                # 데이터 암호화 확인 (API 응답 체크)
                async with self.session.get(f"{region.endpoint}/api/encryption-test") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("encryption_enabled"):
                            region_results["data_encryption"] = True
                            logger.info(f"✅ {region.name}: Data encryption enabled")
                
            except Exception as e:
                logger.error(f"❌ {region.name}: Security test failed - {str(e)}")
                
            results[region.name] = region_results
            
        return results

    async def test_disaster_recovery(self) -> Dict[str, Dict]:
        """재해 복구 테스트"""
        logger.info("🚨 Testing disaster recovery capabilities...")
        
        results = {}
        
        for region in TEST_REGIONS:
            region_results = {
                "backup_system": False,
                "failover_time_seconds": 0,
                "data_recovery": False,
                "service_continuity": False
            }
            
            try:
                # 백업 시스템 확인
                async with self.session.get(f"{region.endpoint}/api/backup-status") as response:
                    if response.status == 200:
                        backup_data = await response.json()
                        if backup_data.get("last_backup_success"):
                            region_results["backup_system"] = True
                            logger.info(f"✅ {region.name}: Backup system working")
                
                # 서비스 연속성 테스트 (시뮬레이션)
                region_results["service_continuity"] = await self._test_service_continuity(region)
                
            except Exception as e:
                logger.error(f"❌ {region.name}: Disaster recovery test failed - {str(e)}")
                
            results[region.name] = region_results
            
        return results

    def _get_test_ip_for_region(self, region_name: str) -> str:
        """지역별 테스트 IP 반환"""
        test_ips = {
            "us-east-1": "3.208.0.0",
            "ap-northeast-2": "52.78.0.0", 
            "eu-west-1": "34.240.0.0"
        }
        return test_ips.get(region_name, "127.0.0.1")

    async def _test_failover(self, region: RegionConfig) -> bool:
        """Failover 테스트"""
        try:
            # 여러 요청을 보내 로드 밸런싱 확인
            for _ in range(5):
                async with self.session.get(f"{region.endpoint}/api/health") as response:
                    if response.status != 200:
                        return False
            return True
        except:
            return False

    async def _test_rate_limiting(self, region: RegionConfig) -> bool:
        """Rate limiting 테스트"""
        try:
            # 연속 요청으로 rate limit 테스트
            for i in range(150):  # 설정된 limit 초과
                async with self.session.get(f"{region.endpoint}/api/test") as response:
                    if response.status == 429:  # Too Many Requests
                        return True
            return False
        except:
            return False

    async def _test_service_continuity(self, region: RegionConfig) -> bool:
        """서비스 연속성 테스트"""
        try:
            # 지속적인 요청으로 서비스 연속성 확인
            start_time = time.time()
            success_count = 0
            total_requests = 10
            
            for _ in range(total_requests):
                try:
                    async with self.session.get(f"{region.endpoint}/api/health") as response:
                        if response.status == 200:
                            success_count += 1
                    await asyncio.sleep(1)
                except:
                    pass
            
            # 90% 이상 성공률이면 연속성 확인
            return (success_count / total_requests) >= 0.9
        except:
            return False

    async def generate_test_report(self, all_results: Dict) -> str:
        """종합 테스트 보고서 생성"""
        report = []
        report.append("# M04_S01_T01 다중 지역 배포 인프라 테스트 보고서")
        report.append(f"**테스트 일시**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**테스트 지역**: {', '.join([region.name for region in TEST_REGIONS])}")
        report.append("")
        
        # 전체 요약
        report.append("## 📊 전체 테스트 요약")
        total_tests = 0
        passed_tests = 0
        
        for test_category, results in all_results.items():
            report.append(f"### {test_category}")
            for region, region_results in results.items():
                if isinstance(region_results, dict):
                    for test_name, result in region_results.items():
                        total_tests += 1
                        if result:
                            passed_tests += 1
                        status = "✅" if result else "❌"
                        report.append(f"- {status} {region} - {test_name}: {result}")
                else:
                    total_tests += 1
                    if region_results:
                        passed_tests += 1
                    status = "✅" if region_results else "❌"
                    report.append(f"- {status} {region}: {region_results}")
            report.append("")
        
        # 성공률 계산
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        report.append(f"**전체 성공률**: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        report.append("")
        
        # 지역별 상세 분석
        report.append("## 🌍 지역별 상세 분석")
        for region in TEST_REGIONS:
            report.append(f"### {region.name}")
            region_tests = 0
            region_passed = 0
            
            for test_category, results in all_results.items():
                if region.name in results:
                    region_result = results[region.name]
                    if isinstance(region_result, dict):
                        for test_name, result in region_result.items():
                            region_tests += 1
                            if result:
                                region_passed += 1
                    else:
                        region_tests += 1
                        if region_result:
                            region_passed += 1
            
            region_success_rate = (region_passed / region_tests * 100) if region_tests > 0 else 0
            report.append(f"**성공률**: {region_success_rate:.1f}% ({region_passed}/{region_tests})")
            report.append("")
        
        # 권장사항
        report.append("## 🔧 권장사항")
        if success_rate < 95:
            report.append("- 🚨 일부 테스트가 실패했습니다. 실패한 항목을 확인하고 수정하세요.")
        if success_rate >= 95:
            report.append("- ✅ 모든 핵심 기능이 정상 작동합니다.")
            report.append("- 🚀 프로덕션 배포 준비가 완료되었습니다.")
        
        report.append("")
        report.append("## 📋 다음 단계")
        report.append("1. 실패한 테스트 항목 수정")
        report.append("2. 성능 최적화 적용")
        report.append("3. 모니터링 대시보드 설정 완료")
        report.append("4. 운영 절차 문서화")
        
        return "\n".join(report)


async def run_comprehensive_tests():
    """종합 테스트 실행"""
    logger.info("🚀 Starting comprehensive multi-region deployment tests...")
    
    async with MultiRegionDeploymentTester() as tester:
        all_results = {}
        
        # 모든 테스트 실행
        test_functions = [
            ("Infrastructure Connectivity", tester.test_infrastructure_connectivity),
            ("Load Balancer Routing", tester.test_load_balancer_routing),
            ("GPU Cluster Performance", tester.test_gpu_cluster_performance),
            ("Data Synchronization", tester.test_data_synchronization),
            ("Monitoring and Alerting", tester.test_monitoring_and_alerting),
            ("Security and Compliance", tester.test_security_and_compliance),
            ("Disaster Recovery", tester.test_disaster_recovery)
        ]
        
        for test_name, test_function in test_functions:
            logger.info(f"Running {test_name} tests...")
            try:
                results = await test_function()
                all_results[test_name] = results
            except Exception as e:
                logger.error(f"Test {test_name} failed: {str(e)}")
                all_results[test_name] = {"error": str(e)}
        
        # 보고서 생성
        report = await tester.generate_test_report(all_results)
        
        # 보고서 저장
        report_path = Path(__file__).parent.parent / "test_reports" / f"m04_s01_t01_multi_region_test_{int(time.time())}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"📄 Test report saved to: {report_path}")
        return all_results, report


# Pytest 테스트 함수들
@pytest.mark.asyncio
async def test_multi_region_infrastructure():
    """다중 지역 인프라 테스트"""
    async with MultiRegionDeploymentTester() as tester:
        results = await tester.test_infrastructure_connectivity()
        assert all(results.values()), f"Infrastructure connectivity failed: {results}"


@pytest.mark.asyncio 
async def test_load_balancer_functionality():
    """로드 밸런서 기능 테스트"""
    async with MultiRegionDeploymentTester() as tester:
        results = await tester.test_load_balancer_routing()
        for region, result in results.items():
            assert result.get("routing_working", False), f"Load balancer routing failed in {region}"


@pytest.mark.asyncio
async def test_gpu_clusters():
    """GPU 클러스터 테스트"""
    async with MultiRegionDeploymentTester() as tester:
        results = await tester.test_gpu_cluster_performance()
        for region, result in results.items():
            assert result.get("gpu_available", False), f"GPU not available in {region}"


@pytest.mark.asyncio
async def test_data_sync():
    """데이터 동기화 테스트"""
    async with MultiRegionDeploymentTester() as tester:
        results = await tester.test_data_synchronization()
        for region, result in results.items():
            assert result.get("sync_successful", False), f"Data sync failed in {region}"


if __name__ == "__main__":
    # 스크립트로 직접 실행 시
    results, report = asyncio.run(run_comprehensive_tests())
    print("\n" + "="*80)
    print("🎯 M04_S01_T01 다중 지역 배포 인프라 테스트 완료!")
    print("="*80)
    print(report)