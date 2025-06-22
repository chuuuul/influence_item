"""
워크플로우 통합 테스트

전체 필터링 워크플로우의 통합 동작을 테스트합니다.
"""

import unittest
from datetime import datetime
from typing import Dict, Any
import tempfile
import os

from src.workflow.workflow_manager import WorkflowManager
from src.workflow.filter_engine import FilterEngine, FilterRule, FilterAction, FilterResult, FilterPriority
from src.workflow.priority_calculator import PriorityCalculator, PriorityLevel
from src.workflow.state_router import StateRouter, CandidateStatus
from src.workflow.audit_logger import AuditLogger


class TestWorkflowIntegration(unittest.TestCase):
    """워크플로우 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 임시 데이터베이스 생성
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # 워크플로우 매니저 초기화
        self.audit_logger = AuditLogger(db_path=self.temp_db.name)
        self.workflow_manager = WorkflowManager(audit_logger=self.audit_logger)
        
        # 테스트 데이터
        self.sample_candidate = {
            "source_info": {
                "celebrity_name": "강민경",
                "channel_name": "걍밍경",
                "video_title": "파리 출장 다녀왔습니다 VLOG",
                "video_url": "https://www.youtube.com/watch?v=test123",
                "upload_date": "2025-06-22"
            },
            "candidate_info": {
                "product_name_ai": "아비에무아 숄더백 (베이지)",
                "clip_start_time": 315,
                "clip_end_time": 340,
                "score_details": {
                    "total": 85,
                    "sentiment_score": 0.9,
                    "endorsement_score": 0.85,
                    "influencer_score": 0.9
                }
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/test"
            },
            "status_info": {
                "current_status": "analysis_complete",
                "is_ppl": False,
                "ppl_confidence": 0.1
            }
        }
        
    def tearDown(self):
        """테스트 정리"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
            
    def test_single_candidate_workflow(self):
        """단일 후보 워크플로우 테스트"""
        result = self.workflow_manager.process_candidate(self.sample_candidate.copy())
        
        # 성공적 처리 확인
        self.assertTrue(result.success)
        self.assertIsNotNone(result.priority_score)
        self.assertIsNotNone(result.state_transition)
        self.assertGreater(len(result.filter_actions), 0)
        
        # 우선순위 점수 검증
        self.assertGreater(result.priority_score.total_score, 0)
        self.assertIn(result.priority_score.level, list(PriorityLevel))
        
        # 상태 전환 검증
        self.assertEqual(result.state_transition.from_status, CandidateStatus.ANALYSIS_COMPLETE)
        self.assertIn(result.state_transition.to_status, [
            CandidateStatus.NEEDS_REVIEW,
            CandidateStatus.HIGH_PL_RISK,
            CandidateStatus.FILTERED_NO_COUPANG
        ])
        
    def test_high_score_candidate_priority(self):
        """고득점 후보 우선순위 테스트"""
        high_score_candidate = self.sample_candidate.copy()
        high_score_candidate["candidate_info"]["score_details"]["total"] = 95
        
        result = self.workflow_manager.process_candidate(high_score_candidate)
        
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.priority_score.total_score, 80)
        self.assertIn(result.priority_score.level, [PriorityLevel.URGENT, PriorityLevel.HIGH])
        self.assertEqual(result.state_transition.to_status, CandidateStatus.NEEDS_REVIEW)
        
    def test_low_score_candidate_filtering(self):
        """저득점 후보 필터링 테스트"""
        low_score_candidate = self.sample_candidate.copy()
        low_score_candidate["candidate_info"]["score_details"]["total"] = 45
        
        result = self.workflow_manager.process_candidate(low_score_candidate)
        
        self.assertTrue(result.success)
        self.assertEqual(result.state_transition.to_status, CandidateStatus.LOW_SCORE_FILTERED)
        
    def test_high_ppl_risk_filtering(self):
        """고PPL 위험도 필터링 테스트"""
        high_ppl_candidate = self.sample_candidate.copy()
        high_ppl_candidate["status_info"]["ppl_confidence"] = 0.8
        
        result = self.workflow_manager.process_candidate(high_ppl_candidate)
        
        self.assertTrue(result.success)
        self.assertEqual(result.state_transition.to_status, CandidateStatus.HIGH_PL_RISK)
        
    def test_no_monetization_filtering(self):
        """수익화 불가능 필터링 테스트"""
        no_monetization_candidate = self.sample_candidate.copy()
        no_monetization_candidate["monetization_info"]["is_coupang_product"] = False
        
        result = self.workflow_manager.process_candidate(no_monetization_candidate)
        
        self.assertTrue(result.success)
        self.assertEqual(result.state_transition.to_status, CandidateStatus.FILTERED_NO_COUPANG)
        
    def test_batch_processing(self):
        """배치 처리 테스트"""
        candidates = []
        
        # 다양한 점수의 후보들 생성
        for i, score in enumerate([95, 75, 45, 85, 55]):
            candidate = self.sample_candidate.copy()
            candidate["candidate_info"]["score_details"]["total"] = score
            candidate["source_info"]["video_url"] = f"https://www.youtube.com/watch?v=test{i}"
            candidates.append(candidate)
            
        batch_result = self.workflow_manager.process_candidates_batch(candidates)
        
        # 배치 결과 검증
        self.assertEqual(batch_result.total_processed, 5)
        self.assertEqual(batch_result.successful, 5)
        self.assertEqual(batch_result.failed, 0)
        self.assertEqual(len(batch_result.results), 5)
        
        # 각 결과 검증
        for result in batch_result.results:
            self.assertTrue(result.success)
            self.assertIsNotNone(result.priority_score)
            
    def test_data_validation(self):
        """데이터 구조 검증 테스트"""
        # 필수 필드 존재 확인
        required_fields = ["source_info", "candidate_info", "monetization_info", "status_info"]
        for field in required_fields:
            self.assertIn(field, self.sample_candidate)
            
        # 점수 구조 확인
        score_details = self.sample_candidate["candidate_info"]["score_details"]
        self.assertIn("sentiment_score", score_details)
        self.assertIn("endorsement_score", score_details)
        self.assertIn("influencer_score", score_details)
        
    def test_state_transitions(self):
        """상태 전환 테스트"""
        candidate = self.sample_candidate.copy()
        
        # 초기 처리
        result = self.workflow_manager.process_candidate(candidate)
        self.assertTrue(result.success)
        
        # 수동 상태 전환
        if result.state_transition.to_status == CandidateStatus.NEEDS_REVIEW:
            transition = self.workflow_manager.state_router.apply_manual_transition(
                candidate, "approved", "운영자 승인", "test_operator"
            )
            self.assertEqual(transition.to_status, CandidateStatus.APPROVED)
            
    def test_audit_logging(self):
        """감사 로깅 테스트"""
        # 워크플로우 실행
        result = self.workflow_manager.process_candidate(self.sample_candidate.copy())
        self.assertTrue(result.success)
        
        # 로그 조회
        logs = self.audit_logger.get_logs(limit=10)
        self.assertGreater(len(logs), 0)
        
        # 로그 내용 검증
        workflow_logs = [log for log in logs if log.category.value == "workflow"]
        self.assertGreater(len(workflow_logs), 0)
        
    def test_performance_monitoring(self):
        """성능 모니터링 테스트"""
        # 여러 후보 처리하여 성능 데이터 생성
        candidates = [self.sample_candidate.copy() for _ in range(5)]
        
        for i, candidate in enumerate(candidates):
            candidate["source_info"]["video_url"] = f"https://www.youtube.com/watch?v=perf{i}"
            result = self.workflow_manager.process_candidate(candidate)
            self.assertTrue(result.success)
            
        # 통계 조회
        stats = self.workflow_manager.get_workflow_statistics()
        self.assertEqual(stats["total_processed"], 5)
        self.assertEqual(stats["successful"], 5)
        self.assertGreater(stats["average_processing_time_ms"], 0)
        
    def test_filter_rule_management(self):
        """필터링 규칙 관리 테스트"""
        # 기본 규칙 확인
        rules_summary = self.workflow_manager.filter_engine.get_rules_summary()
        self.assertGreater(len(rules_summary), 0)
        
        # 규칙 제거 테스트
        remove_result = self.workflow_manager.filter_engine.remove_rule("non_existent_rule")
        self.assertFalse(remove_result)
        
    def test_error_handling(self):
        """오류 처리 테스트"""
        # 잘못된 데이터 구조
        invalid_candidate = {"invalid": "data"}
        
        result = self.workflow_manager.process_candidate(invalid_candidate)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        
        # 직접 워크플로우 오류 처리 검증
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        
    def test_prd_attractiveness_scoring(self):
        """PRD 매력도 스코어링 공식 테스트"""
        # PRD 공식: 총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
        calculator = PriorityCalculator()
        
        test_candidate = self.sample_candidate.copy()
        test_candidate["candidate_info"]["score_details"] = {
            "sentiment_score": 0.9,      # 감성 강도
            "endorsement_score": 0.8,    # 실사용 인증 강도  
            "influencer_score": 0.7,     # 인플루언서 신뢰도
            "total": 85  # 기존 총점 (참고용)
        }
        
        # PRD 공식 직접 계산
        expected_score = (0.50 * 0.9 + 0.35 * 0.8 + 0.15 * 0.7) * 100
        # = (0.45 + 0.28 + 0.105) * 100 = 83.5
        
        # 실제 구현 계산
        actual_score = calculator._calculate_prd_attractiveness_score(test_candidate)
        
        # 허용 오차 내에서 일치 확인
        self.assertAlmostEqual(actual_score, expected_score, places=1)
        
    def test_complex_workflow_scenario(self):
        """복합 워크플로우 시나리오 테스트"""
        scenarios = [
            {
                "name": "고득점_고신뢰도_후보",
                "modifications": {
                    ("candidate_info", "score_details", "total"): 92,
                    ("status_info", "ppl_confidence"): 0.05
                },
                "expected_status": CandidateStatus.NEEDS_REVIEW,
                "expected_priority": [PriorityLevel.URGENT, PriorityLevel.HIGH]
            },
            {
                "name": "중득점_중위험도_후보", 
                "modifications": {
                    ("candidate_info", "score_details", "total"): 68,
                    ("status_info", "ppl_confidence"): 0.45
                },
                "expected_status": CandidateStatus.PPL_REVIEW_REQUIRED,
                "expected_priority": [PriorityLevel.MEDIUM]
            },
            {
                "name": "저득점_수익화불가_후보",
                "modifications": {
                    ("candidate_info", "score_details", "total"): 35,
                    ("monetization_info", "is_coupang_product"): False
                },
                "expected_status": CandidateStatus.FILTERED_NO_COUPANG,
                "expected_priority": [PriorityLevel.LOW, PriorityLevel.MINIMAL]
            }
        ]
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                # 테스트 후보 생성
                candidate = self.sample_candidate.copy()
                
                # 수정 사항 적용
                for path, value in scenario["modifications"].items():
                    obj = candidate
                    for key in path[:-1]:
                        obj = obj[key]
                    obj[path[-1]] = value
                    
                # 워크플로우 실행
                result = self.workflow_manager.process_candidate(candidate)
                
                # 결과 검증
                self.assertTrue(result.success, f"Scenario {scenario['name']} failed")
                self.assertEqual(
                    result.state_transition.to_status,
                    scenario["expected_status"],
                    f"Unexpected status in {scenario['name']}"
                )
                self.assertIn(
                    result.priority_score.level,
                    scenario["expected_priority"],
                    f"Unexpected priority in {scenario['name']}"
                )


