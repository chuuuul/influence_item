"""
채널 탐색 정확도 측정 시스템

실제 채널 데이터를 사용하여 탐색 알고리즘의 정확도를 벤치마킹하고
지속적으로 성능을 개선할 수 있는 피드백 시스템
"""

import logging
import json
import statistics
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
import pandas as pd

from .models import ChannelCandidate, DiscoveryConfig, ChannelType, ChannelStatus
from ..youtube_api.youtube_client import ChannelInfo


@dataclass
class GroundTruthChannel:
    """검증된 참조 채널 데이터"""
    channel_id: str
    channel_name: str
    category: str                    # 실제 카테고리 (뷰티, 패션, 라이프스타일 등)
    relevance_score: float          # 전문가 평가 관련성 점수 (0-1)
    is_target_relevant: bool        # 타겟 키워드와 관련 있는지 여부
    subscriber_count: int
    video_count: int
    verified: bool
    keywords: List[str] = field(default_factory=list)
    manual_review_notes: str = ""   # 수동 검토 메모
    last_verified: datetime = field(default_factory=datetime.now)


@dataclass 
class AccuracyMetrics:
    """정확도 측정 지표"""
    precision: float = 0.0          # 정밀도: 추천된 것 중 실제 관련있는 비율
    recall: float = 0.0             # 재현율: 실제 관련있는 것 중 추천된 비율  
    f1_score: float = 0.0           # F1 점수: 정밀도와 재현율의 조화평균
    accuracy: float = 0.0           # 정확도: 전체 중 올바르게 분류된 비율
    
    # 상세 지표
    true_positives: int = 0         # 올바르게 추천된 관련 채널
    false_positives: int = 0        # 잘못 추천된 무관한 채널
    true_negatives: int = 0         # 올바르게 제외된 무관한 채널
    false_negatives: int = 0        # 잘못 제외된 관련 채널
    
    total_candidates: int = 0
    relevant_candidates: int = 0
    recommended_candidates: int = 0


@dataclass
class BenchmarkResult:
    """벤치마킹 결과"""
    benchmark_id: str
    timestamp: datetime
    config_used: Dict[str, Any]
    
    # 전체 정확도
    overall_metrics: AccuracyMetrics
    
    # 카테고리별 정확도  
    category_metrics: Dict[str, AccuracyMetrics] = field(default_factory=dict)
    
    # 구독자 규모별 정확도
    scale_metrics: Dict[str, AccuracyMetrics] = field(default_factory=dict)
    
    # 상세 결과
    detailed_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # 개선 제안
    improvement_suggestions: List[str] = field(default_factory=list)


