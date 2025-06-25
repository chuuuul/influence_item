#!/usr/bin/env python3
"""
비용 최적화 자동화 시스템

API 사용량 자동 조절, 리소스 스케일링, 비용 알림, 효율성 분석
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

import requests
import aiohttp
from src.notifications.alert_manager import send_warning_alert, send_critical_alert, send_info_alert
from src.config.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CostLevel(Enum):
    """비용 레벨"""
    OPTIMAL = "optimal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class ResourceType(Enum):
    """리소스 타입"""
    API_CALLS = "api_calls"
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"

@dataclass
class CostAlert:
    """비용 알림 데이터 클래스"""
    resource_type: ResourceType
    current_cost: float
    budget_limit: float
    usage_percentage: float
    level: CostLevel
    timestamp: datetime
    recommendations: List[str]
    auto_actions: List[str] = None
    
    def __post_init__(self):
        if self.auto_actions is None:
            self.auto_actions = []

@dataclass
class APIUsageMetrics:
    """API 사용량 메트릭"""
    service_name: str
    requests_count: int
    cost_per_request: float
    total_cost: float
    quota_limit: int
    quota_used: int
    timestamp: datetime
    
    @property
    def quota_percentage(self) -> float:
        return (self.quota_used / self.quota_limit * 100) if self.quota_limit > 0 else 0

@dataclass
class ResourceMetrics:
    """리소스 메트릭"""
    resource_type: ResourceType
    current_usage: float
    capacity: float
    cost_per_unit: float
    efficiency_score: float
    timestamp: datetime
    
    @property
    def usage_percentage(self) -> float:
        return (self.current_usage / self.capacity * 100) if self.capacity > 0 else 0

class APIUsageManager:
    """API 사용량 관리자"""
    
    def __init__(self):
        self.usage_file = Path("data/api_usage.json")
        self.usage_file.parent.mkdir(exist_ok=True)
        
        # API 비용 정보 (월간 기준)
        self.api_costs = {
            "google_api": {
                "youtube_data_v3": 0.002,  # per 1K requests
                "gemini_pro": 0.0005,      # per 1K tokens
                "sheets_api": 0.001        # per 100 requests
            },
            "coupang_partners": {
                "product_search": 0.0,     # 무료
                "link_generation": 0.0     # 무료
            }
        }
        
        # 일일 할당량
        self.daily_quotas = {
            "youtube_data_v3": Config.YOUTUBE_API_DAILY_QUOTA,
            "gemini_pro": 50000,  # 토큰 기준
            "sheets_api": 10000   # 요청 기준
        }
    
    def load_usage_data(self) -> Dict[str, Any]:
        """사용량 데이터 로드"""
        if not self.usage_file.exists():
            return {"daily_usage": {}, "monthly_usage": {}}
        
        try:
            with open(self.usage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"사용량 데이터 로드 실패: {e}")
            return {"daily_usage": {}, "monthly_usage": {}}
    
    def save_usage_data(self, data: Dict[str, Any]):
        """사용량 데이터 저장"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"사용량 데이터 저장 실패: {e}")
    
    def record_api_usage(self, service: str, api_type: str, requests: int = 1, tokens: int = 0):
        """API 사용량 기록"""
        data = self.load_usage_data()
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        
        # 일일 사용량 기록
        if today not in data["daily_usage"]:
            data["daily_usage"][today] = {}
        
        key = f"{service}_{api_type}"
        if key not in data["daily_usage"][today]:
            data["daily_usage"][today][key] = {"requests": 0, "tokens": 0, "cost": 0.0}
        
        data["daily_usage"][today][key]["requests"] += requests
        data["daily_usage"][today][key]["tokens"] += tokens
        
        # 비용 계산
        cost_per_request = self.api_costs.get(service, {}).get(api_type, 0.0)
        if api_type == "gemini_pro":
            # 토큰 기준 비용
            data["daily_usage"][today][key]["cost"] += (tokens / 1000) * cost_per_request
        else:
            # 요청 기준 비용
            data["daily_usage"][today][key]["cost"] += (requests / 1000) * cost_per_request
        
        # 월간 사용량 기록
        if month not in data["monthly_usage"]:
            data["monthly_usage"][month] = {}
        
        if key not in data["monthly_usage"][month]:
            data["monthly_usage"][month][key] = {"requests": 0, "tokens": 0, "cost": 0.0}
        
        data["monthly_usage"][month][key]["requests"] += requests
        data["monthly_usage"][month][key]["tokens"] += tokens
        data["monthly_usage"][month][key]["cost"] = data["daily_usage"][today][key]["cost"]
        
        self.save_usage_data(data)
    
    def get_current_usage(self) -> List[APIUsageMetrics]:
        """현재 사용량 조회"""
        data = self.load_usage_data()
        today = datetime.now().strftime("%Y-%m-%d")
        metrics = []
        
        if today in data["daily_usage"]:
            for service_api, usage in data["daily_usage"][today].items():
                service, api_type = service_api.split("_", 1)
                
                quota_limit = self.daily_quotas.get(api_type, 0)
                quota_used = usage["requests"] if api_type != "gemini_pro" else usage["tokens"]
                
                metric = APIUsageMetrics(
                    service_name=service_api,
                    requests_count=usage["requests"],
                    cost_per_request=self.api_costs.get(service, {}).get(api_type, 0.0),
                    total_cost=usage["cost"],
                    quota_limit=quota_limit,
                    quota_used=quota_used,
                    timestamp=datetime.now()
                )
                metrics.append(metric)
        
        return metrics
    
    async def check_quota_limits(self) -> List[CostAlert]:
        """할당량 제한 확인"""
        alerts = []
        metrics = self.get_current_usage()
        
        for metric in metrics:
            if metric.quota_percentage > 90:
                level = CostLevel.EMERGENCY
                recommendations = [
                    "API 사용을 즉시 중단하거나 제한하세요",
                    "할당량 증가를 요청하세요",
                    "대체 API 서비스 사용을 고려하세요"
                ]
                auto_actions = ["suspend_non_critical_requests"]
            elif metric.quota_percentage > 80:
                level = CostLevel.CRITICAL
                recommendations = [
                    "API 사용량을 모니터링하고 제한하세요",
                    "요청 캐싱을 늘리세요",
                    "배치 처리를 활용하세요"
                ]
                auto_actions = ["enable_aggressive_caching", "reduce_polling_frequency"]
            elif metric.quota_percentage > 70:
                level = CostLevel.WARNING
                recommendations = [
                    "API 사용량을 주의 깊게 모니터링하세요",
                    "불필요한 요청을 줄이세요"
                ]
                auto_actions = ["enable_request_optimization"]
            else:
                continue
            
            alert = CostAlert(
                resource_type=ResourceType.API_CALLS,
                current_cost=metric.total_cost,
                budget_limit=metric.quota_limit,
                usage_percentage=metric.quota_percentage,
                level=level,
                timestamp=datetime.now(),
                recommendations=recommendations,
                auto_actions=auto_actions
            )
            alerts.append(alert)
        
        return alerts

