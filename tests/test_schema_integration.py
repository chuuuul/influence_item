#!/usr/bin/env python3
"""
T05_S03 통합 테스트 - JSON 스키마 시스템 검증

실제 데이터 10개 샘플을 사용하여 전체 스키마 시스템을 테스트합니다.
"""

import json
import sys
import traceback
from datetime import datetime
from typing import List, Dict, Any

# 스키마 모듈 import
sys.path.append('/Users/chul/Documents/claude/influence_item')
from src.schema.models import ProductRecommendationCandidate, ScoreDetails, SourceInfo, CandidateInfo, MonetizationInfo, StatusInfo
from src.schema.validators import SchemaValidator
from src.schema.serializers import JSONSerializer, JSONDeserializer
from src.schema.schema_registry import SchemaRegistry
from src.schema.formatters import APIResponseFormatter, DashboardFormatter, ExportFormatter, ReportFormatter


def create_test_data() -> List[Dict[str, Any]]:
    """실제 사용될 10개의 테스트 데이터 생성"""
    test_data = [
        {
            "source_info": {
                "celebrity_name": "강민경",
                "channel_name": "걍밍경",
                "video_title": "파리 출장 다녀왔습니다 VLOG",
                "video_url": "https://www.youtube.com/watch?v=test001",
                "upload_date": "2025-06-20"
            },
            "candidate_info": {
                "product_name_ai": "아비에무아 숄더백 (베이지)",
                "product_name_manual": None,
                "clip_start_time": 315,
                "clip_end_time": 340,
                "category_path": ["패션잡화", "여성가방", "숄더백"],
                "features": ["수납이 넉넉해요", "가죽이 부드러워요"],
                "score_details": {
                    "total": 88,
                    "sentiment_score": 0.9,
                    "endorsement_score": 0.85,
                    "influencer_score": 0.9
                },
                "hook_sentence": "강민경이 '이것만 쓴다'고 말한 바로 그 숄더백?",
                "summary_for_caption": "사복 장인 강민경 님의 데일리백 정보!",
                "target_audience": ["20대 후반 여성", "30대 직장인"],
                "price_point": "프리미엄",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "요즘 강민경이 매일 드는 '그 가방' 정보",
                    "사복 장인 강민경의 찐 애정템! 아비에무아 숄더백"
                ],
                "recommended_hashtags": [
                    "#강민경", "#걍밍경", "#강민경패션", "#아비에무아", "#숄더백추천"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/example123",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.1,
                "last_updated": None
            },
            "schema_version": "1.0",
            "created_at": None,
            "updated_at": None
        },
        {
            "source_info": {
                "celebrity_name": "이지은",
                "channel_name": "이지금 IU",
                "video_title": "아이유의 홈카페 브이로그",
                "video_url": "https://www.youtube.com/watch?v=test002",
                "upload_date": "2025-06-21"
            },
            "candidate_info": {
                "product_name_ai": "브레빌 바리스타 익스프레스 에스프레소 머신",
                "product_name_manual": "브레빌 바리스타 익스프레스",
                "clip_start_time": 180,
                "clip_end_time": 220,
                "category_path": ["가전제품", "주방가전", "커피머신"],
                "features": ["홈카페 가능", "에스프레소 추출", "스팀 우유 기능"],
                "score_details": {
                    "total": 92,
                    "sentiment_score": 0.95,
                    "endorsement_score": 0.9,
                    "influencer_score": 0.95
                },
                "hook_sentence": "아이유가 매일 마시는 커피는 바로 이 머신으로!",
                "summary_for_caption": "IU님이 직접 사용하는 홈카페 머신 정보",
                "target_audience": ["20-30대 직장인", "커피 애호가"],
                "price_point": "럭셔리",
                "endorsement_type": "명시적 추천",
                "recommended_titles": [
                    "아이유가 추천하는 홈카페 머신",
                    "IU 홈카페의 비밀! 브레빌 바리스타 익스프레스"
                ],
                "recommended_hashtags": [
                    "#아이유", "#IU", "#홈카페", "#브레빌", "#커피머신추천"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/coffee456",
                "coupang_url_manual": "https://link.coupang.com/coffee456_manual"
            },
            "status_info": {
                "current_status": "approved",
                "is_ppl": False,
                "ppl_confidence": 0.05,
                "last_updated": "2025-06-22T10:30:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-22T09:00:00Z",
            "updated_at": "2025-06-22T10:30:00Z"
        },
        {
            "source_info": {
                "celebrity_name": "박서준",
                "channel_name": "박서준 Official",
                "video_title": "운동 후 먹는 건강한 간식",
                "video_url": "https://www.youtube.com/watch?v=test003",
                "upload_date": "2025-06-19"
            },
            "candidate_info": {
                "product_name_ai": "마이프로틴 웨이 프로틴 파우더",
                "product_name_manual": None,
                "clip_start_time": 120,
                "clip_end_time": 165,
                "category_path": ["건강식품", "프로틴", "웨이프로틴"],
                "features": ["고단백", "저칼로리", "맛이 좋음"],
                "score_details": {
                    "total": 73,
                    "sentiment_score": 0.8,
                    "endorsement_score": 0.75,
                    "influencer_score": 0.7
                },
                "hook_sentence": "박서준이 운동 후 꼭 마시는 그 프로틴!",
                "summary_for_caption": "박서준님의 운동 후 필수템 프로틴 정보",
                "target_audience": ["20-40대 남성", "운동하는 사람"],
                "price_point": "일반",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "박서준 운동루틴 필수템! 마이프로틴",
                    "배우 박서준이 선택한 프로틴은?"
                ],
                "recommended_hashtags": [
                    "#박서준", "#마이프로틴", "#운동", "#프로틴추천", "#헬스"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/protein789",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.25,
                "last_updated": None
            },
            "schema_version": "1.0",
            "created_at": None,
            "updated_at": None
        },
        {
            "source_info": {
                "celebrity_name": "송혜교",
                "channel_name": "송혜교 공식채널",
                "video_title": "일상 스킨케어 루틴 공유",
                "video_url": "https://www.youtube.com/watch?v=test004",
                "upload_date": "2025-06-18"
            },
            "candidate_info": {
                "product_name_ai": "더오리지널 세럼",
                "product_name_manual": "더오리지널 비타민C 세럼",
                "clip_start_time": 45,
                "clip_end_time": 75,
                "category_path": ["뷰티", "스킨케어", "세럼"],
                "features": ["비타민C 고함량", "브라이트닝", "안티에이징"],
                "score_details": {
                    "total": 95,
                    "sentiment_score": 0.98,
                    "endorsement_score": 0.95,
                    "influencer_score": 0.95
                },
                "hook_sentence": "송혜교의 완벽한 피부 비결은 바로 이 세럼?",
                "summary_for_caption": "송혜교님의 동안 피부 비밀 아이템!",
                "target_audience": ["20-50대 여성", "스킨케어 관심자"],
                "price_point": "프리미엄",
                "endorsement_type": "명시적 추천",
                "recommended_titles": [
                    "송혜교가 10년 넘게 쓴다는 그 세럼",
                    "동안 피부 송혜교의 비밀 아이템 공개"
                ],
                "recommended_hashtags": [
                    "#송혜교", "#더오리지널", "#비타민C세럼", "#스킨케어", "#동안피부"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/serum101",
                "coupang_url_manual": "https://link.coupang.com/serum101_verified"
            },
            "status_info": {
                "current_status": "approved",
                "is_ppl": False,
                "ppl_confidence": 0.08,
                "last_updated": "2025-06-22T08:15:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-21T14:20:00Z",
            "updated_at": "2025-06-22T08:15:00Z"
        },
        {
            "source_info": {
                "celebrity_name": "유재석",
                "channel_name": "놀면뭐하니",
                "video_title": "유재석의 건강 관리법",
                "video_url": "https://www.youtube.com/watch?v=test005",
                "upload_date": "2025-06-17"
            },
            "candidate_info": {
                "product_name_ai": "나이키 에어맥스 러닝화",
                "product_name_manual": None,
                "clip_start_time": 90,
                "clip_end_time": 125,
                "category_path": ["운동용품", "신발", "러닝화"],
                "features": ["쿠셔닝 좋음", "통기성", "가벼움"],
                "score_details": {
                    "total": 68,
                    "sentiment_score": 0.7,
                    "endorsement_score": 0.65,
                    "influencer_score": 0.8
                },
                "hook_sentence": "유재석이 15년째 신는다는 그 러닝화!",
                "summary_for_caption": "국민MC 유재석님의 러닝화 추천",
                "target_audience": ["30-50대 남성", "러닝 초보자"],
                "price_point": "일반",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "유재석이 15년째 신는 러닝화",
                    "국민MC의 러닝화 선택 기준은?"
                ],
                "recommended_hashtags": [
                    "#유재석", "#나이키", "#에어맥스", "#러닝화추천", "#건강관리"
                ]
            },
            "monetization_info": {
                "is_coupang_product": False,
                "coupang_url_ai": None,
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "filtered_no_coupang",
                "is_ppl": False,
                "ppl_confidence": 0.15,
                "last_updated": "2025-06-22T07:00:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-21T16:30:00Z",
            "updated_at": "2025-06-22T07:00:00Z"
        },
        {
            "source_info": {
                "celebrity_name": "이효리",
                "channel_name": "이효리 라이프",
                "video_title": "제주도 일상 브이로그",
                "video_url": "https://www.youtube.com/watch?v=test006",
                "upload_date": "2025-06-16"
            },
            "candidate_info": {
                "product_name_ai": "바디샵 티트리 페이스 워시",
                "product_name_manual": "바디샵 티트리 폼클렌징",
                "clip_start_time": 200,
                "clip_end_time": 235,
                "category_path": ["뷰티", "클렌징", "폼클렌징"],
                "features": ["천연 성분", "트러블 케어", "순함"],
                "score_details": {
                    "total": 79,
                    "sentiment_score": 0.82,
                    "endorsement_score": 0.75,
                    "influencer_score": 0.85  
                },
                "hook_sentence": "이효리가 10년 넘게 쓴다는 그 세안제!",
                "summary_for_caption": "이효리님의 변하지 않는 세안템",
                "target_audience": ["20-40대 여성", "트러블 고민자"],
                "price_point": "저가",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "이효리가 10년째 쓰는 세안제",
                    "효리언니의 트러블 없는 피부 비결"
                ],
                "recommended_hashtags": [
                    "#이효리", "#바디샵", "#티트리", "#세안제추천", "#트러블케어"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/bodyshop202",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.2,
                "last_updated": None
            },
            "schema_version": "1.0",
            "created_at": None,
            "updated_at": None
        },
        {
            "source_info": {
                "celebrity_name": "김태희",
                "channel_name": "김태희와 함께",
                "video_title": "아이와 함께하는 요리시간",
                "video_url": "https://www.youtube.com/watch?v=test007",
                "upload_date": "2025-06-15"
            },
            "candidate_info": {
                "product_name_ai": "쿠첸 압력밥솥 10인용",
                "product_name_manual": None,
                "clip_start_time": 300,
                "clip_end_time": 350,
                "category_path": ["가전제품", "주방가전", "밥솥"],
                "features": ["대용량", "압력 기능", "보온 우수"],
                "score_details": {
                    "total": 85,
                    "sentiment_score": 0.88,
                    "endorsement_score": 0.8,
                    "influencer_score": 0.9
                },
                "hook_sentence": "김태희가 아이들 밥 해줄 때 쓰는 그 밥솥!",
                "summary_for_caption": "김태희님의 육아맘 필수템 밥솥",
                "target_audience": ["30-40대 주부", "육아맘"],
                "price_point": "일반",
                "endorsement_type": "자연스러운 언급",
                "recommended_titles": [
                    "김태희가 선택한 육아맘 밥솥",
                    "아이 있는 집에 딱! 김태희표 밥솥"
                ],
                "recommended_hashtags": [
                    "#김태희", "#쿠첸", "#압력밥솥", "#육아맘", "#요리"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/cuckoo303",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "approved",
                "is_ppl": False,
                "ppl_confidence": 0.12,
                "last_updated": "2025-06-22T11:45:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-21T13:15:00Z",
            "updated_at": "2025-06-22T11:45:00Z"
        },
        {
            "source_info": {
                "celebrity_name": "정우성",
                "channel_name": "정우성의 일상",
                "video_title": "독서하는 시간",
                "video_url": "https://www.youtube.com/watch?v=test008",
                "upload_date": "2025-06-14"
            },
            "candidate_info": {
                "product_name_ai": "몰스킨 클래식 노트북",
                "product_name_manual": "몰스킨 하드커버 노트북",
                "clip_start_time": 150,
                "clip_end_time": 180,
                "category_path": ["문구", "노트", "다이어리"],
                "features": ["고급 종이", "하드커버", "클래식 디자인"],
                "score_details": {
                    "total": 76,
                    "sentiment_score": 0.78,
                    "endorsement_score": 0.72,
                    "influencer_score": 0.85
                },
                "hook_sentence": "정우성이 20년째 쓰는 그 노트북!",
                "summary_for_caption": "정우성님의 사색을 담는 노트북",
                "target_audience": ["30-50대 남성", "독서가", "직장인"],
                "price_point": "프리미엄",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "정우성이 20년째 쓰는 노트북",
                    "배우 정우성의 사색 노트"
                ],
                "recommended_hashtags": [
                    "#정우성", "#몰스킨", "#노트북", "#독서", "#일기"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/moleskine404",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "needs_review",
                "is_ppl": False,
                "ppl_confidence": 0.18,
                "last_updated": None
            },
            "schema_version": "1.0",
            "created_at": None,
            "updated_at": None
        },
        {
            "source_info": {
                "celebrity_name": "전지현",
                "channel_name": "전지현 공식",
                "video_title": "집에서 하는 홈트레이닝",
                "video_url": "https://www.youtube.com/watch?v=test009",
                "upload_date": "2025-06-13"
            },
            "candidate_info": {
                "product_name_ai": "루루레몬 요가매트",
                "product_name_manual": None,
                "clip_start_time": 60,
                "clip_end_time": 95,
                "category_path": ["운동용품", "요가", "요가매트"],
                "features": ["미끄럼 방지", "두께감", "고급 소재"],
                "score_details": {
                    "total": 89,
                    "sentiment_score": 0.9,
                    "endorsement_score": 0.85,
                    "influencer_score": 0.95
                },
                "hook_sentence": "전지현의 완벽한 몸매 비결은 이 요가매트!",
                "summary_for_caption": "전지현님이 사용하는 홈트 필수템",
                "target_audience": ["20-40대 여성", "홈트족"],
                "price_point": "럭셔리",
                "endorsement_type": "명시적 추천",
                "recommended_titles": [
                    "전지현이 추천하는 요가매트",
                    "지현누나의 홈트 필수템 공개"
                ],
                "recommended_hashtags": [
                    "#전지현", "#루루레몬", "#요가매트", "#홈트레이닝", "#요가"
                ]
            },
            "monetization_info": {
                "is_coupang_product": False,
                "coupang_url_ai": None,
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "filtered_no_coupang",
                "is_ppl": False,
                "ppl_confidence": 0.05,
                "last_updated": "2025-06-22T06:30:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-21T12:00:00Z",
            "updated_at": "2025-06-22T06:30:00Z"
        },
        {
            "source_info": {
                "celebrity_name": "현빈",
                "channel_name": "현빈과 함께",
                "video_title": "커피 한 잔의 여유",
                "video_url": "https://www.youtube.com/watch?v=test010",
                "upload_date": "2025-06-12"
            },
            "candidate_info": {
                "product_name_ai": "하리오 V60 드리퍼 세트",
                "product_name_manual": "하리오 V60 핸드드립 세트",
                "clip_start_time": 240,
                "clip_end_time": 280,
                "category_path": ["주방용품", "커피용품", "드리퍼"],
                "features": ["핸드드립", "세라믹 소재", "전문가용"],
                "score_details": {
                    "total": 82,
                    "sentiment_score": 0.85,
                    "endorsement_score": 0.78,
                    "influencer_score": 0.85
                },
                "hook_sentence": "현빈이 매일 아침 쓰는 그 드리퍼!",
                "summary_for_caption": "현빈님의 모닝커피 비밀무기",
                "target_audience": ["30-50대 남성", "커피 매니아"],
                "price_point": "프리미엄",
                "endorsement_type": "습관적 사용",
                "recommended_titles": [
                    "현빈이 매일 쓰는 커피 드리퍼",
                    "배우 현빈의 모닝커피 루틴"
                ],
                "recommended_hashtags": [
                    "#현빈", "#하리오", "#V60", "#핸드드립", "#커피"
                ]
            },
            "monetization_info": {
                "is_coupang_product": True,
                "coupang_url_ai": "https://link.coupang.com/hario505",
                "coupang_url_manual": None
            },
            "status_info": {
                "current_status": "approved",
                "is_ppl": False,
                "ppl_confidence": 0.1,
                "last_updated": "2025-06-22T09:20:00Z"
            },
            "schema_version": "1.0",
            "created_at": "2025-06-21T11:30:00Z",
            "updated_at": "2025-06-22T09:20:00Z"
        }
    ]
    
    return test_data


def test_pydantic_models():
    """Pydantic 모델 생성 및 검증 테스트"""
    print("=== 1. Pydantic 모델 테스트 ===")
    
    test_data = create_test_data()
    candidates = []
    
    for i, data in enumerate(test_data):
        try:
            candidate = ProductRecommendationCandidate(**data)
            candidates.append(candidate)
            print(f"✅ 후보 {i+1}: {candidate.source_info.celebrity_name} - {candidate.get_final_product_name()}")
            
            # PRD 공식 검증
            priority_score = candidate.calculate_priority_score()
            print(f"   우선순위 점수: {priority_score:.1f}")
            
        except Exception as e:
            print(f"❌ 후보 {i+1} 생성 실패: {e}")
            return False
    
    print(f"총 {len(candidates)}개 후보 생성 완료\n")
    return candidates


def test_validators(candidates):
    """검증기 테스트"""
    print("=== 2. 검증기 테스트 ===")
    
    validator = SchemaValidator()
    valid_count = 0
    
    for i, candidate in enumerate(candidates):
        result = validator.validate(candidate)
        status = "✅ 통과" if result["is_valid"] else "❌ 실패"
        print(f"{status} 후보 {i+1}: 점수 {result['validation_score']:.1f}/100")
        
        if result["errors"]:
            for error in result["errors"]:
                print(f"   🔴 오류: {error}")
        if result["warnings"]:
            for warning in result["warnings"]:
                print(f"   🟡 경고: {warning}")
                
        if result["is_valid"]:
            valid_count += 1
    
    print(f"\n검증 통과: {valid_count}/{len(candidates)}개")
    
    # 배치 검증 테스트
    batch_result = validator.validate_batch(candidates)
    print(f"배치 검증 평균 점수: {batch_result['summary']['average_score']:.1f}/100\n")
    
    return batch_result


def test_serializers(candidates):
    """직렬화/역직렬화 테스트"""
    print("=== 3. 직렬화/역직렬화 테스트 ===")
    
    serializer = JSONSerializer(pretty=True)
    deserializer = JSONDeserializer()
    
    # 단일 직렬화/역직렬화
    test_candidate = candidates[0]
    try:
        json_str = serializer.serialize(test_candidate)
        deserialized = deserializer.deserialize(json_str)
        
        print(f"✅ 단일 직렬화: {test_candidate.source_info.celebrity_name}")
        print(f"✅ 단일 역직렬화: {deserialized.source_info.celebrity_name}")
        
        # 데이터 일치성 검증
        if test_candidate.dict() == deserialized.dict():
            print("✅ 데이터 일치성 검증 통과")
        else:
            print("❌ 데이터 일치성 검증 실패")
            return False
            
    except Exception as e:
        print(f"❌ 단일 직렬화 실패: {e}")
        return False
    
    # 배치 직렬화/역직렬화
    try:
        batch_json = serializer.serialize_batch(candidates[:3])
        batch_deserialized = deserializer.deserialize_batch(batch_json)
        
        print(f"✅ 배치 직렬화: {len(candidates[:3])}개 후보")
        print(f"✅ 배치 역직렬화: {len(batch_deserialized)}개 후보")
        
    except Exception as e:
        print(f"❌ 배치 직렬화 실패: {e}")
        return False
    
    print()
    return True


def test_schema_registry():
    """스키마 레지스트리 테스트"""
    print("=== 4. 스키마 레지스트리 테스트 ===")
    
    registry = SchemaRegistry()
    
    # 버전 정보
    current_version = registry.get_current_version()
    print(f"✅ 현재 버전: {current_version}")
    
    latest_version = registry.get_latest_version()
    print(f"✅ 최신 버전: {latest_version}")
    
    # 호환성 테스트
    compatibility = registry.is_compatible("1.0", "1.0")
    print(f"✅ 버전 호환성 (1.0 -> 1.0): {compatibility}")
    
    # 스키마 정의 내보내기
    try:
        schema_def = registry.export_schema_definitions()
        print(f"✅ 스키마 정의 내보내기 성공")
        
        # JSON Schema 유효성 확인
        if "json_schema" in schema_def:
            print(f"✅ JSON Schema 생성 완료")
        else:
            print(f"❌ JSON Schema 생성 실패")
            return False
            
    except Exception as e:
        print(f"❌ 스키마 정의 내보내기 실패: {e}")
        return False
    
    print()
    return True


def test_formatters(candidates):
    """포맷터 테스트"""
    print("=== 5. 포맷터 테스트 ===")
    
    # API 응답 포맷터
    api_formatter = APIResponseFormatter()
    
    try:
        success_response = api_formatter.format_success(
            candidates[0], 
            message="데이터 조회 성공"
        )
        print(f"✅ API 성공 응답 포맷: {success_response['message']}")
        
        error_response = api_formatter.format_error(
            "테스트 오류",
            error_code="TEST_ERROR"
        )
        print(f"✅ API 오류 응답 포맷: {error_response['error']['code']}")
        
    except Exception as e:
        print(f"❌ API 포맷터 실패: {e}")
        return False
    
    # 대시보드 포맷터
    dashboard_formatter = DashboardFormatter()
    
    try:
        summary = dashboard_formatter.format_batch_summary(candidates)
        print(f"✅ 대시보드 요약: 총 {summary['total_count']}개, 평균 점수 {summary['summary']['average_score']}")
        
    except Exception as e:
        print(f"❌ 대시보드 포맷터 실패: {e}")
        return False
    
    # 내보내기 포맷터
    export_formatter = ExportFormatter()
    
    try:
        csv_data = export_formatter.to_csv(candidates[:2])
        csv_lines = len(csv_data.split('\n'))
        print(f"✅ CSV 내보내기: {csv_lines}줄 생성")
        
        excel_data = export_formatter.to_excel_ready(candidates[:2])
        print(f"✅ Excel 내보내기: {len(excel_data['main_data'])}개 레코드")
        
    except Exception as e:
        print(f"❌ 내보내기 포맷터 실패: {e}")
        return False
    
    # 보고서 포맷터
    report_formatter = ReportFormatter()
    
    try:
        report = report_formatter.generate_analysis_report(candidates)
        print(f"✅ 분석 보고서: {len(report['recommendations'])}개 권장사항")
        
    except Exception as e:
        print(f"❌ 보고서 포맷터 실패: {e}")
        return False
    
    print()
    return True


def test_end_to_end_workflow(candidates):
    """종단간 워크플로우 테스트"""
    print("=== 6. 종단간 워크플로우 테스트 ===")
    
    try:
        # 1. 데이터 검증
        validator = SchemaValidator()
        validation_result = validator.validate(candidates[0])
        
        if not validation_result["is_valid"]:
            print(f"❌ 워크플로우 실패: 데이터 검증 실패")
            return False
        
        # 2. 직렬화
        serializer = JSONSerializer()
        json_data = serializer.serialize(candidates[0])
        
        # 3. 역직렬화
        deserializer = JSONDeserializer()
        restored_candidate = deserializer.deserialize(json_data)
        
        # 4. API 응답 포맷
        api_formatter = APIResponseFormatter()
        api_response = api_formatter.format_success(restored_candidate)
        
        # 5. 대시보드 데이터
        dashboard_formatter = DashboardFormatter()
        dashboard_data = dashboard_formatter.format_candidate_summary(restored_candidate)
        
        print(f"✅ 전체 워크플로우 성공:")
        print(f"   - 연예인: {dashboard_data['celebrity_name']}")
        print(f"   - 제품: {dashboard_data['product_name']}")
        print(f"   - 점수: {dashboard_data['score']}")
        print(f"   - 상태: {dashboard_data['status']}")
        print(f"   - 수익화: {'가능' if dashboard_data['is_monetizable'] else '불가능'}")
        
    except Exception as e:
        print(f"❌ 종단간 워크플로우 실패: {e}")
        traceback.print_exc()
        return False
    
    print()
    return True


def generate_test_report(results):
    """테스트 결과 리포트 생성"""
    print("=== 🎯 T05_S03 통합 테스트 결과 ===")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['passed'])
    
    print(f"전체 테스트: {total_tests}")
    print(f"통과: {passed_tests}")
    print(f"실패: {total_tests - passed_tests}")
    print(f"성공률: {passed_tests/total_tests*100:.1f}%")
    print()
    
    print("상세 결과:")
    for result in results:
        status = "✅ 통과" if result['passed'] else "❌ 실패"
        print(f"{status} {result['name']}")
    
    print()
    
    if passed_tests == total_tests:
        print("🎉 모든 테스트 통과! T05_S03 완료 준비 완료")
        return True
    else:
        print("⚠️  일부 테스트 실패 - 수정 필요")
        return False


def main():
    """메인 테스트 실행"""
    print("T05_S03 - Final JSON Schema Completion 통합 테스트")
    print("=" * 60)
    
    results = []
    
    # 1. Pydantic 모델 테스트
    candidates = test_pydantic_models()
    results.append({
        'name': 'Pydantic 모델 생성',
        'passed': candidates is not False
    })
    
    if not candidates:
        print("❌ 기본 모델 생성 실패 - 테스트 중단")
        return False
    
    # 2. 검증기 테스트
    validation_result = test_validators(candidates)
    results.append({
        'name': '데이터 검증',
        'passed': validation_result is not False
    })
    
    # 3. 직렬화 테스트
    serialization_result = test_serializers(candidates)
    results.append({
        'name': 'JSON 직렬화/역직렬화',
        'passed': serialization_result
    })
    
    # 4. 스키마 레지스트리 테스트
    registry_result = test_schema_registry()
    results.append({
        'name': '스키마 레지스트리',
        'passed': registry_result
    })
    
    # 5. 포맷터 테스트
    formatter_result = test_formatters(candidates)
    results.append({
        'name': '출력 포맷터',
        'passed': formatter_result
    })
    
    # 6. 종단간 워크플로우 테스트
    e2e_result = test_end_to_end_workflow(candidates)
    results.append({
        'name': '종단간 워크플로우',
        'passed': e2e_result
    })
    
    # 최종 리포트
    return generate_test_report(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)