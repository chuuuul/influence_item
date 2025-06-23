"""
S02_M02_T02 반자동 보조 검색 시스템 기본 테스트
Streamlit 없이 기본 기능 검증
"""

import sys
from pathlib import Path
import time

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_keyword_extractor():
    """키워드 추출기 기본 테스트"""
    print("1. 키워드 추출기 테스트...")
    
    try:
        # 키워드 추출기 import 및 테스트
        sys.path.insert(0, str(project_root / "dashboard" / "utils"))
        from keyword_extractor import KeywordExtractor
        
        extractor = KeywordExtractor()
        
        # 테스트 케이스
        test_products = [
            "샤넬 레 베주 플뤼이드 파운데이션",
            "아이유가 사용하는 립밤",
            "그 브랜드 세럼"
        ]
        
        for product in test_products:
            result = extractor.extract_all_keywords(product, max_keywords=8)
            
            assert 'keywords' in result
            assert isinstance(result['keywords'], list)
            assert len(result['keywords']) > 0
            
            print(f"  제품: {product}")
            print(f"  키워드: {result['keywords'][:5]}")
        
        print("  ✅ 키워드 추출기 테스트 통과")
        return True
        
    except Exception as e:
        print(f"  ❌ 키워드 추출기 테스트 실패: {e}")
        return False