class ResourceMonitor:
    """리소스 모니터링"""
    
    def __init__(self):
        self.metrics_file = Path("data/resource_metrics.json")
        self.metrics_file.parent.mkdir(exist_ok=True)
    
    async def collect_system_metrics(self) -> List[ResourceMetrics]:
        """시스템 메트릭 수집"""
        metrics = []
        
        try:
            import psutil
            
            # CPU 메트릭
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_metric = ResourceMetrics(
                resource_type=ResourceType.COMPUTE,
                current_usage=cpu_usage,
                capacity=100.0,
                cost_per_unit=0.05,  # 시간당 비용 (예시)
                efficiency_score=self.calculate_efficiency_score(cpu_usage, 100.0),
                timestamp=datetime.now()
            )
            metrics.append(cpu_metric)
            
            # 메모리 메트릭
            memory = psutil.virtual_memory()
            memory_metric = ResourceMetrics(
                resource_type=ResourceType.COMPUTE,
                current_usage=memory.percent,
                capacity=100.0,
                cost_per_unit=0.02,  # 시간당 비용 (예시)
                efficiency_score=self.calculate_efficiency_score(memory.percent, 100.0),
                timestamp=datetime.now()
            )
            metrics.append(memory_metric)
            
            # 디스크 메트릭
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_metric = ResourceMetrics(
                resource_type=ResourceType.STORAGE,
                current_usage=disk_usage_percent,
                capacity=100.0,
                cost_per_unit=0.01,  # GB당 비용 (예시)
                efficiency_score=self.calculate_efficiency_score(disk_usage_percent, 100.0),
                timestamp=datetime.now()
            )
            metrics.append(disk_metric)
            
        except ImportError:
            logger.warning("psutil이 설치되지 않음 - 시스템 메트릭 수집 불가")
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {e}")
        
        return metrics
    
    def calculate_efficiency_score(self, usage: float, capacity: float) -> float:
        """효율성 점수 계산 (0-100)"""
        usage_ratio = usage / capacity if capacity > 0 else 0
        
        # 60-80% 사용률에서 최고 효율성
        if 0.6 <= usage_ratio <= 0.8:
            return 100.0
        elif usage_ratio < 0.6:
            # 낮은 사용률 - 비효율적
            return usage_ratio * 100 * 1.5  # 패널티
        else:
            # 높은 사용률 - 위험
            return max(0, 100 - (usage_ratio - 0.8) * 500)
    
    async def check_resource_efficiency(self) -> List[CostAlert]:
        """리소스 효율성 확인"""
        alerts = []
        metrics = await self.collect_system_metrics()
        
        for metric in metrics:
            if metric.efficiency_score < 30:
                level = CostLevel.CRITICAL
                if metric.usage_percentage > 90:
                    recommendations = [
                        "리소스 용량을 즉시 증가시키세요",
                        "부하를 다른 인스턴스로 분산하세요",
                        "불필요한 프로세스를 중단하세요"
                    ]
                    auto_actions = ["scale_up_resources", "distribute_load"]
                else:
                    recommendations = [
                        "사용하지 않는 리소스를 정리하세요",
                        "리소스 크기를 줄이는 것을 고려하세요",
                        "스케줄 기반 스케일링을 구현하세요"
                    ]
                    auto_actions = ["cleanup_unused_resources", "schedule_downscaling"]
            elif metric.efficiency_score < 60:
                level = CostLevel.WARNING
                recommendations = [
                    "리소스 사용 패턴을 분석하세요",
                    "자동 스케일링을 고려하세요"
                ]
                auto_actions = ["analyze_usage_patterns"]
            else:
                continue
            
            alert = CostAlert(
                resource_type=metric.resource_type,
                current_cost=metric.current_usage * metric.cost_per_unit,
                budget_limit=metric.capacity * metric.cost_per_unit,
                usage_percentage=metric.usage_percentage,
                level=level,
                timestamp=datetime.now(),
                recommendations=recommendations,
                auto_actions=auto_actions
            )
            alerts.append(alert)
        
        return alerts

