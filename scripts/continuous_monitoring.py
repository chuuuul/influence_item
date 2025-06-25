#!/usr/bin/env python3
"""
지속적 시스템 모니터링 스크립트
10분마다 시스템 상태를 모니터링하고 문제 발생 시 알림
"""

import sys
import time
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.monitoring.system_monitor import SystemMonitor
from src.monitoring.performance_benchmarker import PerformanceBenchmarker

class ContinuousMonitoring:
    """지속적 모니터링 클래스"""
    
    def __init__(self):
        self.project_root = project_root
        self.system_monitor = SystemMonitor()
        self.performance_benchmarker = PerformanceBenchmarker()
        self.monitoring_active = True
        self.last_benchmark_time = None
        self.setup_logging()
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "continuous_monitoring.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def should_run_benchmark(self) -> bool:
        """벤치마크 실행 여부 결정 (30분마다)"""
        if self.last_benchmark_time is None:
            return True
        
        time_since_last = datetime.now() - self.last_benchmark_time
        return time_since_last >= timedelta(minutes=30)
    
    async def monitoring_cycle(self):
        """모니터링 사이클 실행"""
        try:
            self.logger.info("모니터링 사이클 시작")
            
            # 시스템 모니터링 실행
            report = self.system_monitor.monitor_cycle()
            
            # 알림 확인 및 출력
            if report.get('alerts'):
                self.logger.warning("🚨 시스템 알림 발생:")
                for alert in report['alerts']:
                    self.logger.warning(f"  {alert}")
                    print(f"  {alert}")
            
            # 상태 출력
            print(f"\n=== 모니터링 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
            print(f"전체 상태: {report['overall_status']}")
            
            # 시스템 리소스
            health = report['system_health']
            print(f"📊 시스템: CPU {health['cpu_percent']}%, 메모리 {health['memory_percent']}%, 디스크 {health['disk_percent']}%")
            
            # 서비스 상태
            service = report['service_health']
            streamlit_status = "🟢" if "🟢" in service['streamlit_status'] else "🔴"
            api_status = "🟢" if "🟢" in service['api_server_status'] else "🔴"
            db_status = "🟢" if "🟢" in service['database_status'] else "🔴"
            print(f"🌐 서비스: Streamlit {streamlit_status}, API {api_status}, DB {db_status}")
            
            # 성능 벤치마크 (30분마다)
            if self.should_run_benchmark():
                self.logger.info("성능 벤치마크 실행")
                print("🚀 성능 벤치마크 실행 중...")
                
                try:
                    benchmark_report = await self.performance_benchmarker.run_full_benchmark_suite()
                    
                    print("📈 벤치마크 완료:")
                    for test_name, summary in benchmark_report['performance_summary'].items():
                        print(f"  {test_name}: {summary}")
                    
                    # 권장사항이 있으면 출력
                    if benchmark_report['recommendations'] and benchmark_report['recommendations'][0] != "✅ 모든 성능 지표가 양호합니다":
                        print("💡 성능 개선 권장사항:")
                        for rec in benchmark_report['recommendations']:
                            print(f"  {rec}")
                    
                    self.last_benchmark_time = datetime.now()
                    
                except Exception as e:
                    self.logger.error(f"벤치마크 실행 오류: {e}")
            
            print("=" * 80)
            
        except Exception as e:
            self.logger.error(f"모니터링 사이클 오류: {e}")
    
    async def start_continuous_monitoring(self, interval_minutes: int = 10):
        """지속적 모니터링 시작"""
        self.logger.info(f"지속적 모니터링 시작 (간격: {interval_minutes}분)")
        print(f"🔍 지속적 시스템 모니터링 시작 (간격: {interval_minutes}분)")
        print("Ctrl+C로 중지하세요\n")
        
        try:
            while self.monitoring_active:
                await self.monitoring_cycle()
                
                # 다음 모니터링까지 대기
                self.logger.info(f"다음 모니터링까지 {interval_minutes}분 대기...")
                await asyncio.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 모니터링 중지")
            print("\n🛑 모니터링을 중지합니다...")
            self.monitoring_active = False
        except Exception as e:
            self.logger.error(f"모니터링 중 오류 발생: {e}")
            print(f"오류 발생: {e}")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        self.system_monitor.stop_monitoring()
        self.logger.info("모니터링 중지 완료")

async def main():
    """메인 함수"""
    continuous_monitor = ContinuousMonitoring()
    
    try:
        await continuous_monitor.start_continuous_monitoring(interval_minutes=10)
    except Exception as e:
        print(f"모니터링 시작 오류: {e}")
    finally:
        continuous_monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())