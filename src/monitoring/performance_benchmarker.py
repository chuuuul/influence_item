#!/usr/bin/env python3
"""
성능 벤치마크 도구
AI 파이프라인, 데이터 처리, API 응답 시간 등을 벤치마크하여 성능 최적화 지점을 식별
"""

import time
import asyncio
import aiohttp
import requests
import json
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import sqlite3
import subprocess
import logging

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

@dataclass
class BenchmarkResult:
    """벤치마크 결과 데이터 클래스"""
    test_name: str
    timestamp: str
    average_time: float
    min_time: float
    max_time: float
    median_time: float
    success_rate: float
    throughput: float  # requests per second
    details: Dict[str, Any]

class PerformanceBenchmarker:
    """성능 벤치마크 클래스"""
    
    def __init__(self):
        self.project_root = project_root
        self.results = []
        self.setup_logging()
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "performance_benchmark.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    async def benchmark_api_endpoints(self, iterations: int = 10) -> BenchmarkResult:
        """API 엔드포인트 성능 벤치마크"""
        self.logger.info(f"API 엔드포인트 벤치마크 시작 ({iterations}회 반복)")
        
        endpoints = [
            "http://localhost:8501",  # Streamlit 대시보드
            "http://localhost:8000/docs",  # API 서버 문서
        ]
        
        times = []
        success_count = 0
        start_total = time.time()
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                for endpoint in endpoints:
                    try:
                        start_time = time.time()
                        async with session.get(endpoint, timeout=10) as response:
                            await response.text()
                            end_time = time.time()
                            
                        response_time = end_time - start_time
                        times.append(response_time)
                        
                        if response.status == 200:
                            success_count += 1
                            
                    except Exception as e:
                        self.logger.warning(f"API 요청 실패 {endpoint}: {e}")
                        times.append(10.0)  # 타임아웃값으로 설정
        
        total_time = time.time() - start_total
        total_requests = iterations * len(endpoints)
        
        if times:
            return BenchmarkResult(
                test_name="API Endpoints",
                timestamp=datetime.now().isoformat(),
                average_time=round(statistics.mean(times), 3),
                min_time=round(min(times), 3),
                max_time=round(max(times), 3),
                median_time=round(statistics.median(times), 3),
                success_rate=round((success_count / total_requests) * 100, 2),
                throughput=round(total_requests / total_time, 2),
                details={
                    "endpoints_tested": endpoints,
                    "total_requests": total_requests,
                    "successful_requests": success_count,
                    "total_time": round(total_time, 3)
                }
            )
        else:
            return None

    def benchmark_database_operations(self, iterations: int = 100) -> BenchmarkResult:
        """데이터베이스 작업 성능 벤치마크"""
        self.logger.info(f"데이터베이스 성능 벤치마크 시작 ({iterations}회 반복)")
        
        db_path = self.project_root / "influence_item.db"
        if not db_path.exists():
            self.logger.error("데이터베이스 파일이 존재하지 않습니다")
            return None
        
        times = []
        success_count = 0
        start_total = time.time()
        
        queries = [
            "SELECT COUNT(*) FROM rss_channels",
            "SELECT COUNT(*) FROM candidates",
            "SELECT COUNT(*) FROM scraped_videos",
            "SELECT * FROM rss_channels LIMIT 10",
            "SELECT * FROM candidates LIMIT 10",
        ]
        
        for i in range(iterations):
            for query in queries:
                try:
                    start_time = time.time()
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute(query)
                        cursor.fetchall()
                    end_time = time.time()
                    
                    response_time = end_time - start_time
                    times.append(response_time)
                    success_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"데이터베이스 쿼리 실패 {query}: {e}")
                    times.append(1.0)  # 기본값
        
        total_time = time.time() - start_total
        total_queries = iterations * len(queries)
        
        if times:
            return BenchmarkResult(
                test_name="Database Operations",
                timestamp=datetime.now().isoformat(),
                average_time=round(statistics.mean(times), 3),
                min_time=round(min(times), 3),
                max_time=round(max(times), 3),
                median_time=round(statistics.median(times), 3),
                success_rate=round((success_count / total_queries) * 100, 2),
                throughput=round(total_queries / total_time, 2),
                details={
                    "queries_tested": queries,
                    "total_queries": total_queries,
                    "successful_queries": success_count,
                    "total_time": round(total_time, 3)
                }
            )
        else:
            return None

    def benchmark_file_operations(self, iterations: int = 50) -> BenchmarkResult:
        """파일 I/O 성능 벤치마크"""
        self.logger.info(f"파일 I/O 성능 벤치마크 시작 ({iterations}회 반복)")
        
        times = []
        success_count = 0
        start_total = time.time()
        
        # 테스트 파일 생성
        test_dir = self.project_root / "temp_benchmark"
        test_dir.mkdir(exist_ok=True)
        
        try:
            for i in range(iterations):
                try:
                    # 파일 쓰기 벤치마크
                    start_time = time.time()
                    test_file = test_dir / f"test_{i}.txt"
                    test_data = "테스트 데이터 " * 1000  # 약 13KB
                    
                    with open(test_file, 'w', encoding='utf-8') as f:
                        f.write(test_data)
                    
                    # 파일 읽기 벤치마크
                    with open(test_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 파일 삭제
                    test_file.unlink()
                    
                    end_time = time.time()
                    response_time = end_time - start_time
                    times.append(response_time)
                    success_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"파일 I/O 작업 실패 {i}: {e}")
                    times.append(0.1)  # 기본값
            
            # 테스트 디렉토리 정리
            if test_dir.exists():
                import shutil
                shutil.rmtree(test_dir)
        
        except Exception as e:
            self.logger.error(f"파일 I/O 벤치마크 오류: {e}")
            return None
        
        total_time = time.time() - start_total
        
        if times:
            return BenchmarkResult(
                test_name="File I/O Operations",
                timestamp=datetime.now().isoformat(),
                average_time=round(statistics.mean(times), 3),
                min_time=round(min(times), 3),
                max_time=round(max(times), 3),
                median_time=round(statistics.median(times), 3),
                success_rate=round((success_count / iterations) * 100, 2),
                throughput=round(iterations / total_time, 2),
                details={
                    "operations_tested": ["write", "read", "delete"],
                    "total_operations": iterations,
                    "successful_operations": success_count,
                    "total_time": round(total_time, 3),
                    "data_size_kb": 13
                }
            )
        else:
            return None

    def benchmark_cpu_intensive_tasks(self, iterations: int = 10) -> BenchmarkResult:
        """CPU 집약적 작업 성능 벤치마크"""
        self.logger.info(f"CPU 집약적 작업 벤치마크 시작 ({iterations}회 반복)")
        
        times = []
        success_count = 0
        start_total = time.time()
        
        def cpu_intensive_task():
            """CPU 집약적 계산 작업"""
            result = 0
            for i in range(100000):
                result += i ** 0.5
            return result
        
        for i in range(iterations):
            try:
                start_time = time.time()
                result = cpu_intensive_task()
                end_time = time.time()
                
                response_time = end_time - start_time
                times.append(response_time)
                success_count += 1
                
            except Exception as e:
                self.logger.warning(f"CPU 집약적 작업 실패 {i}: {e}")
                times.append(1.0)  # 기본값
        
        total_time = time.time() - start_total
        
        if times:
            return BenchmarkResult(
                test_name="CPU Intensive Tasks",
                timestamp=datetime.now().isoformat(),
                average_time=round(statistics.mean(times), 3),
                min_time=round(min(times), 3),
                max_time=round(max(times), 3),
                median_time=round(statistics.median(times), 3),
                success_rate=round((success_count / iterations) * 100, 2),
                throughput=round(iterations / total_time, 2),
                details={
                    "task_type": "mathematical_computation",
                    "operations_per_task": 100000,
                    "total_tasks": iterations,
                    "successful_tasks": success_count,
                    "total_time": round(total_time, 3)
                }
            )
        else:
            return None

    def benchmark_memory_operations(self, iterations: int = 20) -> BenchmarkResult:
        """메모리 작업 성능 벤치마크"""
        self.logger.info(f"메모리 작업 성능 벤치마크 시작 ({iterations}회 반복)")
        
        times = []
        success_count = 0
        start_total = time.time()
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                # 큰 리스트 생성 및 조작
                large_list = list(range(100000))
                large_list.sort(reverse=True)
                filtered_list = [x for x in large_list if x % 2 == 0]
                
                # 딕셔너리 생성 및 조작
                large_dict = {str(i): i for i in range(10000)}
                sorted_keys = sorted(large_dict.keys())
                
                # 메모리 해제
                del large_list, filtered_list, large_dict, sorted_keys
                
                end_time = time.time()
                response_time = end_time - start_time
                times.append(response_time)
                success_count += 1
                
            except Exception as e:
                self.logger.warning(f"메모리 작업 실패 {i}: {e}")
                times.append(1.0)  # 기본값
        
        total_time = time.time() - start_total
        
        if times:
            return BenchmarkResult(
                test_name="Memory Operations",
                timestamp=datetime.now().isoformat(),
                average_time=round(statistics.mean(times), 3),
                min_time=round(min(times), 3),
                max_time=round(max(times), 3),
                median_time=round(statistics.median(times), 3),
                success_rate=round((success_count / iterations) * 100, 2),
                throughput=round(iterations / total_time, 2),
                details={
                    "operations_tested": ["list_creation", "sorting", "filtering", "dict_creation"],
                    "list_size": 100000,
                    "dict_size": 10000,
                    "total_operations": iterations,
                    "successful_operations": success_count,
                    "total_time": round(total_time, 3)
                }
            )
        else:
            return None

    async def run_full_benchmark_suite(self) -> Dict[str, Any]:
        """전체 벤치마크 스위트 실행"""
        self.logger.info("전체 성능 벤치마크 스위트 시작")
        
        start_time = time.time()
        benchmark_results = {}
        
        # API 엔드포인트 벤치마크
        try:
            api_result = await self.benchmark_api_endpoints(iterations=5)
            if api_result:
                benchmark_results["api_endpoints"] = asdict(api_result)
                self.results.append(api_result)
        except Exception as e:
            self.logger.error(f"API 벤치마크 실패: {e}")
        
        # 데이터베이스 작업 벤치마크
        try:
            db_result = self.benchmark_database_operations(iterations=50)
            if db_result:
                benchmark_results["database_operations"] = asdict(db_result)
                self.results.append(db_result)
        except Exception as e:
            self.logger.error(f"데이터베이스 벤치마크 실패: {e}")
        
        # 파일 I/O 벤치마크
        try:
            file_result = self.benchmark_file_operations(iterations=20)
            if file_result:
                benchmark_results["file_operations"] = asdict(file_result)
                self.results.append(file_result)
        except Exception as e:
            self.logger.error(f"파일 I/O 벤치마크 실패: {e}")
        
        # CPU 집약적 작업 벤치마크
        try:
            cpu_result = self.benchmark_cpu_intensive_tasks(iterations=5)
            if cpu_result:
                benchmark_results["cpu_intensive"] = asdict(cpu_result)
                self.results.append(cpu_result)
        except Exception as e:
            self.logger.error(f"CPU 벤치마크 실패: {e}")
        
        # 메모리 작업 벤치마크
        try:
            memory_result = self.benchmark_memory_operations(iterations=10)
            if memory_result:
                benchmark_results["memory_operations"] = asdict(memory_result)
                self.results.append(memory_result)
        except Exception as e:
            self.logger.error(f"메모리 벤치마크 실패: {e}")
        
        total_time = time.time() - start_time
        
        # 종합 리포트 생성
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_benchmark_time": round(total_time, 3),
            "benchmarks_completed": len(benchmark_results),
            "results": benchmark_results,
            "performance_summary": self.generate_performance_summary(benchmark_results),
            "recommendations": self.generate_recommendations(benchmark_results)
        }
        
        # 결과를 파일로 저장
        self.save_benchmark_results(report)
        
        return report

    def generate_performance_summary(self, results: Dict[str, Any]) -> Dict[str, str]:
        """성능 요약 생성"""
        summary = {}
        
        for test_name, result in results.items():
            avg_time = result.get('average_time', 0)
            success_rate = result.get('success_rate', 0)
            throughput = result.get('throughput', 0)
            
            # 성능 등급 결정
            if test_name == "api_endpoints":
                if avg_time < 0.1 and success_rate > 95:
                    grade = "🟢 우수"
                elif avg_time < 0.5 and success_rate > 90:
                    grade = "🟡 양호"
                else:
                    grade = "🔴 개선 필요"
            elif test_name == "database_operations":
                if avg_time < 0.01 and success_rate > 98:
                    grade = "🟢 우수"
                elif avg_time < 0.05 and success_rate > 95:
                    grade = "🟡 양호"
                else:
                    grade = "🔴 개선 필요"
            else:
                if success_rate > 95:
                    grade = "🟢 우수"
                elif success_rate > 85:
                    grade = "🟡 양호"
                else:
                    grade = "🔴 개선 필요"
            
            summary[test_name] = f"{grade} (평균: {avg_time}초, 성공률: {success_rate}%, 처리량: {throughput}/초)"
        
        return summary

    def generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """성능 개선 권장사항 생성"""
        recommendations = []
        
        for test_name, result in results.items():
            avg_time = result.get('average_time', 0)
            success_rate = result.get('success_rate', 0)
            max_time = result.get('max_time', 0)
            
            if test_name == "api_endpoints":
                if avg_time > 0.5:
                    recommendations.append("🔧 API 응답 시간 개선: 캐싱, 데이터베이스 인덱스 최적화 검토")
                if success_rate < 95:
                    recommendations.append("🔧 API 안정성 개선: 에러 핸들링 및 재시도 로직 강화")
                if max_time > 2.0:
                    recommendations.append("🔧 API 타임아웃 최적화: 느린 요청 원인 분석 필요")
            
            elif test_name == "database_operations":
                if avg_time > 0.05:
                    recommendations.append("🔧 데이터베이스 성능 개선: 인덱스 추가, 쿼리 최적화 검토")
                if success_rate < 98:
                    recommendations.append("🔧 데이터베이스 안정성 개선: 연결 풀링, 트랜잭션 최적화")
            
            elif test_name == "file_operations":
                if avg_time > 0.1:
                    recommendations.append("🔧 파일 I/O 성능 개선: SSD 사용, 비동기 I/O 적용 검토")
            
            elif test_name == "cpu_intensive":
                if avg_time > 0.5:
                    recommendations.append("🔧 CPU 성능 개선: 멀티프로세싱, 알고리즘 최적화 검토")
            
            elif test_name == "memory_operations":
                if avg_time > 0.5:
                    recommendations.append("🔧 메모리 사용 최적화: 제너레이터 사용, 메모리 효율적 자료구조 검토")
        
        if not recommendations:
            recommendations.append("✅ 모든 성능 지표가 양호합니다")
        
        return recommendations

    def save_benchmark_results(self, report: Dict[str, Any]):
        """벤치마크 결과를 파일로 저장"""
        try:
            benchmark_dir = self.project_root / "monitoring_data"
            benchmark_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            with open(benchmark_dir / f"benchmark_report_{timestamp}.json", 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"벤치마크 결과 저장 완료: benchmark_report_{timestamp}.json")
                
        except Exception as e:
            self.logger.error(f"벤치마크 결과 저장 오류: {e}")

async def main():
    """메인 함수"""
    benchmarker = PerformanceBenchmarker()
    
    print("🚀 성능 벤치마크 스위트 시작...")
    print("이 작업은 몇 분 소요될 수 있습니다...")
    
    try:
        report = await benchmarker.run_full_benchmark_suite()
        
        print(f"\n=== 성능 벤치마크 리포트 ===")
        print(f"실행 시간: {report['total_benchmark_time']}초")
        print(f"완료된 벤치마크: {report['benchmarks_completed']}개")
        
        print(f"\n📊 성능 요약:")
        for test_name, summary in report['performance_summary'].items():
            print(f"  {test_name}: {summary}")
        
        print(f"\n💡 권장사항:")
        for recommendation in report['recommendations']:
            print(f"  {recommendation}")
        
        print(f"\n자세한 결과는 monitoring_data/ 폴더의 JSON 파일을 확인하세요.")
        
    except Exception as e:
        print(f"벤치마크 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())