class GroundTruthManager:
    """참조 데이터 관리자"""
    
    def __init__(self, data_file_path: str):
        self.data_file_path = Path(data_file_path)
        self.ground_truth_channels: List[GroundTruthChannel] = []
        self.logger = logging.getLogger(__name__)
        
        # 데이터 로드
        self._load_ground_truth_data()
    
    def _load_ground_truth_data(self):
        """참조 데이터 로드"""
        
        if self.data_file_path.exists():
            try:
                with open(self.data_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.ground_truth_channels = [
                    GroundTruthChannel(**item) for item in data
                ]
                
                self.logger.info(f"참조 데이터 로드 완료: {len(self.ground_truth_channels)}개 채널")
                
            except Exception as e:
                self.logger.error(f"참조 데이터 로드 실패: {str(e)}")
                self._create_sample_ground_truth()
        else:
            self.logger.info("참조 데이터 파일이 없어 샘플 데이터 생성")
            self._create_sample_ground_truth()
    
    def _create_sample_ground_truth(self):
        """샘플 참조 데이터 생성"""
        
        sample_channels = [
            # 뷰티 카테고리 - 관련성 높음
            GroundTruthChannel(
                channel_id="UC_beauty_expert_1",
                channel_name="뷰티 전문가 채널",
                category="뷰티",
                relevance_score=0.95,
                is_target_relevant=True,
                subscriber_count=150000,
                video_count=200,
                verified=True,
                keywords=["뷰티", "메이크업", "스킨케어", "리뷰"],
                manual_review_notes="전문적인 뷰티 콘텐츠, 제품 리뷰 중심"
            ),
            
            # 패션 카테고리 - 관련성 높음  
            GroundTruthChannel(
                channel_id="UC_fashion_influencer_1",
                channel_name="패션 인플루언서",
                category="패션",
                relevance_score=0.90,
                is_target_relevant=True,
                subscriber_count=80000,
                video_count=150,
                verified=False,
                keywords=["패션", "스타일링", "옷", "코디"],
                manual_review_notes="패션 트렌드 소개, 스타일링 팁"
            ),
            
            # 라이프스타일 - 중간 관련성
            GroundTruthChannel(
                channel_id="UC_lifestyle_vlogger_1", 
                channel_name="라이프스타일 브이로거",
                category="라이프스타일",
                relevance_score=0.70,
                is_target_relevant=True,
                subscriber_count=50000,
                video_count=300,
                verified=False,
                keywords=["일상", "vlog", "라이프스타일"],
                manual_review_notes="일상 브이로그, 가끔 뷰티/패션 언급"
            ),
            
            # 게임 카테고리 - 관련성 낮음
            GroundTruthChannel(
                channel_id="UC_gaming_channel_1",
                channel_name="게임 전문 채널",
                category="게임",
                relevance_score=0.10,
                is_target_relevant=False,
                subscriber_count=200000,
                video_count=500,
                verified=True,
                keywords=["게임", "플레이", "리뷰", "공략"],
                manual_review_notes="게임 전용 채널, 뷰티/패션과 무관"
            ),
            
            # 요리 카테고리 - 관련성 낮음
            GroundTruthChannel(
                channel_id="UC_cooking_channel_1",
                channel_name="요리 레시피 채널",
                category="요리",
                relevance_score=0.20,
                is_target_relevant=False,
                subscriber_count=100000,
                video_count=250,
                verified=False,
                keywords=["요리", "레시피", "음식", "맛집"],
                manual_review_notes="요리 전문, 뷰티/패션과 거리 있음"
            )
        ]
        
        self.ground_truth_channels = sample_channels
        self._save_ground_truth_data()
    
    def _save_ground_truth_data(self):
        """참조 데이터 저장"""
        
        try:
            # 데이터 디렉토리 생성
            self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = [asdict(channel) for channel in self.ground_truth_channels]
            
            with open(self.data_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"참조 데이터 저장 완료: {self.data_file_path}")
            
        except Exception as e:
            self.logger.error(f"참조 데이터 저장 실패: {str(e)}")
    
    def add_ground_truth_channel(self, channel: GroundTruthChannel):
        """새로운 참조 채널 추가"""
        
        # 중복 확인
        existing_ids = {ch.channel_id for ch in self.ground_truth_channels}
        if channel.channel_id not in existing_ids:
            self.ground_truth_channels.append(channel)
            self._save_ground_truth_data()
            self.logger.info(f"새로운 참조 채널 추가: {channel.channel_name}")
    
    def get_ground_truth_by_category(self, category: str) -> List[GroundTruthChannel]:
        """카테고리별 참조 데이터 조회"""
        return [ch for ch in self.ground_truth_channels if ch.category == category]
    
    def get_relevant_channels(self, min_relevance: float = 0.5) -> List[GroundTruthChannel]:
        """관련성 기준으로 채널 필터링"""
        return [
            ch for ch in self.ground_truth_channels 
            if ch.is_target_relevant and ch.relevance_score >= min_relevance
        ]


class AccuracyEvaluator:
    """정확도 평가기"""
    
    def __init__(self, ground_truth_manager: GroundTruthManager):
        self.ground_truth_manager = ground_truth_manager
        self.logger = logging.getLogger(__name__)
    
    def evaluate_discovery_results(self, 
                                 discovered_candidates: List[ChannelCandidate],
                                 config: DiscoveryConfig,
                                 relevance_threshold: float = 0.6) -> BenchmarkResult:
        """탐색 결과 정확도 평가"""
        
        benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 1. 전체 정확도 계산
        overall_metrics = self._calculate_overall_accuracy(
            discovered_candidates, relevance_threshold
        )
        
        # 2. 카테고리별 정확도 계산
        category_metrics = self._calculate_category_accuracy(
            discovered_candidates, relevance_threshold
        )
        
        # 3. 구독자 규모별 정확도 계산
        scale_metrics = self._calculate_scale_accuracy(
            discovered_candidates, relevance_threshold
        )
        
        # 4. 상세 결과 생성
        detailed_results = self._generate_detailed_results(
            discovered_candidates, relevance_threshold
        )
        
        # 5. 개선 제안 생성
        improvement_suggestions = self._generate_improvement_suggestions(
            overall_metrics, category_metrics, scale_metrics
        )
        
        result = BenchmarkResult(
            benchmark_id=benchmark_id,
            timestamp=datetime.now(),
            config_used=asdict(config),
            overall_metrics=overall_metrics,
            category_metrics=category_metrics,
            scale_metrics=scale_metrics,
            detailed_results=detailed_results,
            improvement_suggestions=improvement_suggestions
        )
        
        self.logger.info(f"정확도 평가 완료: {benchmark_id}")
        return result
    
    def _calculate_overall_accuracy(self, 
                                  candidates: List[ChannelCandidate],
                                  relevance_threshold: float) -> AccuracyMetrics:
        """전체 정확도 계산"""
        
        # 참조 데이터에서 관련 채널 ID 집합
        relevant_channel_ids = {
            ch.channel_id for ch in self.ground_truth_manager.ground_truth_channels
            if ch.is_target_relevant and ch.relevance_score >= relevance_threshold
        }
        
        # 탐색 결과에서 추천된 채널 ID 집합 (점수 기준)
        recommended_channel_ids = {
            candidate.channel_id for candidate in candidates
            if candidate.total_score >= 60  # 추천 점수 임계치
        }
        
        # 전체 참조 채널 ID 집합
        all_ground_truth_ids = {ch.channel_id for ch in self.ground_truth_manager.ground_truth_channels}
        
        # 혼동 행렬 계산
        tp = len(relevant_channel_ids & recommended_channel_ids)  # True Positive
        fp = len(recommended_channel_ids - relevant_channel_ids)   # False Positive  
        fn = len(relevant_channel_ids - recommended_channel_ids)   # False Negative
        tn = len(all_ground_truth_ids - relevant_channel_ids - recommended_channel_ids)  # True Negative
        
        # 지표 계산
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
        
        return AccuracyMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            total_candidates=len(candidates),
            relevant_candidates=len(relevant_channel_ids),
            recommended_candidates=len(recommended_channel_ids)
        )
    
    def _calculate_category_accuracy(self, 
                                   candidates: List[ChannelCandidate],
                                   relevance_threshold: float) -> Dict[str, AccuracyMetrics]:
        """카테고리별 정확도 계산"""
        
        category_metrics = {}
        
        # 카테고리별로 분석
        categories = set(ch.category for ch in self.ground_truth_manager.ground_truth_channels)
        
        for category in categories:
            # 해당 카테고리의 참조 채널들
            category_ground_truth = self.ground_truth_manager.get_ground_truth_by_category(category)
            
            # 관련 채널 ID
            relevant_ids = {
                ch.channel_id for ch in category_ground_truth
                if ch.is_target_relevant and ch.relevance_score >= relevance_threshold
            }
            
            # 추천된 채널 중 해당 카테고리에 속하는 것들
            category_candidate_ids = {ch.channel_id for ch in category_ground_truth}
            recommended_ids = {
                candidate.channel_id for candidate in candidates
                if candidate.channel_id in category_candidate_ids and candidate.total_score >= 60
            }
            
            # 해당 카테고리 전체 채널
            all_category_ids = {ch.channel_id for ch in category_ground_truth}
            
            # 혼동 행렬
            tp = len(relevant_ids & recommended_ids)
            fp = len(recommended_ids - relevant_ids)
            fn = len(relevant_ids - recommended_ids)
            tn = len(all_category_ids - relevant_ids - recommended_ids)
            
            # 지표 계산
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
            
            category_metrics[category] = AccuracyMetrics(
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                accuracy=accuracy,
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn
            )
        
        return category_metrics
    
    def _calculate_scale_accuracy(self, 
                                candidates: List[ChannelCandidate],
                                relevance_threshold: float) -> Dict[str, AccuracyMetrics]:
        """구독자 규모별 정확도 계산"""
        
        scale_ranges = {
            "소규모 (1K-10K)": (1000, 10000),
            "중규모 (10K-100K)": (10000, 100000),
            "대규모 (100K-1M)": (100000, 1000000),
            "초대규모 (1M+)": (1000000, float('inf'))
        }
        
        scale_metrics = {}
        
        for scale_name, (min_subs, max_subs) in scale_ranges.items():
            # 해당 규모의 참조 채널들
            scale_ground_truth = [
                ch for ch in self.ground_truth_manager.ground_truth_channels
                if min_subs <= ch.subscriber_count < max_subs
            ]
            
            if not scale_ground_truth:
                continue
            
            # 관련 채널 ID
            relevant_ids = {
                ch.channel_id for ch in scale_ground_truth
                if ch.is_target_relevant and ch.relevance_score >= relevance_threshold
            }
            
            # 추천된 채널 중 해당 규모에 속하는 것들
            scale_candidate_ids = {ch.channel_id for ch in scale_ground_truth}
            recommended_ids = {
                candidate.channel_id for candidate in candidates
                if candidate.channel_id in scale_candidate_ids and candidate.total_score >= 60
            }
            
            # 해당 규모 전체 채널
            all_scale_ids = {ch.channel_id for ch in scale_ground_truth}
            
            # 혼동 행렬
            tp = len(relevant_ids & recommended_ids)
            fp = len(recommended_ids - relevant_ids)
            fn = len(relevant_ids - recommended_ids)
            tn = len(all_scale_ids - relevant_ids - recommended_ids)
            
            # 지표 계산
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
            
            scale_metrics[scale_name] = AccuracyMetrics(
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                accuracy=accuracy,
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn
            )
        
        return scale_metrics
    
    def _generate_detailed_results(self, 
                                 candidates: List[ChannelCandidate],
                                 relevance_threshold: float) -> List[Dict[str, Any]]:
        """상세 결과 생성"""
        
        detailed_results = []
        
        # 참조 데이터 맵 생성
        ground_truth_map = {
            ch.channel_id: ch for ch in self.ground_truth_manager.ground_truth_channels
        }
        
        for candidate in candidates:
            if candidate.channel_id in ground_truth_map:
                gt_channel = ground_truth_map[candidate.channel_id]
                
                # 예측 결과
                predicted_relevant = candidate.total_score >= 60
                actual_relevant = (gt_channel.is_target_relevant and 
                                 gt_channel.relevance_score >= relevance_threshold)
                
                # 분류 결과
                if predicted_relevant and actual_relevant:
                    classification = "True Positive"
                elif predicted_relevant and not actual_relevant:
                    classification = "False Positive"
                elif not predicted_relevant and actual_relevant:
                    classification = "False Negative"
                else:
                    classification = "True Negative"
                
                detailed_results.append({
                    "channel_id": candidate.channel_id,
                    "channel_name": candidate.channel_name,
                    "predicted_score": candidate.total_score,
                    "predicted_relevant": predicted_relevant,
                    "actual_relevance_score": gt_channel.relevance_score,
                    "actual_relevant": actual_relevant,
                    "classification": classification,
                    "category": gt_channel.category,
                    "subscriber_count": candidate.subscriber_count,
                    "notes": gt_channel.manual_review_notes
                })
        
        return detailed_results
    
    def _generate_improvement_suggestions(self, 
                                        overall: AccuracyMetrics,
                                        category: Dict[str, AccuracyMetrics],
                                        scale: Dict[str, AccuracyMetrics]) -> List[str]:
        """개선 제안 생성"""
        
        suggestions = []
        
        # 전체 성능 분석
        if overall.precision < 0.7:
            suggestions.append("정밀도 개선 필요: 추천 기준을 더 엄격하게 설정하여 잘못된 추천 줄이기")
        
        if overall.recall < 0.7:
            suggestions.append("재현율 개선 필요: 탐색 범위를 넓히거나 매칭 기준을 완화하여 누락 줄이기")
        
        if overall.f1_score < 0.7:
            suggestions.append("F1 점수 개선 필요: 정밀도와 재현율의 균형 조정")
        
        # 카테고리별 분석
        worst_category = None
        worst_f1 = 1.0
        
        for cat_name, cat_metrics in category.items():
            if cat_metrics.f1_score < worst_f1:
                worst_f1 = cat_metrics.f1_score
                worst_category = cat_name
        
        if worst_category and worst_f1 < 0.6:
            suggestions.append(f"'{worst_category}' 카테고리 성능 개선 필요: 해당 카테고리 특화 키워드 추가")
        
        # 규모별 분석
        for scale_name, scale_metrics in scale.items():
            if scale_metrics.f1_score < 0.6:
                suggestions.append(f"'{scale_name}' 규모 채널 성능 개선 필요: 규모별 점수 가중치 조정")
        
        # 일반적인 제안
        if overall.f1_score > 0.8:
            suggestions.append("우수한 성능! 현재 설정 유지 권장")
        elif not suggestions:
            suggestions.append("전반적으로 양호한 성능, 세부 튜닝으로 개선 가능")
        
        return suggestions