class BudgetManager:
    """예산 관리자"""
    
    def __init__(self):
        self.budget_file = Path("data/budget_tracking.json")
        self.budget_file.parent.mkdir(exist_ok=True)
        
        # PRD 기준 예산 설정
        self.monthly_budget = Config.MONTHLY_BUDGET
        self.thresholds = {
            "warning": Config.BUDGET_WARNING_THRESHOLD,
            "alert": Config.BUDGET_ALERT_THRESHOLD,
            "critical": Config.BUDGET_CRITICAL_THRESHOLD,
            "emergency": Config.BUDGET_EMERGENCY_THRESHOLD
        }
    
    def load_budget_data(self) -> Dict[str, Any]:
        """예산 데이터 로드"""
        if not self.budget_file.exists():
            return {"monthly_spending": {}, "daily_spending": {}}
        
        try:
            with open(self.budget_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"예산 데이터 로드 실패: {e}")
            return {"monthly_spending": {}, "daily_spending": {}}
    
    def save_budget_data(self, data: Dict[str, Any]):
        """예산 데이터 저장"""
        try:
            with open(self.budget_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"예산 데이터 저장 실패: {e}")
    
    def record_spending(self, category: str, amount: float, description: str = ""):
        """지출 기록"""
        data = self.load_budget_data()
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        
        # 일일 지출 기록
        if today not in data["daily_spending"]:
            data["daily_spending"][today] = {}
        
        if category not in data["daily_spending"][today]:
            data["daily_spending"][today][category] = []
        
        data["daily_spending"][today][category].append({
            "amount": amount,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
        
        # 월간 지출 합계 업데이트
        if month not in data["monthly_spending"]:
            data["monthly_spending"][month] = {}
        
        if category not in data["monthly_spending"][month]:
            data["monthly_spending"][month][category] = 0.0
        
        data["monthly_spending"][month][category] += amount
        
        self.save_budget_data(data)
    
    def get_monthly_spending(self) -> Dict[str, float]:
        """월간 지출 조회"""
        data = self.load_budget_data()
        month = datetime.now().strftime("%Y-%m")
        
        return data["monthly_spending"].get(month, {})
    
    def get_total_monthly_spending(self) -> float:
        """총 월간 지출"""
        monthly_spending = self.get_monthly_spending()
        return sum(monthly_spending.values())
    
    async def check_budget_status(self) -> List[CostAlert]:
        """예산 상태 확인"""
        alerts = []
        total_spending = self.get_total_monthly_spending()
        usage_percentage = (total_spending / self.monthly_budget) * 100
        
        # 예산 임계값 확인
        if usage_percentage >= self.thresholds["emergency"] * 100:
            level = CostLevel.EMERGENCY
            recommendations = [
                "모든 비필수 서비스를 즉시 중단하세요",
                "예산을 즉시 증액하거나 월말까지 서비스를 중단하세요"
            ]
            auto_actions = ["suspend_all_non_critical_services", "enable_emergency_mode"]
        elif usage_percentage >= self.thresholds["critical"] * 100:
            level = CostLevel.CRITICAL
            recommendations = [
                "비용이 많이 드는 작업을 즉시 중단하세요",
                "API 사용량을 대폭 줄이세요",
                "예산 증액을 고려하세요"
            ]
            auto_actions = ["suspend_expensive_operations", "reduce_api_usage"]
        elif usage_percentage >= self.thresholds["alert"] * 100:
            level = CostLevel.WARNING
            recommendations = [
                "비용 사용을 주의 깊게 모니터링하세요",
                "불필요한 작업을 줄이세요"
            ]
            auto_actions = ["enable_cost_monitoring", "optimize_operations"]
        elif usage_percentage >= self.thresholds["warning"] * 100:
            level = CostLevel.WARNING
            recommendations = [
                "비용 사용량을 확인하고 최적화하세요"
            ]
            auto_actions = ["review_cost_optimization"]
        else:
            return alerts  # 정상 범위
        
        alert = CostAlert(
            resource_type=ResourceType.API_CALLS,  # 주요 비용 요소
            current_cost=total_spending,
            budget_limit=self.monthly_budget,
            usage_percentage=usage_percentage,
            level=level,
            timestamp=datetime.now(),
            recommendations=recommendations,
            auto_actions=auto_actions
        )
        alerts.append(alert)
        
        return alerts

class AutomatedCostOptimizer:
    """자동화된 비용 최적화 시스템"""
    
    def __init__(self):
        self.api_manager = APIUsageManager()
        self.resource_monitor = ResourceMonitor()
        self.budget_manager = BudgetManager()
        self.optimization_actions = {
            "suspend_non_critical_requests": self.suspend_non_critical_requests,
            "enable_aggressive_caching": self.enable_aggressive_caching,
            "reduce_polling_frequency": self.reduce_polling_frequency,
            "enable_request_optimization": self.enable_request_optimization,
            "scale_up_resources": self.scale_up_resources,
            "distribute_load": self.distribute_load,
            "cleanup_unused_resources": self.cleanup_unused_resources,
            "schedule_downscaling": self.schedule_downscaling,
            "suspend_expensive_operations": self.suspend_expensive_operations,
            "reduce_api_usage": self.reduce_api_usage,
            "enable_emergency_mode": self.enable_emergency_mode
        }
    
    async def run_cost_optimization_cycle(self):
        """비용 최적화 사이클 실행"""
        logger.info("비용 최적화 사이클 시작")
        
        try:
            all_alerts = []
            
            # 1. API 할당량 확인
            quota_alerts = await self.api_manager.check_quota_limits()
            all_alerts.extend(quota_alerts)
            
            # 2. 리소스 효율성 확인
            resource_alerts = await self.resource_monitor.check_resource_efficiency()
            all_alerts.extend(resource_alerts)
            
            # 3. 예산 상태 확인
            budget_alerts = await self.budget_manager.check_budget_status()
            all_alerts.extend(budget_alerts)
            
            # 4. 알림 처리
            await self.process_cost_alerts(all_alerts)
            
            # 5. 자동 최적화 실행
            await self.execute_auto_optimizations(all_alerts)
            
            # 6. 비용 리포트 생성
            await self.generate_cost_report()
            
            logger.info("비용 최적화 사이클 완료")
            
        except Exception as e:
            logger.error(f"비용 최적화 사이클 실패: {e}")
            await send_critical_alert(
                "비용 최적화 시스템 오류",
                f"비용 최적화 시스템에서 오류가 발생했습니다: {e}",
                service="cost_optimization"
            )
    
    async def process_cost_alerts(self, alerts: List[CostAlert]):
        """비용 알림 처리"""
        if not alerts:
            return
        
        # 심각도별 알림 분류
        emergency_alerts = [a for a in alerts if a.level == CostLevel.EMERGENCY]
        critical_alerts = [a for a in alerts if a.level == CostLevel.CRITICAL]
        warning_alerts = [a for a in alerts if a.level == CostLevel.WARNING]
        
        # 긴급 알림 즉시 전송
        for alert in emergency_alerts:
            await send_critical_alert(
                f"🚨 긴급 비용 알림: {alert.resource_type.value}",
                f"비용 사용량이 위험 수준에 도달했습니다.\n"
                f"현재: {alert.current_cost:.2f}원 ({alert.usage_percentage:.1f}%)\n"
                f"예산: {alert.budget_limit:.2f}원\n\n"
                f"권장 조치:\n" + "\n".join(f"- {rec}" for rec in alert.recommendations),
                service="cost_optimization",
                resource_type=alert.resource_type.value,
                usage_percentage=alert.usage_percentage
            )
        
        # 전체 요약 알림
        if alerts:
            total_cost = sum(alert.current_cost for alert in alerts)
            summary = f"""
비용 최적화 알림 요약:
- 긴급: {len(emergency_alerts)}개
- 위험: {len(critical_alerts)}개
- 경고: {len(warning_alerts)}개

총 비용: {total_cost:.2f}원
"""
            
            if emergency_alerts or critical_alerts:
                await send_warning_alert(
                    "비용 최적화 알림",
                    summary,
                    service="cost_optimization",
                    total_alerts=len(alerts),
                    total_cost=total_cost
                )
    
    async def execute_auto_optimizations(self, alerts: List[CostAlert]):
        """자동 최적화 실행"""
        executed_actions = set()
        
        for alert in alerts:
            for action in alert.auto_actions:
                if action in executed_actions:
                    continue  # 중복 실행 방지
                
                if action in self.optimization_actions:
                    try:
                        await self.optimization_actions[action](alert)
                        executed_actions.add(action)
                        logger.info(f"자동 최적화 실행: {action}")
                    except Exception as e:
                        logger.error(f"자동 최적화 실패 ({action}): {e}")
    
    async def suspend_non_critical_requests(self, alert: CostAlert):
        """비핵심 요청 중단"""
        # 실제 구현에서는 API 요청 큐를 관리하여 우선순위가 낮은 요청을 중단
        logger.info("비핵심 API 요청을 중단합니다")
        
        # 환경 변수나 설정 파일을 통해 제한 설정
        os.environ["ENABLE_NON_CRITICAL_APIS"] = "false"
        
        await send_info_alert(
            "비핵심 API 요청 중단",
            "할당량 보호를 위해 비핵심 API 요청이 자동으로 중단되었습니다.",
            service="cost_optimization"
        )
    
    async def enable_aggressive_caching(self, alert: CostAlert):
        """적극적 캐싱 활성화"""
        logger.info("적극적 캐싱을 활성화합니다")
        
        # 캐시 TTL 증가
        os.environ["CACHE_TTL_MULTIPLIER"] = "3"
        os.environ["ENABLE_AGGRESSIVE_CACHING"] = "true"
        
        await send_info_alert(
            "적극적 캐싱 활성화",
            "API 비용 절약을 위해 캐시 시간이 연장되었습니다.",
            service="cost_optimization"
        )
    
    async def reduce_polling_frequency(self, alert: CostAlert):
        """폴링 빈도 감소"""
        logger.info("폴링 빈도를 감소시킵니다")
        
        # 폴링 간격 증가
        os.environ["POLLING_INTERVAL_MULTIPLIER"] = "2"
        
        await send_info_alert(
            "폴링 빈도 감소",
            "API 사용량 절약을 위해 데이터 폴링 빈도가 감소되었습니다.",
            service="cost_optimization"
        )
    
    async def enable_request_optimization(self, alert: CostAlert):
        """요청 최적화 활성화"""
        logger.info("요청 최적화를 활성화합니다")
        
        # 배치 처리 활성화
        os.environ["ENABLE_BATCH_PROCESSING"] = "true"
        os.environ["BATCH_SIZE"] = "50"
    
    async def scale_up_resources(self, alert: CostAlert):
        """리소스 스케일업"""
        logger.info("리소스 스케일업을 요청합니다")
        
        # Kubernetes HPA 설정 조정 또는 클라우드 API 호출
        await send_warning_alert(
            "리소스 스케일업 필요",
            f"{alert.resource_type.value} 리소스의 스케일업이 필요합니다.",
            service="cost_optimization"
        )
    
    async def distribute_load(self, alert: CostAlert):
        """부하 분산"""
        logger.info("부하 분산을 활성화합니다")
        
        # 로드 밸런서 설정 조정
        os.environ["ENABLE_LOAD_BALANCING"] = "true"
    
    async def cleanup_unused_resources(self, alert: CostAlert):
        """사용하지 않는 리소스 정리"""
        logger.info("사용하지 않는 리소스를 정리합니다")
        
        # 임시 파일 정리, 오래된 캐시 삭제 등
        import shutil
        temp_dirs = ["/tmp", "temp", "cache"]
        
        for temp_dir in temp_dirs:
            if Path(temp_dir).exists():
                try:
                    # 1주일 이상 된 파일만 삭제
                    cutoff = datetime.now() - timedelta(days=7)
                    for file_path in Path(temp_dir).rglob("*"):
                        if file_path.is_file() and datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff:
                            file_path.unlink()
                except Exception as e:
                    logger.error(f"임시 파일 정리 실패: {e}")
    
    async def schedule_downscaling(self, alert: CostAlert):
        """다운스케일링 스케줄"""
        logger.info("다운스케일링을 스케줄합니다")
        
        # 야간 시간대 다운스케일링 설정
        os.environ["ENABLE_NIGHT_DOWNSCALING"] = "true"
        os.environ["DOWNSCALE_START_HOUR"] = "22"
        os.environ["DOWNSCALE_END_HOUR"] = "6"
    
    async def suspend_expensive_operations(self, alert: CostAlert):
        """비용이 많이 드는 작업 중단"""
        logger.info("비용이 많이 드는 작업을 중단합니다")
        
        # 대용량 분석, 히스토리컬 데이터 처리 등 중단
        os.environ["SUSPEND_HEAVY_ANALYSIS"] = "true"
        os.environ["SUSPEND_HISTORICAL_PROCESSING"] = "true"
        
        await send_warning_alert(
            "비용 절약 모드 활성화",
            "예산 보호를 위해 비용이 많이 드는 작업이 일시 중단되었습니다.",
            service="cost_optimization"
        )
    
    async def reduce_api_usage(self, alert: CostAlert):
        """API 사용량 대폭 감소"""
        logger.info("API 사용량을 대폭 감소시킵니다")
        
        # API 요청 제한 강화
        os.environ["API_RATE_LIMIT"] = "10"  # 시간당 10개로 제한
        os.environ["ENABLE_STRICT_RATE_LIMITING"] = "true"
    
    async def enable_emergency_mode(self, alert: CostAlert):
        """비상 모드 활성화"""
        logger.info("비상 모드를 활성화합니다")
        
        # 모든 비필수 기능 중단
        os.environ["EMERGENCY_MODE"] = "true"
        os.environ["DISABLE_ALL_NON_ESSENTIAL"] = "true"
        
        await send_critical_alert(
            "🚨 비상 모드 활성화",
            "예산 한계 도달로 비상 모드가 활성화되었습니다. 모든 비필수 기능이 중단됩니다.",
            service="cost_optimization"
        )
    
    async def generate_cost_report(self):
        """비용 리포트 생성"""
        try:
            # API 사용량 요약
            api_metrics = self.api_manager.get_current_usage()
            total_api_cost = sum(metric.total_cost for metric in api_metrics)
            
            # 월간 지출 요약
            monthly_spending = self.budget_manager.get_monthly_spending()
            total_monthly_cost = self.budget_manager.get_total_monthly_spending()
            
            # 예산 사용률
            budget_usage = (total_monthly_cost / self.budget_manager.monthly_budget) * 100
            
            report = f"""
💰 일일 비용 리포트
================

📊 API 사용량:
- 총 API 비용: {total_api_cost:.2f}원
- 활성 서비스: {len(api_metrics)}개

💳 월간 예산 현황:
- 사용 금액: {total_monthly_cost:.2f}원
- 예산 한도: {self.budget_manager.monthly_budget:.2f}원
- 사용률: {budget_usage:.1f}%

📈 카테고리별 지출:
{chr(10).join(f"- {cat}: {cost:.2f}원" for cat, cost in monthly_spending.items())}

🎯 상태: {"⚠️ 주의" if budget_usage > 70 else "✅ 정상"}
"""
            
            await send_info_alert(
                "일일 비용 리포트",
                report,
                service="cost_optimization",
                budget_usage=budget_usage,
                total_cost=total_monthly_cost
            )
            
        except Exception as e:
            logger.error(f"비용 리포트 생성 실패: {e}")

async def main():
    """메인 함수"""
    cost_optimizer = AutomatedCostOptimizer()
    
    # 지속적 비용 최적화 모니터링
    while True:
        try:
            await cost_optimizer.run_cost_optimization_cycle()
            await asyncio.sleep(1800)  # 30분 간격
        except KeyboardInterrupt:
            logger.info("비용 최적화 시스템 중단")
            break
        except Exception as e:
            logger.error(f"비용 최적화 시스템 오류: {e}")
            await asyncio.sleep(300)  # 5분 후 재시도

if __name__ == "__main__":
    asyncio.run(main())