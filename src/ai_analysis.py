"""
AI 2-Pass 분석 파이프라인
PRD v1.0 - Whisper + Gemini 2.5 Flash 통합 분석 시스템
"""

import os
import json
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import time
import asyncio

# AI 모델 imports
import google.generativeai as genai
from faster_whisper import WhisperModel
import librosa
import soundfile as sf

# 프로젝트 imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.utils.database_manager import get_database_manager

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Whisper 음성 인식 처리기"""
    
    def __init__(self, model_size: str = "small"):
        """
        Args:
            model_size: Whisper 모델 크기 (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
        self._init_model()
    
    def _init_model(self):
        """Whisper 모델 초기화"""
        try:
            logger.info(f"Whisper {self.model_size} 모델 로딩 중...")
            self.model = WhisperModel(
                self.model_size,
                device="cpu",  # GPU 사용시 "cuda"
                compute_type="int8"  # 메모리 효율성
            )
            logger.info("Whisper 모델 로딩 완료")
        except Exception as e:
            logger.error(f"Whisper 모델 로딩 실패: {e}")
    
    def transcribe_audio(
        self,
        audio_path: str,
        language: str = "ko"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        오디오 파일을 텍스트로 변환 (타임스탬프 포함)
        
        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드 (ko, en)
            
        Returns:
            타임스탬프가 포함된 세그먼트 리스트
        """
        if not self.model:
            logger.error("Whisper 모델이 초기화되지 않았습니다.")
            return None
        
        try:
            logger.info(f"음성 인식 시작: {audio_path}")
            
            # 오디오 파일 전처리
            audio_path = self._preprocess_audio(audio_path)
            
            # 음성 인식 실행
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                language=language,
                word_timestamps=True,  # 단어별 타임스탬프
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )
            
            # 결과 정리
            transcripts = []
            for segment in segments:
                transcript_data = {
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip(),
                    "confidence": round(segment.avg_logprob, 3),
                    "words": []
                }
                
                # 단어별 타임스탬프 추가
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        transcript_data["words"].append({
                            "start": round(word.start, 2),
                            "end": round(word.end, 2),
                            "word": word.word.strip(),
                            "confidence": round(word.probability, 3)
                        })
                
                transcripts.append(transcript_data)
            
            logger.info(f"음성 인식 완료: {len(transcripts)}개 세그먼트")
            return transcripts
            
        except Exception as e:
            logger.error(f"음성 인식 실패: {e}")
            return None
        finally:
            # 임시 파일 정리
            if audio_path != str(audio_path) and Path(audio_path).exists():
                Path(audio_path).unlink()
    
    def _preprocess_audio(self, audio_path: str) -> str:
        """오디오 전처리 (샘플률 조정, 모노 변환)"""
        try:
            # 오디오 로드 (16kHz 모노로 변환)
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            
            # 음성이 너무 작은 경우 정규화
            if audio.max() < 0.1:
                audio = librosa.util.normalize(audio)
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                sf.write(tmp_file.name, audio, 16000)
                return tmp_file.name
                
        except Exception as e:
            logger.warning(f"오디오 전처리 실패, 원본 사용: {e}")
            return audio_path


class GeminiAnalyzer:
    """Gemini 2.5 Flash AI 분석기"""
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Gemini API 키
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("Gemini API 키가 설정되지 않았습니다. 환경변수 GEMINI_API_KEY를 설정하세요.")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("Gemini 2.5 Flash 모델 초기화 완료")
        except Exception as e:
            logger.error(f"Gemini 모델 초기화 실패: {e}")
            self.model = None
    
    def first_pass_analysis(
        self,
        transcript: List[Dict[str, Any]],
        video_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        1차 분석: 전체 스크립트에서 제품 추천 후보 시간대 탐지
        
        Args:
            transcript: Whisper 변환 결과
            video_metadata: 영상 메타데이터
            
        Returns:
            후보 시간대 목록
        """
        if not self.model:
            logger.error("Gemini 모델이 초기화되지 않았습니다.")
            return []
        
        try:
            # 전체 스크립트 텍스트 구성
            full_script = self._format_transcript_for_analysis(transcript)
            
            # 1차 분석 프롬프트 (PRD 기반)
            prompt = self._get_first_pass_prompt(full_script, video_metadata)
            
            # Gemini 분석 실행
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # 일관성을 위해 낮은 temperature
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            
            # JSON 파싱
            candidates = json.loads(response.text)
            
            # 결과 검증 및 정리
            validated_candidates = []
            for candidate in candidates:
                if self._validate_candidate_timeframe(candidate, transcript):
                    validated_candidates.append(candidate)
            
            logger.info(f"1차 분석 완료: {len(validated_candidates)}개 후보 시간대 발견")
            return validated_candidates
            
        except Exception as e:
            logger.error(f"1차 분석 실패: {e}")
            return []
    
    def second_pass_analysis(
        self,
        candidate_timeframe: Dict[str, Any],
        transcript_segment: List[Dict[str, Any]],
        visual_data: Dict[str, Any],
        video_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        2차 분석: 특정 후보 시간대의 상세 분석
        
        Args:
            candidate_timeframe: 1차 분석 결과 후보
            transcript_segment: 해당 구간 음성 데이터
            visual_data: 해당 구간 시각 데이터 (OCR, 객체 인식)
            video_metadata: 영상 메타데이터
            
        Returns:
            PRD JSON 스키마 형식의 완전한 후보 데이터
        """
        if not self.model:
            logger.error("Gemini 모델이 초기화되지 않았습니다.")
            return None
        
        try:
            # 2차 분석 프롬프트 구성
            prompt = self._get_second_pass_prompt(
                candidate_timeframe,
                transcript_segment,
                visual_data,
                video_metadata
            )
            
            # Gemini 분석 실행
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    response_mime_type="application/json"
                )
            )
            
            # JSON 파싱 및 스키마 검증
            result = json.loads(response.text)
            
            # PPL 확률 분석
            ppl_probability = self._analyze_ppl_probability(
                transcript_segment,
                video_metadata
            )
            
            # 매력도 스코어링
            attractiveness_score = self._calculate_attractiveness_score(result)
            
            # 최종 데이터 구성
            final_result = {
                "source_info": {
                    "celebrity_name": result.get("celebrity_name", video_metadata.get("channel_title", "")),
                    "channel_name": video_metadata.get("channel_title", ""),
                    "video_title": video_metadata.get("title", ""),
                    "video_url": video_metadata.get("url", ""),
                    "upload_date": video_metadata.get("published_at", "")
                },
                "candidate_info": {
                    "product_name_ai": result.get("product_name", ""),
                    "product_name_manual": None,
                    "clip_start_time": candidate_timeframe.get("start_time", 0),
                    "clip_end_time": candidate_timeframe.get("end_time", 0),
                    "category_path": result.get("category", []),
                    "features": result.get("features", []),
                    "score_details": attractiveness_score,
                    "hook_sentence": result.get("hook_sentence", ""),
                    "summary_for_caption": result.get("summary", ""),
                    "target_audience": result.get("target_audience", []),
                    "price_point": result.get("price_point", ""),
                    "endorsement_type": result.get("endorsement_type", ""),
                    "recommended_titles": result.get("recommended_titles", []),
                    "recommended_hashtags": result.get("recommended_hashtags", [])
                },
                "monetization_info": {
                    "is_coupang_product": False,  # 추후 쿠팡 API 연동에서 업데이트
                    "coupang_url_ai": None,
                    "coupang_url_manual": None
                },
                "status_info": {
                    "current_status": "filtered_no_coupang" if ppl_probability > 0.7 else "needs_review",
                    "is_ppl": ppl_probability > 0.7,
                    "ppl_confidence": round(ppl_probability, 2)
                }
            }
            
            logger.info(f"2차 분석 완료: {result.get('product_name', 'Unknown')}")
            return final_result
            
        except Exception as e:
            logger.error(f"2차 분석 실패: {e}")
            return None
    
    def _format_transcript_for_analysis(self, transcript: List[Dict[str, Any]]) -> str:
        """분석용 스크립트 포맷팅"""
        formatted_segments = []
        for segment in transcript:
            start_time = segment["start"]
            text = segment["text"]
            formatted_segments.append(f'[{start_time:.1f}s] {text}')
        
        return "\n".join(formatted_segments)
    
    def _get_first_pass_prompt(
        self,
        full_script: str,
        video_metadata: Dict[str, Any]
    ) -> str:
        """1차 분석 프롬프트 생성 (PRD 기반)"""
        return f"""
너는 지금부터 **'베테랑 유튜브 콘텐츠 큐레이터'** 역할을 수행한다. 너의 임무는 긴 영상 스크립트에서 시청자의 구매 욕구를 자극할 만한 '진짜 제품 추천' 구간만을 정확히 골라내는 것이다.

**[영상 정보]**
- 제목: {video_metadata.get('title', '')}
- 채널: {video_metadata.get('channel_title', '')}
- 설명: {video_metadata.get('description', '')[:200]}...

**[전체 스크립트]**
{full_script}

**[지시사항]**
1. 스크립트 전체를 읽고, 아래 [판단 기준]에 부합하는 모든 '제품 추천 의심 구간'을 찾아라.
2. 각 구간에 대해 JSON 리스트로 결과를 반환해라.
3. 추천 구간이 없다면, 빈 리스트 []를 반환하고 다른 어떤 설명도 추가하지 마라.

**[판단 기준]**
제품명이 직접 언급되지 않아도, 아래와 같은 패턴이 나타나면 '추천의 시작'을 알리는 강력한 신호로 인지해야 한다:

1. **지칭 및 소개 패턴:** "제가 요즘 진짜 잘 쓰는 게 있는데...", "짠! 오늘 보여드릴 건 바로 이거예요."
2. **상세 묘사 패턴:** "딱 열면 향이 확 나는데...", "발라보면 제형이 진짜 꾸덕해요."
3. **경험 및 효과 공유 패턴:** "이거 쓰고 나서 피부가 완전 달라졌어요.", "아침에 화장이 진짜 잘 받아요."
4. **소유 및 애착 표현 패턴:** "이건 제 파우치에 항상 들어있는 거예요.", "해외 나갈 때 없으면 불안한 아이템이에요."

**[응답 형식]**
```json
[
  {{
    "start_time": 시작_시간_초,
    "end_time": 종료_시간_초,
    "reason": "탐지_사유",
    "confidence_score": 0.0-1.0_신뢰도
  }}
]
```
"""
    
    def _get_second_pass_prompt(
        self,
        candidate_timeframe: Dict[str, Any],
        transcript_segment: List[Dict[str, Any]],
        visual_data: Dict[str, Any],
        video_metadata: Dict[str, Any]
    ) -> str:
        """2차 분석 프롬프트 생성 (PRD 기반)"""
        
        # 음성 텍스트 추출
        audio_text = " ".join([seg["text"] for seg in transcript_segment])
        
        # 시각 데이터 요약
        visual_summary = {
            "ocr_text": visual_data.get("ocr_text", []),
            "detected_objects": visual_data.get("objects", []),
            "text_regions": visual_data.get("text_regions", [])
        }
        
        return f"""
너는 지금부터 소비자의 구매 심리를 꿰뚫는 **'탑티어 커머스 콘텐츠 크리에이터'** 역할을 맡는다. 너의 임무는 주어진 음성, 시각 정보를 조합하여, 즉시 바이럴될 수 있는 인스타그램 릴스 콘텐츠의 모든 구성 요소를 완벽하게 생성하는 것이다.

**[분석할 데이터]**
- **영상 정보:** {video_metadata.get('title', '')} by {video_metadata.get('channel_title', '')}
- **시간대:** {candidate_timeframe.get('start_time', 0):.1f}초 ~ {candidate_timeframe.get('end_time', 0):.1f}초
- **음성 내용:** {audio_text}
- **시각 정보:** {json.dumps(visual_summary, ensure_ascii=False)}

**[지시사항]**
아래 JSON 스키마에 맞춰 완벽하게 출력해줘. 정보가 부족하면, 절대 지어내지 말고 적절한 기본값을 사용해야 한다.

**[JSON 응답 형식]**
```json
{{
  "celebrity_name": "연예인_이름",
  "product_name": "제품명_AI_추정",
  "category": ["대분류", "중분류", "소분류"],
  "features": ["특징1", "특징2", "특징3"],
  "hook_sentence": "바이럴_훅_문장",
  "summary": "캡션용_요약_설명",
  "target_audience": ["타겟1", "타겟2", "타겟3"],
  "price_point": "가격대_추정(저가/중가/고가/프리미엄)",
  "endorsement_type": "추천_유형(자연스러운_언급/적극적_추천/습관적_사용)",
  "recommended_titles": ["제목1", "제목2", "제목3"],
  "recommended_hashtags": ["#해시태그1", "#해시태그2", "#해시태그3"]
}}
```
"""
    
    def _validate_candidate_timeframe(
        self,
        candidate: Dict[str, Any],
        transcript: List[Dict[str, Any]]
    ) -> bool:
        """후보 시간대 검증"""
        try:
            start_time = candidate.get("start_time", 0)
            end_time = candidate.get("end_time", 0)
            confidence = candidate.get("confidence_score", 0)
            
            # 기본 검증
            if start_time >= end_time or confidence < 0.3:
                return False
            
            # 시간대가 스크립트 범위 내에 있는지 확인
            max_time = max([seg["end"] for seg in transcript]) if transcript else 0
            if start_time > max_time or end_time > max_time + 30:  # 30초 여유
                return False
            
            return True
            
        except Exception:
            return False
    
    def _analyze_ppl_probability(
        self,
        transcript_segment: List[Dict[str, Any]],
        video_metadata: Dict[str, Any]
    ) -> float:
        """PPL(유료광고) 확률 분석"""
        try:
            # 음성 텍스트 분석
            text = " ".join([seg["text"] for seg in transcript_segment])
            
            # PPL 지표들
            ppl_indicators = [
                "협찬", "광고", "제공", "paid", "ad", "sponsored",
                "할인", "쿠폰", "링크", "구매", "주문"
            ]
            
            # 영상 설명 분석
            description = video_metadata.get("description", "").lower()
            
            ppl_score = 0.0
            
            # 텍스트에서 PPL 지표 검출
            for indicator in ppl_indicators:
                if indicator in text.lower():
                    ppl_score += 0.15
                if indicator in description:
                    ppl_score += 0.1
            
            # 제목에서 PPL 지표 검출
            title = video_metadata.get("title", "").lower()
            if any(indicator in title for indicator in ppl_indicators):
                ppl_score += 0.2
            
            return min(1.0, ppl_score)
            
        except Exception:
            return 0.0
    
    def _calculate_attractiveness_score(
        self,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """매력도 스코어링 (PRD 공식 기반)"""
        try:
            # 감성 강도 계산 (0.0 - 1.0)
            sentiment_score = 0.8  # 기본값, 추후 감성 분석 모델 연동
            
            # 실사용 인증 강도 계산
            endorsement_type = analysis_result.get("endorsement_type", "")
            if "습관적_사용" in endorsement_type:
                endorsement_score = 0.9
            elif "적극적_추천" in endorsement_type:
                endorsement_score = 0.8
            elif "자연스러운_언급" in endorsement_type:
                endorsement_score = 0.6
            else:
                endorsement_score = 0.5
            
            # 인플루언서 신뢰도 (기본값, 추후 채널 분석으로 개선)
            influencer_score = 0.7
            
            # PRD 공식: 총점 = (0.50 * 감성 강도) + (0.35 * 실사용 인증 강도) + (0.15 * 인플루언서 신뢰도)
            total_score = (
                0.50 * sentiment_score +
                0.35 * endorsement_score +
                0.15 * influencer_score
            )
            
            return {
                "total": round(total_score * 100, 1),  # 100점 만점으로 변환
                "sentiment_score": round(sentiment_score, 2),
                "endorsement_score": round(endorsement_score, 2),
                "influencer_score": round(influencer_score, 2)
            }
            
        except Exception:
            return {
                "total": 50.0,
                "sentiment_score": 0.5,
                "endorsement_score": 0.5,
                "influencer_score": 0.5
            }


class AIAnalysisPipeline:
    """AI 2-Pass 분석 파이프라인 통합 관리"""
    
    def __init__(
        self,
        whisper_model_size: str = "small",
        gemini_api_key: str = None
    ):
        """
        Args:
            whisper_model_size: Whisper 모델 크기
            gemini_api_key: Gemini API 키
        """
        self.transcriber = WhisperTranscriber(whisper_model_size)
        self.analyzer = GeminiAnalyzer(gemini_api_key)
        self.db = get_database_manager()
    
    def analyze_video(
        self,
        video_metadata: Dict[str, Any],
        audio_file_path: str
    ) -> List[Dict[str, Any]]:
        """
        전체 영상 분석 파이프라인 실행
        
        Args:
            video_metadata: 영상 메타데이터
            audio_file_path: 오디오 파일 경로
            
        Returns:
            분석된 후보 목록
        """
        try:
            logger.info(f"영상 분석 시작: {video_metadata.get('title', 'Unknown')}")
            
            # 1단계: Whisper 음성 인식
            transcript = self.transcriber.transcribe_audio(audio_file_path)
            if not transcript:
                logger.error("음성 인식 실패")
                return []
            
            # 2단계: Gemini 1차 분석 (후보 시간대 탐지)
            candidate_timeframes = self.analyzer.first_pass_analysis(
                transcript, video_metadata
            )
            
            if not candidate_timeframes:
                logger.info("제품 추천 후보 시간대를 찾지 못했습니다.")
                return []
            
            # 3단계: 각 후보 시간대별 상세 분석
            final_candidates = []
            for timeframe in candidate_timeframes:
                try:
                    # 해당 구간 스크립트 추출
                    segment_transcript = self._extract_transcript_segment(
                        transcript, timeframe["start_time"], timeframe["end_time"]
                    )
                    
                    # 시각 데이터 추출 (현재는 더미, 추후 구현)
                    visual_data = self._extract_visual_data(
                        video_metadata, timeframe["start_time"], timeframe["end_time"]
                    )
                    
                    # Gemini 2차 분석
                    detailed_analysis = self.analyzer.second_pass_analysis(
                        timeframe, segment_transcript, visual_data, video_metadata
                    )
                    
                    if detailed_analysis:
                        # 데이터베이스에 저장
                        success = self.db.save_candidate(detailed_analysis)
                        if success:
                            final_candidates.append(detailed_analysis)
                            logger.info(f"후보 저장 완료: {detailed_analysis['candidate_info']['product_name_ai']}")
                    
                    # API 호출 제한 준수
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"후보 분석 실패: {e}")
                    continue
            
            logger.info(f"분석 완료: {len(final_candidates)}개 후보 생성")
            return final_candidates
            
        except Exception as e:
            logger.error(f"영상 분석 파이프라인 실패: {e}")
            return []
    
    def _extract_transcript_segment(
        self,
        transcript: List[Dict[str, Any]],
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """특정 시간대의 스크립트 추출"""
        segment = []
        for entry in transcript:
            # 구간과 겹치는 부분이 있으면 포함
            if entry["start"] <= end_time and entry["end"] >= start_time:
                segment.append(entry)
        return segment
    
    def _extract_visual_data(
        self,
        video_metadata: Dict[str, Any],
        start_time: float,
        end_time: float
    ) -> Dict[str, Any]:
        """시각 데이터 추출 (OCR 및 객체 인식)"""
        try:
            # 시각 분석기 import
            from .visual_analysis import create_visual_analyzer
            
            # 시각 분석기 초기화 (필요시에만)
            if not hasattr(self, 'visual_analyzer'):
                self.visual_analyzer = create_visual_analyzer()
            
            # YouTube URL에서 시각 분석
            video_url = video_metadata.get('url', '')
            if video_url and 'youtube.com' in video_url:
                result = self.visual_analyzer.analyze_video_segment(
                    video_url,
                    start_time,
                    end_time,
                    is_youtube_url=True
                )
                
                # 임시 파일 정리 (백그라운드에서)
                try:
                    self.visual_analyzer.cleanup_temp_files(result)
                except Exception as e:
                    logger.warning(f"임시 파일 정리 중 오류: {e}")
                
                return result
            else:
                logger.warning("YouTube URL이 아니므로 시각 분석을 건너뜁니다.")
                return {
                    "ocr_text": [],
                    "objects": [],
                    "text_regions": [],
                    "frames_analyzed": 0
                }
                
        except Exception as e:
            logger.error(f"시각 데이터 추출 실패: {e}")
            return {
                "ocr_text": [],
                "objects": [],
                "text_regions": [],
                "frames_analyzed": 0
            }


def create_ai_pipeline(
    whisper_model_size: str = "small",
    gemini_api_key: str = None
) -> AIAnalysisPipeline:
    """AI 분석 파이프라인 생성"""
    return AIAnalysisPipeline(whisper_model_size, gemini_api_key)


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # API 키 확인
    if not os.getenv('GEMINI_API_KEY'):
        print("Gemini API 키가 설정되지 않았습니다.")
        print("환경변수 GEMINI_API_KEY를 설정해주세요.")
        sys.exit(1)
    
    # 파이프라인 테스트
    pipeline = create_ai_pipeline()
    
    # 더미 데이터로 테스트
    test_metadata = {
        "title": "제가 요즘 사용하는 스킨케어 제품들",
        "channel_title": "뷰티크리에이터",
        "description": "안녕하세요! 오늘은 제가 요즘 사용하는 스킨케어 제품들을 소개해드리려고 해요.",
        "url": "https://www.youtube.com/watch?v=test123"
    }
    
    print("AI 분석 파이프라인이 준비되었습니다.")
    print("실제 오디오 파일로 테스트하려면 analyze_video() 메소드를 사용하세요.")