class TestWorkflowPerformance(unittest.TestCase):
    """워크플로우 성능 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.workflow_manager = WorkflowManager()
        
        # 표준 테스트 후보
        self.test_candidate = {
            "source_info": {
                "celebrity_name": "테스트연예인",
                "channel_name": "테스트채널",
                "video_title": "테스트 영상",
                "video_url": "https://www.youtube.com/watch?v=performance_test",
                "upload_date": "2025-06-22"
            },
            "candidate_info": {
                "product_name_ai": "테스트 제품",
                "clip_start_time": 100,
                "clip_end_time": 120,
                "score_details": {
                    "total": 75,
                    "sentiment_score": 0.8,
                    "endorsement_score": 0.7,
                    "influencer_score": 0.8
                }
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/performance_test"
            },
            "status_info": {
                "current_status": "analysis_complete",
                "is_ppl": False,
                "ppl_confidence": 0.2
            }
        }
        
    def test_single_candidate_performance(self):
        """단일 후보 처리 성능 테스트"""
        start_time = datetime.now()
        
        result = self.workflow_manager.process_candidate(self.test_candidate.copy())
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds() * 1000
        
        # 성공 검증
        self.assertTrue(result.success)
        
        # 성능 검증 (5초 이내)
        self.assertLess(processing_time, 5000, "Single candidate processing too slow")
        self.assertLess(result.processing_time_ms, 5000, "Measured processing time too slow")
        
    def test_batch_processing_performance(self):
        """배치 처리 성능 테스트"""
        batch_size = 10
        candidates = []
        
        # 테스트 후보들 생성
        for i in range(batch_size):
            candidate = self.test_candidate.copy()
            candidate["source_info"]["video_url"] = f"https://www.youtube.com/watch?v=perf_batch_{i}"
            candidates.append(candidate)
            
        start_time = datetime.now()
        
        batch_result = self.workflow_manager.process_candidates_batch(candidates, parallel=True)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds() * 1000
        
        # 성공 검증
        self.assertEqual(batch_result.successful, batch_size)
        self.assertEqual(batch_result.failed, 0)
        
        # 성능 검증
        avg_time_per_candidate = total_time / batch_size
        self.assertLess(avg_time_per_candidate, 2000, "Batch processing average too slow")
        
        # 병렬 처리 효과 검증 (순차 처리보다 빨라야 함)
        sequential_result = self.workflow_manager.process_candidates_batch(candidates, parallel=False)
        self.assertLess(
            batch_result.total_processing_time_ms,
            sequential_result.total_processing_time_ms * 0.8,
            "Parallel processing not faster than sequential"
        )
        
    def test_memory_usage(self):
        """메모리 사용량 테스트"""
        import psutil
        import os
        
        # 초기 메모리 사용량
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 대량 처리
        large_batch = [self.test_candidate.copy() for _ in range(50)]
        for i, candidate in enumerate(large_batch):
            candidate["source_info"]["video_url"] = f"https://www.youtube.com/watch?v=memory_test_{i}"
            
        batch_result = self.workflow_manager.process_candidates_batch(large_batch)
        
        # 최종 메모리 사용량
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 성공 검증
        self.assertEqual(batch_result.successful, 50)
        
        # 메모리 사용량 검증 (100MB 이내 증가)
        self.assertLess(memory_increase, 100, f"Memory usage increased too much: {memory_increase:.1f}MB")


if __name__ == '__main__':
    unittest.main()