def test_smart_search():
    """스마트 검색 기본 테스트"""
    print("\n2. 스마트 검색 테스트...")
    
    try:
        # 스마트 검색 import 및 테스트
        sys.path.insert(0, str(project_root / "dashboard" / "components"))
        
        # Mock Streamlit
        class MockStreamlit:
            def progress(self, value):
                return MockProgressBar()
            def empty(self):
                return MockEmpty()
            def error(self, msg):
                print(f"Error: {msg}")
            def info(self, msg):
                print(f"Info: {msg}")
        
        class MockProgressBar:
            def progress(self, value):
                pass
            def empty(self):
                pass
        
        class MockEmpty:
            def text(self, msg):
                print(f"Status: {msg}")
            def empty(self):
                pass
        
        # Mock streamlit module
        sys.modules['streamlit'] = MockStreamlit()
        
        from smart_search import SmartSearch
        
        smart_search = SmartSearch()
        
        # 키워드 추출 테스트
        keywords = smart_search.extract_keywords("샤넬 크림")
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        print(f"  키워드 추출: {keywords[:3]}")
        
        # 플랫폼별 검색 테스트
        naver_results = smart_search.search_naver("크림", max_results=2)
        assert isinstance(naver_results, list)
        print(f"  네이버 검색: {len(naver_results)}개 결과")
        
        st11_results = smart_search.search_11st("크림", max_results=2)
        assert isinstance(st11_results, list)
        print(f"  11번가 검색: {len(st11_results)}개 결과")
        
        # 추천 점수 계산 테스트
        if naver_results:
            score = smart_search.calculate_recommendation_score(naver_results[0])
            assert 0 <= score <= 1
            print(f"  추천 점수: {score:.3f}")
        
        print("  ✅ 스마트 검색 기본 기능 테스트 통과")
        return True
        
    except Exception as e:
        print(f"  ❌ 스마트 검색 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_image_similarity():
    """이미지 유사도 분석기 테스트"""
    print("\n3. 이미지 유사도 분석기 테스트...")
    
    try:
        sys.path.insert(0, str(project_root / "dashboard" / "utils"))
        from image_similarity import ImageSimilarityAnalyzer
        
        analyzer = ImageSimilarityAnalyzer()
        
        # 테스트 이미지 URL들
        test_images = [
            "https://example.com/beauty/cream.jpg",
            "https://coupang.com/product/image1.png",
        ]
        
        # 특징 추출 테스트
        for image_url in test_images:
            features = analyzer.extract_image_features(image_url)
            
            required_fields = ['url_hash', 'domain', 'file_type', 'estimated_category']
            for field in required_fields:
                assert field in features
            
            print(f"  이미지: {image_url.split('/')[-1]} -> 카테고리: {features['estimated_category']}")
        
        # 유사도 계산 테스트
        if len(test_images) >= 2:
            features1 = analyzer.extract_image_features(test_images[0])
            features2 = analyzer.extract_image_features(test_images[1])
            
            similarity = analyzer.calculate_similarity_score(features1, features2)
            assert 0 <= similarity <= 1
            print(f"  이미지 유사도: {similarity:.3f}")
        
        print("  ✅ 이미지 유사도 분석기 테스트 통과")
        return True
        
    except Exception as e:
        print(f"  ❌ 이미지 유사도 분석기 테스트 실패: {e}")
        return False

def test_file_structure():
    """파일 구조 확인"""
    print("\n4. 파일 구조 확인...")
    
    required_files = [
        "dashboard/components/smart_search.py",
        "dashboard/utils/keyword_extractor.py",
        "dashboard/utils/image_similarity.py",
        "dashboard/pages/filtered_products.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"  ✅ {file_path}")
    
    if missing_files:
        print(f"  ❌ 누락된 파일: {missing_files}")
        return False
    else:
        print("  ✅ 모든 필수 파일 존재")
        return True

def test_integration_workflow():
    """통합 워크플로우 시뮬레이션"""
    print("\n5. 통합 워크플로우 시뮬레이션...")
    
    try:
        # Mock environment setup
        class MockStreamlit:
            def progress(self, value): return MockEmpty()
            def empty(self): return MockEmpty()
            def error(self, msg): print(f"Error: {msg}")
            def info(self, msg): print(f"Info: {msg}")
            def success(self, msg): print(f"Success: {msg}")
        
        class MockEmpty:
            def text(self, msg): print(f"Status: {msg}")
            def empty(self): pass
            def progress(self, value): pass
        
        sys.modules['streamlit'] = MockStreamlit()
        
        # Import modules
        sys.path.insert(0, str(project_root / "dashboard" / "components"))
        sys.path.insert(0, str(project_root / "dashboard" / "utils"))
        
        from smart_search import SmartSearch
        from keyword_extractor import KeywordExtractor
        from image_similarity import ImageSimilarityAnalyzer
        
        # 워크플로우 시뮬레이션
        test_product = "샤넬 파운데이션"
        print(f"  테스트 제품: {test_product}")
        
        # 1. 키워드 추출
        extractor = KeywordExtractor()
        keyword_result = extractor.extract_all_keywords(test_product)
        keywords = keyword_result['keywords']
        print(f"  1단계 - 키워드 추출: {len(keywords)}개")
        
        # 2. 스마트 검색
        smart_search = SmartSearch()
        extracted_keywords = smart_search.extract_keywords(test_product)
        print(f"  2단계 - 검색 키워드: {len(extracted_keywords)}개")
        
        # 3. 플랫폼별 검색 (모의)
        naver_results = smart_search.search_naver(test_product, max_results=3)
        st11_results = smart_search.search_11st(test_product, max_results=3)
        amazon_results = smart_search.search_amazon(test_product, max_results=2)
        
        total_results = len(naver_results) + len(st11_results) + len(amazon_results)
        print(f"  3단계 - 검색 결과: {total_results}개 (네이버: {len(naver_results)}, 11번가: {len(st11_results)}, 아마존: {len(amazon_results)})")
        
        # 4. 추천 점수 계산
        all_results = naver_results + st11_results + amazon_results
        for result in all_results:
            score = smart_search.calculate_recommendation_score(result)
            result['recommendation_score'] = score
        
        # 5. 이미지 유사도 분석
        analyzer = ImageSimilarityAnalyzer()
        product_image = "https://example.com/chanel_foundation.jpg"
        analyzed_results = analyzer.analyze_product_images(product_image, all_results)
        
        # 6. 최종 정렬
        analyzed_results.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        if analyzed_results:
            best_result = analyzed_results[0]
            print(f"  4단계 - 최고 점수: {best_result['recommendation_score']:.3f} ({best_result['platform']})")
        
        print("  ✅ 통합 워크플로우 시뮬레이션 성공")
        return True
        
    except Exception as e:
        print(f"  ❌ 통합 워크플로우 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print("S02_M02_T02 반자동 보조 검색 시스템 기본 테스트")
    print("="*60)
    
    test_results = []
    
    # 각 테스트 실행
    test_results.append(test_file_structure())
    test_results.append(test_keyword_extractor())
    test_results.append(test_smart_search())
    test_results.append(test_image_similarity())
    test_results.append(test_integration_workflow())
    
    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약:")
    
    passed = sum(test_results)
    total = len(test_results)
    
    test_names = [
        "파일 구조 확인",
        "키워드 추출기",
        "스마트 검색",
        "이미지 유사도 분석",
        "통합 워크플로우"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 통과" if result else "❌ 실패"
        print(f"  {i+1}. {name}: {status}")
    
    print(f"\n총 {passed}/{total} 테스트 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 모든 기본 테스트 통과!")
        print("✅ S02_M02_T02 반자동 보조 검색 시스템 기본 구현 완료")
        return True
    else:
        print(f"\n⚠️ {total-passed}개 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)