class BenchmarkReporter:
    """벤치마킹 결과 리포터"""
    
    def __init__(self, output_dir: str = "benchmark_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def generate_report(self, result: BenchmarkResult) -> str:
        """상세 리포트 생성"""
        
        report_lines = [
            f"# 채널 탐색 정확도 벤치마킹 리포트",
            f"",
            f"**벤치마크 ID:** {result.benchmark_id}",
            f"**측정 시간:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 전체 성능 지표",
            f"",
            f"| 지표 | 값 |",
            f"|------|-----|",
            f"| 정밀도 (Precision) | {result.overall_metrics.precision:.3f} |",
            f"| 재현율 (Recall) | {result.overall_metrics.recall:.3f} |",
            f"| F1 점수 | {result.overall_metrics.f1_score:.3f} |",
            f"| 정확도 (Accuracy) | {result.overall_metrics.accuracy:.3f} |",
            f"| 전체 후보 수 | {result.overall_metrics.total_candidates} |",
            f"| 관련 채널 수 | {result.overall_metrics.relevant_candidates} |",
            f"| 추천된 채널 수 | {result.overall_metrics.recommended_candidates} |",
            f"",
            f"## 혼동 행렬",
            f"",
            f"| | 예측: 관련 | 예측: 무관 |",
            f"|------|------------|------------|",
            f"| **실제: 관련** | {result.overall_metrics.true_positives} (TP) | {result.overall_metrics.false_negatives} (FN) |",
            f"| **실제: 무관** | {result.overall_metrics.false_positives} (FP) | {result.overall_metrics.true_negatives} (TN) |",
            f"",
        ]
        
        # 카테고리별 성능
        if result.category_metrics:
            report_lines.extend([
                f"## 카테고리별 성능",
                f"",
                f"| 카테고리 | 정밀도 | 재현율 | F1 점수 |",
                f"|----------|--------|--------|---------|"
            ])
            
            for category, metrics in result.category_metrics.items():
                report_lines.append(
                    f"| {category} | {metrics.precision:.3f} | {metrics.recall:.3f} | {metrics.f1_score:.3f} |"
                )
            
            report_lines.append("")
        
        # 규모별 성능
        if result.scale_metrics:
            report_lines.extend([
                f"## 구독자 규모별 성능",
                f"",
                f"| 규모 | 정밀도 | 재현율 | F1 점수 |",
                f"|------|--------|--------|---------|"
            ])
            
            for scale, metrics in result.scale_metrics.items():
                report_lines.append(
                    f"| {scale} | {metrics.precision:.3f} | {metrics.recall:.3f} | {metrics.f1_score:.3f} |"
                )
            
            report_lines.append("")
        
        # 개선 제안
        if result.improvement_suggestions:
            report_lines.extend([
                f"## 개선 제안",
                f""
            ])
            
            for i, suggestion in enumerate(result.improvement_suggestions, 1):
                report_lines.append(f"{i}. {suggestion}")
            
            report_lines.append("")
        
        # 설정 정보
        report_lines.extend([
            f"## 사용된 설정",
            f"",
            f"```json",
            json.dumps(result.config_used, indent=2, ensure_ascii=False, default=str),
            f"```"
        ])
        
        report_content = "\n".join(report_lines)
        
        # 파일 저장
        report_file = self.output_dir / f"{result.benchmark_id}_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.logger.info(f"벤치마킹 리포트 생성: {report_file}")
        return str(report_file)
    
    def save_raw_results(self, result: BenchmarkResult) -> str:
        """원시 결과 데이터 저장"""
        
        results_file = self.output_dir / f"{result.benchmark_id}_results.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"원시 결과 저장: {results_file}")
        return str(results_file)


# 편의 함수들
def create_accuracy_evaluator(ground_truth_file: str = "ground_truth_channels.json") -> AccuracyEvaluator:
    """정확도 평가기 생성"""
    
    # 데이터 디렉토리 설정
    data_dir = Path("channel_discovery_data")
    data_dir.mkdir(exist_ok=True)
    
    ground_truth_path = data_dir / ground_truth_file
    
    ground_truth_manager = GroundTruthManager(str(ground_truth_path))
    return AccuracyEvaluator(ground_truth_manager)


def benchmark_discovery_system(discovery_engine, config: DiscoveryConfig) -> BenchmarkResult:
    """탐색 시스템 벤치마킹 실행"""
    
    # 정확도 평가기 생성
    evaluator = create_accuracy_evaluator()
    
    # 탐색 실행 (실제 또는 Mock 모드)
    candidates = discovery_engine.discover_channels(config)
    
    # 정확도 평가
    result = evaluator.evaluate_discovery_results(candidates, config)
    
    # 리포트 생성
    reporter = BenchmarkReporter()
    report_file = reporter.generate_report(result)
    results_file = reporter.save_raw_results(result)
    
    return result