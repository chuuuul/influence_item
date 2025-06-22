"""
데이터 변환 및 정규화 유틸리티

다양한 데이터 형식을 표준 스키마로 변환하고 정규화합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from .models import (
    ProductRecommendationCandidate, SourceInfo, CandidateInfo, 
    MonetizationInfo, StatusInfo, ScoreDetails, PricePoint, EndorsementType
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """데이터 정규화 유틸리티"""
    
    @staticmethod
    def normalize_youtube_url(url: str) -> str:
        """YouTube URL 정규화"""
        try:
            # 다양한 YouTube URL 형식을 표준 형식으로 변환
            patterns = [
                r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
                r'youtu\.be/([a-zA-Z0-9_-]+)',
                r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
                r'youtube\.com/v/([a-zA-Z0-9_-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    return f"https://www.youtube.com/watch?v={video_id}"
            
            # 이미 올바른 형식인 경우 그대로 반환
            if url.startswith('https://www.youtube.com/watch?v='):
                return url
                
            raise ValueError(f"Invalid YouTube URL format: {url}")
            
        except Exception as e:
            logger.warning(f"Failed to normalize YouTube URL {url}: {e}")
            return url
    
    @staticmethod
    def normalize_coupang_url(url: str) -> str:
        """쿠팡 파트너스 URL 정규화"""
        try:
            # 쿠팡 링크 형식 확인 및 정규화
            if not url.startswith('https://link.coupang.com/'):
                # 일반 쿠팡 URL을 파트너스 링크로 변환 (실제로는 API 호출 필요)
                logger.warning(f"Non-partner Coupang URL detected: {url}")
                return url
            
            # 이미 파트너스 링크인 경우 그대로 반환
            return url
            
        except Exception as e:
            logger.warning(f"Failed to normalize Coupang URL {url}: {e}")
            return url
    
    @staticmethod
    def normalize_date_string(date_input: Union[str, datetime]) -> str:
        """날짜 문자열 정규화 (YYYY-MM-DD 형식)"""
        try:
            if isinstance(date_input, datetime):
                return date_input.strftime('%Y-%m-%d')
            
            if isinstance(date_input, str):
                # 다양한 날짜 형식 파싱 시도
                date_formats = [
                    '%Y-%m-%d',           # 2025-06-23
                    '%Y/%m/%d',           # 2025/06/23
                    '%d-%m-%Y',           # 23-06-2025
                    '%d/%m/%Y',           # 23/06/2025
                    '%Y년 %m월 %d일',      # 2025년 6월 23일
                    '%Y.%m.%d',           # 2025.06.23
                ]
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_input, fmt)
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                
                # ISO 형식 시도
                try:
                    if 'T' in date_input:
                        parsed_date = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                        return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass
            
            raise ValueError(f"Unable to parse date: {date_input}")
            
        except Exception as e:
            logger.warning(f"Failed to normalize date {date_input}: {e}")
            return str(date_input)
    
    @staticmethod
    def normalize_product_name(name: str) -> str:
        """제품명 정규화"""
        try:
            # 불필요한 공백 제거
            normalized = re.sub(r'\s+', ' ', name.strip())
            
            # 특수문자 정리 (괄호 내용은 유지)
            normalized = re.sub(r'[^\w\s\(\)\[\]가-힣-]', '', normalized)
            
            # 길이 제한 (100자)
            if len(normalized) > 100:
                normalized = normalized[:97] + "..."
                
            return normalized
            
        except Exception as e:
            logger.warning(f"Failed to normalize product name {name}: {e}")
            return name
    
    @staticmethod
    def normalize_hashtags(hashtags: List[str]) -> List[str]:
        """해시태그 정규화"""
        try:
            normalized = []
            
            for tag in hashtags:
                # # 추가 (없으면)
                if not tag.startswith('#'):
                    tag = '#' + tag
                
                # 공백 제거
                tag = tag.replace(' ', '')
                
                # 특수문자 제거 (한글, 영문, 숫자만 유지)
                tag = re.sub(r'[^\w가-힣#]', '', tag)
                
                # 길이 확인 (2자 이상)
                if len(tag) >= 2:
                    normalized.append(tag)
            
            # 중복 제거
            normalized = list(dict.fromkeys(normalized))
            
            # 최대 20개로 제한
            return normalized[:20]
            
        except Exception as e:
            logger.warning(f"Failed to normalize hashtags {hashtags}: {e}")
            return hashtags
    
    @staticmethod
    def normalize_price_point(price_input: Union[str, int, float]) -> PricePoint:
        """가격대 정규화"""
        try:
            if isinstance(price_input, (int, float)):
                # 숫자로 입력된 경우 가격대 추정
                if price_input < 10000:
                    return PricePoint.BUDGET
                elif price_input < 50000:
                    return PricePoint.STANDARD
                elif price_input < 200000:
                    return PricePoint.PREMIUM
                else:
                    return PricePoint.LUXURY
            
            if isinstance(price_input, str):
                price_lower = price_input.lower()
                
                # 매핑 테이블
                price_mapping = {
                    '저가': PricePoint.BUDGET,
                    '일반': PricePoint.STANDARD,
                    '프리미엄': PricePoint.PREMIUM,
                    '럭셔리': PricePoint.LUXURY,
                    'budget': PricePoint.BUDGET,
                    'standard': PricePoint.STANDARD,
                    'premium': PricePoint.PREMIUM,
                    'luxury': PricePoint.LUXURY,
                    '저렴': PricePoint.BUDGET,
                    '중간': PricePoint.STANDARD,
                    '고급': PricePoint.PREMIUM,
                    '최고급': PricePoint.LUXURY
                }
                
                for key, value in price_mapping.items():
                    if key in price_lower:
                        return value
                
                # 숫자 추출 시도
                numbers = re.findall(r'\d+', price_input)
                if numbers:
                    price_value = int(numbers[0])
                    return DataNormalizer.normalize_price_point(price_value)
            
            # 기본값
            return PricePoint.STANDARD
            
        except Exception as e:
            logger.warning(f"Failed to normalize price point {price_input}: {e}")
            return PricePoint.STANDARD
    
    @staticmethod
    def normalize_endorsement_type(type_input: str) -> EndorsementType:
        """추천 유형 정규화"""
        try:
            type_lower = type_input.lower()
            
            # 매핑 테이블
            type_mapping = {
                '명시적': EndorsementType.EXPLICIT_RECOMMENDATION,
                '추천': EndorsementType.EXPLICIT_RECOMMENDATION,
                '자연스러운': EndorsementType.CASUAL_MENTION,
                '언급': EndorsementType.CASUAL_MENTION,
                '습관적': EndorsementType.HABITUAL_USE,
                '사용': EndorsementType.HABITUAL_USE,
                '비교': EndorsementType.COMPARISON_REVIEW,
                '리뷰': EndorsementType.COMPARISON_REVIEW,
                '튜토리얼': EndorsementType.TUTORIAL_DEMO,
                '시연': EndorsementType.TUTORIAL_DEMO,
                'explicit': EndorsementType.EXPLICIT_RECOMMENDATION,
                'casual': EndorsementType.CASUAL_MENTION,
                'habitual': EndorsementType.HABITUAL_USE,
                'comparison': EndorsementType.COMPARISON_REVIEW,
                'tutorial': EndorsementType.TUTORIAL_DEMO
            }
            
            for key, value in type_mapping.items():
                if key in type_lower:
                    return value
            
            # 기본값
            return EndorsementType.CASUAL_MENTION
            
        except Exception as e:
            logger.warning(f"Failed to normalize endorsement type {type_input}: {e}")
            return EndorsementType.CASUAL_MENTION


class DataTransformer:
    """다양한 형식의 데이터를 표준 스키마로 변환"""
    
    def __init__(self):
        self.normalizer = DataNormalizer()
    
    def transform_legacy_format(self, legacy_data: Dict[str, Any]) -> ProductRecommendationCandidate:
        """레거시 형식 데이터를 새 스키마로 변환"""
        try:
            # 소스 정보 매핑
            source_info = SourceInfo(
                celebrity_name=legacy_data.get('influencer_name', '알 수 없음'),
                channel_name=legacy_data.get('channel', '알 수 없음'),
                video_title=legacy_data.get('title', '제목 없음'),
                video_url=self.normalizer.normalize_youtube_url(legacy_data.get('url', '')),
                upload_date=self.normalizer.normalize_date_string(
                    legacy_data.get('upload_date', datetime.now())
                )
            )
            
            # 점수 매핑
            score_details = ScoreDetails(
                total=legacy_data.get('total_score', 50),
                sentiment_score=legacy_data.get('emotion_score', 0.5),
                endorsement_score=legacy_data.get('usage_score', 0.5),
                influencer_score=legacy_data.get('creator_score', 0.5)
            )
            
            # 후보 정보 매핑
            candidate_info = CandidateInfo(
                product_name_ai=self.normalizer.normalize_product_name(
                    legacy_data.get('product', '')
                ),
                product_name_manual=legacy_data.get('manual_product'),
                clip_start_time=legacy_data.get('start', 0),
                clip_end_time=legacy_data.get('end', 30),
                category_path=legacy_data.get('categories', ['기타']),
                features=legacy_data.get('features', []),
                score_details=score_details,
                hook_sentence=legacy_data.get('hook', '매력적인 제품입니다!'),
                summary_for_caption=legacy_data.get('summary', '제품 정보'),
                target_audience=legacy_data.get('audience', []),
                price_point=self.normalizer.normalize_price_point(
                    legacy_data.get('price_range', '일반')
                ),
                endorsement_type=self.normalizer.normalize_endorsement_type(
                    legacy_data.get('mention_type', '자연스러운 언급')
                ),
                recommended_titles=legacy_data.get('titles', []),
                recommended_hashtags=self.normalizer.normalize_hashtags(
                    legacy_data.get('hashtags', [])
                )
            )
            
            # 수익화 정보 매핑
            is_monetizable = legacy_data.get('monetizable', False)
            affiliate_link = legacy_data.get('affiliate_link')
            manual_link = legacy_data.get('manual_link')
            
            # 수익화 가능하지만 링크가 없는 경우 기본 링크 생성
            if is_monetizable and not affiliate_link and not manual_link:
                affiliate_link = "https://link.coupang.com/a/pending"
            
            monetization_info = MonetizationInfo(
                is_coupang_product=is_monetizable,
                coupang_url_ai=affiliate_link,
                coupang_url_manual=manual_link
            )
            
            # 상태 정보 매핑
            status_info = StatusInfo(
                current_status=legacy_data.get('status', 'needs_review'),
                is_ppl=legacy_data.get('is_sponsored', False),
                ppl_confidence=legacy_data.get('sponsor_probability', 0.1),
                last_updated=datetime.now().isoformat()
            )
            
            return ProductRecommendationCandidate(
                source_info=source_info,
                candidate_info=candidate_info,
                monetization_info=monetization_info,
                status_info=status_info,
                schema_version="1.0",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to transform legacy data: {e}")
            raise ValueError(f"Failed to transform legacy data: {str(e)}")
    
    def transform_gemini_output(self, gemini_data: Dict[str, Any], source_info: Dict[str, Any]) -> ProductRecommendationCandidate:
        """Gemini AI 출력을 표준 스키마로 변환"""
        try:
            # 소스 정보
            source = SourceInfo(**source_info)
            
            # Gemini 출력에서 점수 추출 및 정규화
            raw_scores = gemini_data.get('scores', {})
            score_details = ScoreDetails(
                total=int(raw_scores.get('total', 50)),
                sentiment_score=float(raw_scores.get('sentiment', 0.5)),
                endorsement_score=float(raw_scores.get('endorsement', 0.5)),
                influencer_score=float(raw_scores.get('influencer', 0.5))
            )
            
            # 후보 정보 구성
            candidate_info = CandidateInfo(
                product_name_ai=self.normalizer.normalize_product_name(
                    gemini_data.get('product_name', '')
                ),
                product_name_manual=None,
                clip_start_time=int(gemini_data.get('start_time', 0)),
                clip_end_time=int(gemini_data.get('end_time', 30)),
                category_path=gemini_data.get('category', ['기타']),
                features=gemini_data.get('features', []),
                score_details=score_details,
                hook_sentence=gemini_data.get('hook', '매력적인 제품입니다!'),
                summary_for_caption=gemini_data.get('caption', '제품 정보'),
                target_audience=gemini_data.get('target_audience', []),
                price_point=self.normalizer.normalize_price_point(
                    gemini_data.get('price_point', '일반')
                ),
                endorsement_type=self.normalizer.normalize_endorsement_type(
                    gemini_data.get('endorsement_type', '자연스러운 언급')
                ),
                recommended_titles=gemini_data.get('titles', []),
                recommended_hashtags=self.normalizer.normalize_hashtags(
                    gemini_data.get('hashtags', [])
                )
            )
            
            # 수익화 정보 (기본값 - 수익화 불가능하므로 URL 필요 없음)
            monetization_info = MonetizationInfo(
                is_coupang_product=False,
                coupang_url_ai=None,
                coupang_url_manual=None
            )
            
            # 상태 정보
            status_info = StatusInfo(
                current_status='analysis_complete',
                is_ppl=gemini_data.get('is_ppl', False),
                ppl_confidence=float(gemini_data.get('ppl_confidence', 0.1)),
                last_updated=datetime.now().isoformat()
            )
            
            return ProductRecommendationCandidate(
                source_info=source,
                candidate_info=candidate_info,
                monetization_info=monetization_info,
                status_info=status_info,
                schema_version="1.0",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to transform Gemini output: {e}")
            raise ValueError(f"Failed to transform Gemini output: {str(e)}")
    
    def transform_csv_row(self, csv_row: Dict[str, str]) -> ProductRecommendationCandidate:
        """CSV 행 데이터를 표준 스키마로 변환"""
        try:
            # CSV 데이터는 모두 문자열이므로 적절히 변환
            source_info = SourceInfo(
                celebrity_name=csv_row.get('celebrity_name', '').strip(),
                channel_name=csv_row.get('channel_name', '').strip(),
                video_title=csv_row.get('video_title', '').strip(),
                video_url=self.normalizer.normalize_youtube_url(csv_row.get('video_url', '')),
                upload_date=self.normalizer.normalize_date_string(csv_row.get('upload_date', ''))
            )
            
            # 점수 변환
            score_details = ScoreDetails(
                total=int(csv_row.get('total_score', '50')),
                sentiment_score=float(csv_row.get('sentiment_score', '0.5')),
                endorsement_score=float(csv_row.get('endorsement_score', '0.5')),
                influencer_score=float(csv_row.get('influencer_score', '0.5'))
            )
            
            # 배열 필드 처리 (콤마 구분)
            category_path = [c.strip() for c in csv_row.get('category_path', '').split(',') if c.strip()]
            features = [f.strip() for f in csv_row.get('features', '').split(',') if f.strip()]
            target_audience = [t.strip() for t in csv_row.get('target_audience', '').split(',') if t.strip()]
            titles = [t.strip() for t in csv_row.get('recommended_titles', '').split('|') if t.strip()]
            hashtags = [h.strip() for h in csv_row.get('recommended_hashtags', '').split(',') if h.strip()]
            
            candidate_info = CandidateInfo(
                product_name_ai=self.normalizer.normalize_product_name(csv_row.get('product_name_ai', '')),
                product_name_manual=csv_row.get('product_name_manual') or None,
                clip_start_time=int(csv_row.get('clip_start_time', '0')),
                clip_end_time=int(csv_row.get('clip_end_time', '30')),
                category_path=category_path or ['기타'],
                features=features,
                score_details=score_details,
                hook_sentence=csv_row.get('hook_sentence', '매력적인 제품입니다!'),
                summary_for_caption=csv_row.get('summary_for_caption', '제품 정보'),
                target_audience=target_audience,
                price_point=self.normalizer.normalize_price_point(csv_row.get('price_point', '일반')),
                endorsement_type=self.normalizer.normalize_endorsement_type(csv_row.get('endorsement_type', '자연스러운 언급')),
                recommended_titles=titles,
                recommended_hashtags=self.normalizer.normalize_hashtags(hashtags)
            )
            
            # 수익화 정보
            monetization_info = MonetizationInfo(
                is_coupang_product=csv_row.get('is_coupang_product', '').lower() == 'true',
                coupang_url_ai=csv_row.get('coupang_url_ai') or None,
                coupang_url_manual=csv_row.get('coupang_url_manual') or None
            )
            
            # 상태 정보
            status_info = StatusInfo(
                current_status=csv_row.get('current_status', 'needs_review'),
                is_ppl=csv_row.get('is_ppl', '').lower() == 'true',
                ppl_confidence=float(csv_row.get('ppl_confidence', '0.1')),
                last_updated=csv_row.get('last_updated') or datetime.now().isoformat()
            )
            
            return ProductRecommendationCandidate(
                source_info=source_info,
                candidate_info=candidate_info,
                monetization_info=monetization_info,
                status_info=status_info,
                schema_version="1.0",
                created_at=csv_row.get('created_at') or datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to transform CSV row: {e}")
            raise ValueError(f"Failed to transform CSV row: {str(e)}")
    
    def convert_to_csv_dict(self, candidate: ProductRecommendationCandidate) -> Dict[str, str]:
        """스키마 데이터를 CSV 호환 딕셔너리로 변환"""
        try:
            return {
                # Source info
                'celebrity_name': candidate.source_info.celebrity_name,
                'channel_name': candidate.source_info.channel_name,
                'video_title': candidate.source_info.video_title,
                'video_url': candidate.source_info.video_url,
                'upload_date': candidate.source_info.upload_date,
                
                # Candidate info
                'product_name_ai': candidate.candidate_info.product_name_ai,
                'product_name_manual': candidate.candidate_info.product_name_manual or '',
                'clip_start_time': str(candidate.candidate_info.clip_start_time),
                'clip_end_time': str(candidate.candidate_info.clip_end_time),
                'category_path': ','.join(candidate.candidate_info.category_path),
                'features': ','.join(candidate.candidate_info.features),
                'total_score': str(candidate.candidate_info.score_details.total),
                'sentiment_score': str(candidate.candidate_info.score_details.sentiment_score),
                'endorsement_score': str(candidate.candidate_info.score_details.endorsement_score),
                'influencer_score': str(candidate.candidate_info.score_details.influencer_score),
                'hook_sentence': candidate.candidate_info.hook_sentence,
                'summary_for_caption': candidate.candidate_info.summary_for_caption,
                'target_audience': ','.join(candidate.candidate_info.target_audience),
                'price_point': candidate.candidate_info.price_point.value,
                'endorsement_type': candidate.candidate_info.endorsement_type.value,
                'recommended_titles': '|'.join(candidate.candidate_info.recommended_titles),
                'recommended_hashtags': ','.join(candidate.candidate_info.recommended_hashtags),
                
                # Monetization info
                'is_coupang_product': str(candidate.monetization_info.is_coupang_product).lower(),
                'coupang_url_ai': candidate.monetization_info.coupang_url_ai or '',
                'coupang_url_manual': candidate.monetization_info.coupang_url_manual or '',
                
                # Status info
                'current_status': candidate.status_info.current_status.value,
                'is_ppl': str(candidate.status_info.is_ppl).lower(),
                'ppl_confidence': str(candidate.status_info.ppl_confidence),
                'last_updated': candidate.status_info.last_updated or '',
                
                # Metadata
                'schema_version': candidate.schema_version,
                'created_at': candidate.created_at or '',
                'updated_at': candidate.updated_at or ''
            }
            
        except Exception as e:
            logger.error(f"Failed to convert to CSV dict: {e}")
            raise ValueError(f"Failed to convert to CSV dict: {str(e)}")


# 편의 함수들
def transform_legacy_data(legacy_data: Dict[str, Any]) -> ProductRecommendationCandidate:
    """레거시 데이터 변환 편의 함수"""
    transformer = DataTransformer()
    return transformer.transform_legacy_format(legacy_data)


def normalize_urls(data: Dict[str, Any]) -> Dict[str, Any]:
    """URL 정규화 편의 함수"""
    normalizer = DataNormalizer()
    
    if 'video_url' in data:
        data['video_url'] = normalizer.normalize_youtube_url(data['video_url'])
    
    if 'coupang_url' in data:
        data['coupang_url'] = normalizer.normalize_coupang_url(data['coupang_url'])
    
    return data


def batch_transform(data_list: List[Dict[str, Any]], transform_func: str = 'legacy') -> List[ProductRecommendationCandidate]:
    """배치 데이터 변환 편의 함수"""
    transformer = DataTransformer()
    results = []
    
    for data in data_list:
        try:
            if transform_func == 'legacy':
                result = transformer.transform_legacy_format(data)
            elif transform_func == 'csv':
                result = transformer.transform_csv_row(data)
            else:
                raise ValueError(f"Unknown transform function: {transform_func}")
            
            results.append(result)
            
        except Exception as e:
            logger.error(f"Failed to transform data item: {e}")
            continue
    
    return results