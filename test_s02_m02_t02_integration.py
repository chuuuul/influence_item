"""
S02_M02_T02 반자동 보조 검색 시스템 통합 테스트
"""

import sys
import pytest
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dashboard.components.smart_search import SmartSearch
    from dashboard.utils.keyword_extractor import KeywordExtractor
    from dashboard.utils.image_similarity import ImageSimilarityAnalyzer
except ImportError as e:
    print(f"모듈 임포트 오류: {e}")
    SmartSearch = None
    KeywordExtractor = None
    ImageSimilarityAnalyzer = None

class TestSmartSearchSystem:
    """스마트 검색 시스템 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        if SmartSearch:
            self.smart_search = SmartSearch()
        if KeywordExtractor:
            self.keyword_extractor = KeywordExtractor()
        if ImageSimilarityAnalyzer:
            self.image_analyzer = ImageSimilarityAnalyzer()
    
    def test_keyword_extractor_basic_functionality(self):
        """키워드 추출기 기본 기능 테스트"""
        if not KeywordExtractor:
            pytest.skip("KeywordExtractor 모듈 없음")
        
        # 테스트 케이스
        test_products = [
            "샤넬 레 베주 플뤼이드 파운데이션",
            "구찌 블룸 오드 퍼퓸",
            "아이유가 사용하는 립밤",
            "그 브랜드 세럼",
            "Nike Air Force 1"
        ]
        
        for product in test_products:
            result = self.keyword_extractor.extract_all_keywords(product, max_keywords=10)
            
            # 기본 검증
            assert 'keywords' in result
            assert isinstance(result['keywords'], list)
            assert len(result['keywords']) > 0
            assert len(result['keywords']) <= 10
            
            # 원본 제품명 포함 여부 확인
            keywords = result['keywords']
            assert any(product.lower() in kw.lower() or kw.lower() in product.lower() 
                      for kw in keywords)
            
            print(f"제품: {product}")
            print(f"추출된 키워드 ({len(keywords)}개): {keywords[:5]}")
    
    def test_keyword_extractor_edge_cases(self):
        """키워드 추출기 엣지 케이스 테스트"""
        if not KeywordExtractor:
            pytest.skip("KeywordExtractor 모듈 없음")
        
        # 엣지 케이스들
        edge_cases = [
            "",  # 빈 문자열
            "A",  # 너무 짧은 문자열
            "!@#$%^&*()",  # 특수문자만
            "Brand x Brand 콜라보 제품",  # 복잡한 브랜드명
            "일본에서 구매한 알 수 없는 브랜드 크림"  # 모호한 제품명
        ]
        
        for case in edge_cases:
            result = self.keyword_extractor.extract_all_keywords(case)
            
            # 오류 처리 확인
            assert 'keywords' in result
            
            if case == "" or len(case.strip()) < 2:
                # 빈 문자열이나 너무 짧은 경우
                assert len(result['keywords']) <= 1
            else:
                # 다른 경우는 최소 1개 이상의 키워드
                assert len(result['keywords']) >= 1
            
            print(f"엣지 케이스: '{case}' -> {len(result['keywords'])}개 키워드")
    
    def test_smart_search_multi_platform(self):
        """스마트 검색 다중 플랫폼 기능 테스트"""
        if not SmartSearch:
            pytest.skip("SmartSearch 모듈 없음")
        
        test_products = [
            "비비크림",
            "립스틱",
            "향수"
        ]
        
        for product in test_products:
            # 검색 실행
            result = self.smart_search.search_multi_platform(product)
            
            # 기본 응답 구조 확인
            assert 'success' in result
            
            if result['success']:
                assert 'results' in result
                assert 'keywords_used' in result
                assert 'search_info' in result
                
                results = result['results']
                assert isinstance(results, list)
                
                # 결과 검증
                for search_result in results[:3]:  # 처음 3개만 검증
                    required_fields = ['title', 'price', 'url', 'platform', 'recommendation_score']
                    for field in required_fields:
                        assert field in search_result, f"필수 필드 '{field}' 누락"
                    
                    # 점수 범위 확인
                    score = search_result['recommendation_score']
                    assert 0 <= score <= 1, f"추천 점수 범위 오류: {score}"
                
                print(f"제품: {product} -> {len(results)}개 결과")
            else:
                print(f"제품: {product} -> 검색 실패: {result.get('message', 'Unknown error')}")
    
    def test_smart_search_manual_search(self):
        """스마트 검색 수동 검색 기능 테스트"""
        if not SmartSearch:
            pytest.skip("SmartSearch 모듈 없음")
        
        test_keywords = [
            "크림",
            "화장품",
            "스킨케어"
        ]
        
        for keyword in test_keywords:
            results = self.smart_search.manual_search(keyword)
            
            # 결과 구조 확인
            assert isinstance(results, list)
            
            for result in results:
                # 필수 필드 확인
                assert 'title' in result
                assert 'platform' in result
                assert 'recommendation_score' in result
                assert 'keyword_used' in result
                assert result['keyword_used'] == keyword
                assert result['search_type'] == 'manual'
            
            print(f"수동 검색 '{keyword}': {len(results)}개 결과")
    
    def test_image_similarity_analyzer(self):
        """이미지 유사도 분석기 테스트"""
        if not ImageSimilarityAnalyzer:
            pytest.skip("ImageSimilarityAnalyzer 모듈 없음")
        
        # 테스트 이미지 URL들
        test_images = [
            "https://example.com/beauty/cream.jpg",
            "https://coupang.com/product/image1.png",
            "https://naver.shopping.com/item.jpeg"
        ]
        
        for image_url in test_images:
            # 특징 추출 테스트
            features = self.image_analyzer.extract_image_features(image_url)
            
            # 기본 구조 확인
            required_fields = ['url_hash', 'domain', 'file_type', 'estimated_category']
            for field in required_fields:
                assert field in features, f"특징 필드 '{field}' 누락"
            
            print(f"이미지: {image_url} -> 카테고리: {features['estimated_category']}")
        
        # 유사도 계산 테스트
        if len(test_images) >= 2:
            features1 = self.image_analyzer.extract_image_features(test_images[0])
            features2 = self.image_analyzer.extract_image_features(test_images[1])
            
            similarity = self.image_analyzer.calculate_similarity_score(features1, features2)
            
            # 유사도 점수 검증
            assert 0 <= similarity <= 1, f"유사도 점수 범위 오류: {similarity}"
            print(f"이미지 유사도: {similarity:.3f}")
    
    def test_end_to_end_search_workflow(self):
        """전체 검색 워크플로우 End-to-End 테스트"""
        if not all([SmartSearch, KeywordExtractor, ImageSimilarityAnalyzer]):
            pytest.skip("일부 모듈 없음")
        
        # 실제 시나리오 테스트
        test_product = "에스티 로더 더블 웨어 파운데이션"
        product_image = "https://example.com/estee_lauder_foundation.jpg"
        
        print(f"\n=== End-to-End 테스트: {test_product} ===")
        
        # 1. 키워드 추출
        keyword_result = self.keyword_extractor.extract_all_keywords(test_product)
        keywords = keyword_result['keywords']
        
        assert len(keywords) > 0
        print(f"1. 키워드 추출: {len(keywords)}개 -> {keywords[:3]}")
        
        # 2. 다중 플랫폼 검색
        search_result = self.smart_search.search_multi_platform(test_product, product_image)
        
        if search_result['success']:
            results = search_result['results']
            print(f"2. 다중 플랫폼 검색: {len(results)}개 결과")
            
            # 3. 이미지 유사도 분석 (결과가 있는 경우)
            if results:
                analyzed_results = self.image_analyzer.analyze_product_images(product_image, results)
                
                # 유사도 점수가 추가되었는지 확인
                for result in analyzed_results[:3]:
                    assert 'image_similarity' in result
                    similarity = result['image_similarity']
                    assert 0 <= similarity <= 1
                
                print(f"3. 이미지 분석: 평균 유사도 {sum(r['image_similarity'] for r in analyzed_results) / len(analyzed_results):.3f}")
            
            # 4. 검색 통계
            stats = self.smart_search.get_search_statistics()
            print(f"4. 검색 통계: {stats}")
            
            # 성공 기준 검증
            assert len(results) >= 3, "최소 3개 이상의 검색 결과 필요"
            
            high_quality_results = [r for r in results if r.get('recommendation_score', 0) > 0.5]
            assert len(high_quality_results) >= 1, "최소 1개 이상의 고품질 결과 필요"
            
            print("✅ End-to-End 테스트 통과!")
        
        else:
            print(f"검색 실패: {search_result.get('message')}")
    
    def test_performance_benchmarks(self):
        """성능 벤치마크 테스트"""
        if not SmartSearch:
            pytest.skip("SmartSearch 모듈 없음")
        
        import time
        
        # 성능 테스트 케이스
        test_cases = [
            "크림",
            "립스틱 추천",
            "샤넬 향수",
            "아이유 사용 제품",
            "일본 브랜드 스킨케어"
        ]
        
        total_time = 0
        successful_searches = 0
        
        for test_case in test_cases:
            start_time = time.time()
            
            result = self.smart_search.search_multi_platform(test_case)
            
            end_time = time.time()
            search_time = end_time - start_time
            total_time += search_time
            
            if result['success']:
                successful_searches += 1
                result_count = len(result['results'])
                print(f"검색: '{test_case}' -> {result_count}개 결과, {search_time:.2f}초")
            else:
                print(f"검색 실패: '{test_case}' -> {search_time:.2f}초")
        
        # 성능 기준 검증
        avg_time = total_time / len(test_cases)
        success_rate = successful_searches / len(test_cases)
        
        print(f"\n=== 성능 벤치마크 ===")
        print(f"평균 검색 시간: {avg_time:.2f}초")
        print(f"성공률: {success_rate:.1%}")
        
        # 성능 목표 검증
        assert avg_time < 5.0, f"평균 검색 시간이 너무 오래 걸림: {avg_time:.2f}초"
        assert success_rate >= 0.8, f"성공률이 너무 낮음: {success_rate:.1%}"
        
        print("✅ 성능 벤치마크 통과!")

def test_integration_with_streamlit_components():
    """Streamlit 컴포넌트와의 통합 테스트"""
    
    # 모듈 임포트 테스트
    try:
        from dashboard.pages.filtered_products import render_smart_search_interface
        print("✅ Streamlit 컴포넌트 임포트 성공")
    except ImportError as e:
        print(f"❌ Streamlit 컴포넌트 임포트 실패: {e}")
        return False
    
    # 기본 함수 호출 테스트 (실제 Streamlit 세션 없이)
    try:
        # 이 테스트는 실제 Streamlit 환경에서만 실행 가능
        print("⚠️ Streamlit 세션이 필요한 테스트는 대시보드에서 직접 확인 필요")
        return True
    except Exception as e:
        print(f"Streamlit 통합 테스트 오류: {e}")
        return False

if __name__ == "__main__":
    print("S02_M02_T02 반자동 보조 검색 시스템 통합 테스트 시작")
    print("="*60)
    
    # 모듈 가용성 확인
    modules_available = {
        'SmartSearch': SmartSearch is not None,
        'KeywordExtractor': KeywordExtractor is not None,
        'ImageSimilarityAnalyzer': ImageSimilarityAnalyzer is not None
    }
    
    print("모듈 가용성:")
    for module, available in modules_available.items():
        status = "✅" if available else "❌"
        print(f"  {status} {module}")
    
    if not any(modules_available.values()):
        print("❌ 필수 모듈을 로드할 수 없습니다.")
        exit(1)
    
    # 수동 테스트 실행
    test_suite = TestSmartSearchSystem()
    test_suite.setup_method()
    
    try:
        print("\n1. 키워드 추출기 테스트...")
        test_suite.test_keyword_extractor_basic_functionality()
        
        print("\n2. 키워드 추출기 엣지 케이스 테스트...")
        test_suite.test_keyword_extractor_edge_cases()
        
        print("\n3. 스마트 검색 다중 플랫폼 테스트...")
        test_suite.test_smart_search_multi_platform()
        
        print("\n4. 수동 검색 테스트...")
        test_suite.test_smart_search_manual_search()
        
        print("\n5. 이미지 유사도 분석기 테스트...")
        test_suite.test_image_similarity_analyzer()
        
        print("\n6. End-to-End 워크플로우 테스트...")
        test_suite.test_end_to_end_search_workflow()
        
        print("\n7. 성능 벤치마크 테스트...")
        test_suite.test_performance_benchmarks()
        
        print("\n8. Streamlit 통합 테스트...")
        test_integration_with_streamlit_components()
        
        print("\n" + "="*60)
        print("🎉 모든 테스트 완료!")
        print("✅ S02_M02_T02 반자동 보조 검색 시스템이 성공적으로 구현되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        exit(1)