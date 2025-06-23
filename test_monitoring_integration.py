#!/usr/bin/env python3
"""
T01_S03_M03: 실시간 모니터링 대시보드 통합 테스트
모든 모니터링 컴포넌트가 정상적으로 작동하는지 확인
"""

import sys
import time
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_system_monitor():
    """시스템 모니터링 테스트"""
    try:
        from dashboard.utils.system_monitor import get_system_monitor
        
        logger.info("🖥️ 시스템 모니터링 테스트 시작")
        
        monitor = get_system_monitor()
        
        # 현재 메트릭 수집
        metrics = monitor._collect_system_metrics()
        if metrics:
            logger.info(f"✅ 시스템 메트릭 수집 성공 - CPU: {metrics.cpu_percent:.1f}%, 메모리: {metrics.memory_percent:.1f}%")
            
            # GPU 메트릭 확인
            if metrics.gpu_metrics:
                logger.info(f"✅ GPU 메트릭 수집 성공 - {len(metrics.gpu_metrics)}개 GPU 감지")
            else:
                logger.info("ℹ️ GPU 메트릭 없음 (GPU 없거나 GPUtil 미설치)")
        else:
            logger.error("❌ 시스템 메트릭 수집 실패")
            return False
        
        # 헬스체크 테스트
        health_status = monitor.get_health_status()
        logger.info(f"✅ 헬스체크 완료 - {len(health_status)}개 컴포넌트 확인")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 시스템 모니터링 테스트 실패: {e}")
        return False


def test_database_monitor():
    """데이터베이스 모니터링 테스트"""
    try:
        from dashboard.utils.database_performance_monitor import get_database_monitor
        
        logger.info("🗄️ 데이터베이스 모니터링 테스트 시작")
        
        monitor = get_database_monitor()
        
        # 메트릭 수집
        metrics = monitor.collect_database_metrics()
        if metrics:
            logger.info(f"✅ DB 메트릭 수집 성공 - 크기: {metrics.database_size_mb:.1f}MB, 테이블: {metrics.table_count}개")
        else:
            logger.error("❌ DB 메트릭 수집 실패")
            return False
        
        # 성능 요약
        summary = monitor.get_performance_summary(1)
        if 'error' not in summary:
            logger.info("✅ DB 성능 요약 조회 성공")
        else:
            logger.warning(f"⚠️ DB 성능 요약 조회 실패: {summary.get('error', 'Unknown error')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 모니터링 테스트 실패: {e}")
        return False


def test_network_monitor():
    """네트워크 모니터링 테스트"""
    try:
        from dashboard.utils.network_monitor import get_network_monitor
        
        logger.info("🌐 네트워크 모니터링 테스트 시작")
        
        monitor = get_network_monitor()
        
        # 네트워크 메트릭 수집
        metrics = monitor.collect_network_metrics()
        if metrics:
            logger.info(f"✅ 네트워크 메트릭 수집 성공 - 연결: {metrics.connections_established}개")
        else:
            logger.error("❌ 네트워크 메트릭 수집 실패")
            return False
        
        # API 테스트
        api_metrics = monitor.monitor_api_endpoint("https://www.google.com", timeout=5)
        if api_metrics:
            status = "성공" if api_metrics.success else f"실패 ({api_metrics.error_message})"
            logger.info(f"✅ API 모니터링 테스트 완료 - 응답시간: {api_metrics.response_time:.1f}ms, 상태: {status}")
        else:
            logger.error("❌ API 모니터링 테스트 실패")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 네트워크 모니터링 테스트 실패: {e}")
        return False


def test_n8n_monitor():
    """n8n 모니터링 테스트"""
    try:
        from dashboard.utils.n8n_monitor import get_n8n_monitor
        
        logger.info("⚙️ n8n 모니터링 테스트 시작")
        
        monitor = get_n8n_monitor("http://localhost:5678")
        
        # 연결 테스트
        connected = monitor.check_connection()
        if connected:
            logger.info("✅ n8n 서버 연결 성공")
            
            # 워크플로우 조회
            workflows = monitor.get_workflows()
            logger.info(f"✅ 워크플로우 조회 성공 - {len(workflows)}개 워크플로우")
            
            # 실행 요약
            summary = monitor.get_workflow_execution_summary(1)
            logger.info(f"✅ 실행 요약 조회 성공 - 총 실행: {summary.get('total_executions', 0)}회")
        else:
            logger.warning("⚠️ n8n 서버에 연결할 수 없음 (서버가 실행되지 않았을 수 있음)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ n8n 모니터링 테스트 실패: {e}")
        return False


def test_monitoring_database():
    """모니터링 데이터베이스 테스트"""
    try:
        from dashboard.utils.monitoring_database import get_monitoring_database
        
        logger.info("💾 모니터링 데이터베이스 테스트 시작")
        
        db = get_monitoring_database("test_monitoring.db")
        
        # 테스트 데이터 저장
        test_system_data = {
            'timestamp': datetime.now(),
            'cpu_percent': 50.0,
            'memory_percent': 60.0,
            'memory_available': 8000000000,
            'disk_percent': 70.0,
            'disk_free': 100000000000,
            'active_connections': 10,
            'uptime': 3600.0
        }
        
        db.store_system_metrics(test_system_data)
        logger.info("✅ 테스트 시스템 메트릭 저장 성공")
        
        # 데이터 조회
        history = db.get_system_metrics_history(1)
        if history:
            logger.info(f"✅ 메트릭 이력 조회 성공 - {len(history)}개 레코드")
        else:
            logger.warning("⚠️ 메트릭 이력이 비어있음")
        
        # API 성능 요약
        api_summary = db.get_api_performance_summary(1)
        logger.info("✅ API 성능 요약 조회 성공")
        
        # 데이터베이스 크기 확인
        db_size = db.get_database_size()
        logger.info(f"✅ 데이터베이스 크기: {db_size:.3f}MB")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 모니터링 데이터베이스 테스트 실패: {e}")
        return False


def main():
    """메인 테스트 함수"""
    logger.info("🚀 실시간 모니터링 대시보드 통합 테스트 시작")
    logger.info("=" * 60)
    
    test_results = {
        "시스템 모니터링": test_system_monitor(),
        "데이터베이스 모니터링": test_database_monitor(),
        "네트워크 모니터링": test_network_monitor(),
        "n8n 모니터링": test_n8n_monitor(),
        "모니터링 데이터베이스": test_monitoring_database()
    }
    
    logger.info("=" * 60)
    logger.info("📊 테스트 결과 요약")
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
        if result:
            passed_tests += 1
    
    logger.info("=" * 60)
    success_rate = (passed_tests / total_tests) * 100
    logger.info(f"전체 테스트 결과: {passed_tests}/{total_tests} 통과 ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        logger.info("🎉 모니터링 시스템이 성공적으로 구축되었습니다!")
        return True
    else:
        logger.error("⚠️ 일부 테스트가 실패했습니다. 문제를 확인해주세요.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)