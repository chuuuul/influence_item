#!/usr/bin/env python3
"""
샘플 데이터 생성 스크립트
T09_S01_M02 필터링된 제품 관리 기능 테스트를 위한 샘플 데이터
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dashboard.utils.database_manager import get_database_manager

def create_sample_candidates():
    """필터링된 제품들의 샘플 후보 데이터 생성"""
    
    # 연예인 채널 목록
    channels = [
        {"name": "홍지윤 Yoon", "subscriber_count": 850000},
        {"name": "아이유IU", "subscriber_count": 2300000},
        {"name": "이사배(RISABAE)", "subscriber_count": 1200000},
        {"name": "다영 DAYOUNG", "subscriber_count": 680000},
        {"name": "소이와여니", "subscriber_count": 920000},
        {"name": "윰댕Yummy D", "subscriber_count": 750000},
        {"name": "SEJEONG OFFICIAL", "subscriber_count": 1100000},
        {"name": "수린 SURIN", "subscriber_count": 450000}
    ]
    
    # 제품 카테고리별 문제 있는 제품들
    problem_products = {
        "스킨케어": [
            "그 브랜드 세럼", "화장품 가게에서 산 크림", "일본에서 구매한 토너", 
            "언니가 추천한 마스크", "면세점에서 산 에센스", "해외 직구 앰플"
        ],
        "메이크업": [
            "요즘 핫한 파운데이션", "인스타에서 본 틴트", "해외 직구 팔레트", 
            "브랜드명 모르는 컨실러", "한정판 립스틱", "아티스트 아이섀도"
        ],
        "헤어케어": [
            "미용실 전용 샴푸", "세일즈 샴푸", "외국 브랜드 트리트먼트", 
            "프로페셔널 헤어세럼", "살롱 케어 오일", "스타일리스트 추천템"
        ],
        "패션": [
            "작년에 산 후드티", "해외쇼핑몰 원피스", "온라인몰 데님", 
            "브랜드 불명 가디건", "빈티지 자켓", "디자이너 한정 드레스"
        ],
        "향수": [
            "면세점 향수", "해외 브랜드 향수", "리미티드 에디션 향수", 
            "단종된 향수", "아티스트 콜라보 향수", "프랑스 현지 구매"
        ]
    }
    
    # 필터링 사유들
    filter_reasons = [
        "쿠팡 API 검색 결과 없음",
        "브랜드명 불일치", 
        "단종된 제품",
        "해외 브랜드 (쿠팡 미취급)",
        "제품명 불분명",
        "가격 정보 부족",
        "카테고리 매칭 실패"
    ]
    
    candidates = []
    
    for i in range(120):  # 120개 샘플 생성
        channel = random.choice(channels)
        category = random.choice(list(problem_products.keys()))
        product_name = random.choice(problem_products[category])
        filter_reason = random.choice(filter_reasons)
        
        # 날짜 설정
        created_date = datetime.now() - timedelta(days=random.randint(1, 15))
        start_time = random.randint(60, 900)  # 1분 ~ 15분
        duration = random.randint(20, 180)    # 20초 ~ 3분
        
        # 매력도 점수 (필터링되었지만 나름 괜찮은 점수들)
        total_score = random.uniform(45, 85)
        sentiment_score = random.uniform(0.6, 0.9)
        endorsement_score = random.uniform(0.5, 0.8)
        influencer_score = random.uniform(0.7, 0.95)
        
        candidate_data = {
            "id": f"FILTERED_{i+1:03d}_{channel['name'][:3]}",
            "source_info": {
                "celebrity_name": channel['name'].split()[0],
                "channel_name": channel['name'],
                "video_title": f"[VLOG] {category} 솔직 리뷰 | 실패템 vs 성공템 #{i+1}",
                "video_url": f"https://www.youtube.com/watch?v=filtered_{i+1:03d}",
                "upload_date": created_date.strftime("%Y-%m-%d"),
                "subscriber_count": channel['subscriber_count'],
                "view_count": random.randint(8000, 200000)
            },
            "candidate_info": {
                "product_name_ai": product_name,
                "product_name_manual": None,
                "clip_start_time": start_time,
                "clip_end_time": start_time + duration,
                "category_path": [category, "기타"],
                "features": [
                    "사용감이 독특해요", 
                    "브랜드가 특이해요", 
                    "어디서 구했는지 궁금해요"
                ],
                "score_details": {
                    "total": round(total_score, 1),
                    "sentiment_score": round(sentiment_score, 2),
                    "endorsement_score": round(endorsement_score, 2),
                    "influencer_score": round(influencer_score, 2)
                },
                "hook_sentence": f"{channel['name']}이 추천하는 {product_name}?",
                "summary_for_caption": f"{channel['name']}님이 사용하는 {product_name}에 대한 솔직한 후기입니다.",
                "target_audience": ["20대 여성", "뷰티 관심층", "브랜드 탐험가"],
                "price_point": random.choice(["저가", "중가", "고가", "프리미엄"]),
                "endorsement_type": random.choice(["습관적 사용", "신규 발견", "재구매"]),
                "recommended_titles": [
                    f"{channel['name']}의 숨겨진 {category} 아이템!",
                    f"이 제품 진짜 대박! {product_name} 리뷰",
                    f"{category} 고수가 쓰는 특별한 제품"
                ],
                "recommended_hashtags": [
                    f"#{channel['name'].replace(' ', '')}", 
                    f"#{category}", 
                    "#숨겨진템", 
                    "#특별한제품",
                    "#리뷰", 
                    "#추천"
                ]
            },
            "monetization_info": {
                "is_coupang_product": False,
                "coupang_url_ai": None,
                "coupang_url_manual": None,
                "search_failed_reason": filter_reason,
                "alternative_platforms": ["네이버쇼핑", "11번가", "G마켓"],
                "estimated_price_range": f"{random.randint(10, 100)}천원 ~ {random.randint(100, 500)}천원"
            },
            "status_info": {
                "current_status": random.choice([
                    "needs_review", "approved", "filtered_no_coupang", 
                    "rejected", "in_review", "pending_monetization"
                ]),
                "is_ppl": random.choice([True, False]),
                "ppl_confidence": round(random.uniform(0.05, 0.85), 2),
                "filter_category": random.choice(["monetization_failed", "quality_check", "ppl_detected", "manual_review"]),
                "filter_reason": filter_reason if random.random() < 0.3 else None,
                "created_at": created_date.isoformat(),
                "updated_at": created_date.isoformat(),
                "updated_by": random.choice(["ai_system", "human_reviewer", "admin"]),
                "manual_review_needed": random.choice([True, False]),
                "priority_score": round(total_score * random.uniform(0.8, 1.2), 1)
            }
        }
        
        candidates.append(candidate_data)
    
    return candidates

def populate_database():
    """데이터베이스에 샘플 데이터 추가"""
    print("🔄 샘플 데이터 생성 중...")
    
    try:
        db_manager = get_database_manager()
        candidates = create_sample_candidates()
        
        success_count = 0
        for candidate in candidates:
            if db_manager.save_candidate(candidate):
                success_count += 1
                print(f"✅ 저장됨: {candidate['candidate_info']['product_name_ai']} ({candidate['source_info']['channel_name']})")
            else:
                print(f"❌ 실패: {candidate['candidate_info']['product_name_ai']}")
        
        print(f"\n📊 완료: {success_count}/{len(candidates)}개 샘플 데이터 저장")
        
        # 통계 정보 출력
        stats = db_manager.get_status_statistics()
        print(f"\n📈 데이터베이스 통계:")
        print(f"  - 전체 후보: {stats.get('total_candidates', 0)}개")
        print(f"  - 필터링된 제품: {stats.get('status_distribution', {}).get('filtered_no_coupang', 0)}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False

if __name__ == "__main__":
    print("🚀 T09_S01_M02 필터링된 제품 관리 - 샘플 데이터 생성")
    print("=" * 60)
    
    if populate_database():
        print("\n✅ 샘플 데이터 생성 완료!")
        print("이제 대시보드에서 필터링된 제품 관리 기능을 테스트할 수 있습니다.")
        print("\n실행 방법:")
        print("  python run_dashboard.py")
        print("  -> '🔍 필터링된 제품' 페이지에서 확인")
    else:
        print("\n❌ 샘플 데이터 생성 실패")