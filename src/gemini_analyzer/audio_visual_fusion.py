"""
Audio-Visual Data Fusion Engine

음성 분석 결과와 시각 분석 결과를 융합하여 종합적인 제품 분석 정보를 생성하는 
다중 모달 데이터 융합 엔진입니다.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime
from pathlib import Path

from config.config import Config
from .models import (
    WhisperSegment, AudioAnalysisResult, VisualAnalysisResult, 
    OCRResult, ObjectDetectionResult, FusionConfidence, FusedAnalysisResult
)


class AudioVisualFusion:
    """음성+시각 데이터 융합 엔진"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        융합 엔진 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config()
        self.logger = self._setup_logger()
        
        # 융합 설정
        self.time_tolerance = getattr(self.config, 'FUSION_TIME_TOLERANCE', 2.0)  # 2초 허용
        self.text_similarity_threshold = getattr(self.config, 'TEXT_SIMILARITY_THRESHOLD', 0.6)
        self.confidence_threshold = getattr(self.config, 'FUSION_CONFIDENCE_THRESHOLD', 0.7)
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL, 'INFO'))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def fuse_timeframe_data(
        self,
        audio_data: Dict[str, Any],
        visual_data: List[Dict[str, Any]],
        timeframe_start: float,
        timeframe_end: float
    ) -> FusedAnalysisResult:
        """
        특정 시간대의 음성+시각 데이터를 융합
        
        Args:
            audio_data: Whisper 음성 분석 결과
            visual_data: 시각 분석 결과 리스트 (OCR + 객체 탐지)
            timeframe_start: 분석 구간 시작 시간
            timeframe_end: 분석 구간 종료 시간
            
        Returns:
            융합된 분석 결과
        """
        try:
            self.logger.info(f"음성+시각 데이터 융합 시작: {timeframe_start:.1f}s-{timeframe_end:.1f}s")
            start_time = time.time()
            
            # 1. 음성 데이터 처리
            audio_analysis = self._process_audio_data(audio_data, timeframe_start, timeframe_end)
            
            # 2. 시각 데이터 처리 및 시간 동기화
            visual_analysis = self._process_visual_data(visual_data, timeframe_start, timeframe_end)
            
            # 3. 텍스트 매칭 및 신뢰도 계산
            fusion_confidence = self._calculate_fusion_confidence(audio_analysis, visual_analysis)
            
            # 4. 제품 언급 추출 및 시각적 확인
            product_mentions = self._extract_product_mentions(audio_analysis)
            visual_confirmations = self._extract_visual_confirmations(visual_analysis, product_mentions)
            
            # 5. 일치성 검사
            consistency_check = self._check_consistency(product_mentions, visual_confirmations, fusion_confidence)
            
            # 6. 융합 요약 생성
            fusion_summary = self._generate_fusion_summary(
                audio_analysis, visual_analysis, product_mentions, visual_confirmations, consistency_check
            )
            
            # 결과 구성
            result = FusedAnalysisResult(
                timeframe_start=timeframe_start,
                timeframe_end=timeframe_end,
                audio_analysis=audio_analysis,
                visual_analysis=visual_analysis,
                fusion_confidence=fusion_confidence,
                product_mentions=product_mentions,
                visual_confirmations=visual_confirmations,
                consistency_check=consistency_check,
                fusion_summary=fusion_summary
            )
            
            process_time = time.time() - start_time
            self.logger.info(f"융합 완료 - 소요시간: {process_time:.2f}초, 신뢰도: {fusion_confidence.overall_confidence:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"데이터 융합 실패: {str(e)}")
            raise
    
    def _process_audio_data(
        self, 
        audio_data: Dict[str, Any], 
        timeframe_start: float, 
        timeframe_end: float
    ) -> AudioAnalysisResult:
        """
        음성 데이터 처리 및 세그먼트 추출
        
        Args:
            audio_data: Whisper 분석 결과
            timeframe_start: 시작 시간
            timeframe_end: 종료 시간
            
        Returns:
            처리된 음성 분석 결과
        """
        try:
            # 시간대에 해당하는 세그먼트 필터링
            relevant_segments = []
            full_text_parts = []
            
            if isinstance(audio_data, list):
                # script_data 형태
                for segment in audio_data:
                    seg_start = segment.get('start', 0)
                    seg_end = segment.get('end', 0)
                    
                    # 겹치는 구간 확인
                    if self._is_time_overlap(seg_start, seg_end, timeframe_start, timeframe_end):
                        whisper_segment = WhisperSegment(
                            start=seg_start,
                            end=seg_end,
                            text=segment.get('text', ''),
                            confidence=segment.get('confidence')
                        )
                        relevant_segments.append(whisper_segment)
                        full_text_parts.append(segment.get('text', ''))
            
            elif isinstance(audio_data, dict):
                # 다른 형태의 음성 데이터 처리
                segments = audio_data.get('segments', [])
                for segment in segments:
                    seg_start = segment.get('start', 0)
                    seg_end = segment.get('end', 0)
                    
                    if self._is_time_overlap(seg_start, seg_end, timeframe_start, timeframe_end):
                        whisper_segment = WhisperSegment(
                            start=seg_start,
                            end=seg_end,
                            text=segment.get('text', ''),
                            confidence=segment.get('confidence')
                        )
                        relevant_segments.append(whisper_segment)
                        full_text_parts.append(segment.get('text', ''))
            
            full_text = ' '.join(full_text_parts).strip()
            
            return AudioAnalysisResult(
                timeframe_start=timeframe_start,
                timeframe_end=timeframe_end,
                segments=relevant_segments,
                full_text=full_text
            )
            
        except Exception as e:
            self.logger.error(f"음성 데이터 처리 실패: {str(e)}")
            raise
    
    def _process_visual_data(
        self, 
        visual_data: List[Dict[str, Any]], 
        timeframe_start: float, 
        timeframe_end: float
    ) -> List[VisualAnalysisResult]:
        """
        시각 데이터 처리 및 시간 동기화
        
        Args:
            visual_data: 시각 분석 결과 리스트
            timeframe_start: 시작 시간
            timeframe_end: 종료 시간
            
        Returns:
            처리된 시각 분석 결과 리스트
        """
        try:
            processed_visuals = []
            
            for visual_item in visual_data:
                frame_timestamp = visual_item.get('timestamp', 0)
                
                # 시간대 내 프레임인지 확인
                if timeframe_start <= frame_timestamp <= timeframe_end:
                    # OCR 결과 처리
                    ocr_results = []
                    if 'ocr_results' in visual_item:
                        for ocr_item in visual_item['ocr_results']:
                            ocr_result = OCRResult(
                                text=ocr_item.get('text', ''),
                                confidence=ocr_item.get('confidence', 0.0),
                                bbox=ocr_item.get('bbox', []),
                                language=ocr_item.get('language', 'unknown'),
                                area=ocr_item.get('area', 0)
                            )
                            ocr_results.append(ocr_result)
                    
                    # 객체 탐지 결과 처리
                    object_results = []
                    if 'object_detections' in visual_item:
                        for obj_item in visual_item['object_detections']:
                            obj_result = ObjectDetectionResult(
                                class_name=obj_item.get('class', 'unknown'),
                                confidence=obj_item.get('confidence', 0.0),
                                bbox=obj_item.get('bbox', [0, 0, 0, 0]),
                                area=obj_item.get('area', 0)
                            )
                            object_results.append(obj_result)
                    
                    visual_analysis = VisualAnalysisResult(
                        frame_timestamp=frame_timestamp,
                        ocr_results=ocr_results,
                        object_detection_results=object_results,
                        frame_path=visual_item.get('frame_path')
                    )
                    processed_visuals.append(visual_analysis)
            
            self.logger.debug(f"시각 데이터 처리 완료: {len(processed_visuals)}개 프레임")
            return processed_visuals
            
        except Exception as e:
            self.logger.error(f"시각 데이터 처리 실패: {str(e)}")
            raise
    
    def _is_time_overlap(
        self, 
        seg_start: float, 
        seg_end: float, 
        frame_start: float, 
        frame_end: float
    ) -> bool:
        """
        시간 구간 겹침 여부 확인
        
        Args:
            seg_start: 세그먼트 시작 시간
            seg_end: 세그먼트 종료 시간
            frame_start: 프레임 시작 시간
            frame_end: 프레임 종료 시간
            
        Returns:
            겹침 여부
        """
        # 허용 오차를 포함한 겹침 확인
        return (seg_start <= frame_end + self.time_tolerance and 
                seg_end >= frame_start - self.time_tolerance)
    
    def _calculate_fusion_confidence(
        self, 
        audio_analysis: AudioAnalysisResult, 
        visual_analysis: List[VisualAnalysisResult]
    ) -> FusionConfidence:
        """
        융합 신뢰도 계산
        
        Args:
            audio_analysis: 음성 분석 결과
            visual_analysis: 시각 분석 결과
            
        Returns:
            융합 신뢰도 점수
        """
        try:
            # 1. 텍스트 매칭 점수
            text_matching_score = self._calculate_text_matching_score(audio_analysis, visual_analysis)
            
            # 2. 시간 정렬 점수
            temporal_alignment_score = self._calculate_temporal_alignment_score(audio_analysis, visual_analysis)
            
            # 3. 의미적 일관성 점수
            semantic_coherence_score = self._calculate_semantic_coherence_score(audio_analysis, visual_analysis)
            
            # 4. 전체 신뢰도 (가중 평균)
            overall_confidence = (
                text_matching_score * 0.4 +
                temporal_alignment_score * 0.3 +
                semantic_coherence_score * 0.3
            )
            
            return FusionConfidence(
                text_matching_score=text_matching_score,
                temporal_alignment_score=temporal_alignment_score,
                semantic_coherence_score=semantic_coherence_score,
                overall_confidence=overall_confidence
            )
            
        except Exception as e:
            self.logger.error(f"신뢰도 계산 실패: {str(e)}")
            # 기본값 반환
            return FusionConfidence(
                text_matching_score=0.0,
                temporal_alignment_score=0.0,
                semantic_coherence_score=0.0,
                overall_confidence=0.0
            )
    
    def _calculate_text_matching_score(
        self, 
        audio_analysis: AudioAnalysisResult, 
        visual_analysis: List[VisualAnalysisResult]
    ) -> float:
        """텍스트 매칭 점수 계산"""
        if not audio_analysis.full_text or not visual_analysis:
            return 0.0
        
        audio_text = audio_analysis.full_text.lower()
        max_score = 0.0
        
        for visual in visual_analysis:
            for ocr_result in visual.ocr_results:
                ocr_text = ocr_result.text.lower()
                
                # 직접 매칭
                if ocr_text in audio_text or audio_text in ocr_text:
                    similarity = min(len(ocr_text), len(audio_text)) / max(len(ocr_text), len(audio_text))
                    max_score = max(max_score, similarity * ocr_result.confidence)
                
                # 단어 기반 매칭
                audio_words = set(audio_text.split())
                ocr_words = set(ocr_text.split())
                
                if audio_words and ocr_words:
                    intersection = audio_words.intersection(ocr_words)
                    if intersection:
                        jaccard = len(intersection) / len(audio_words.union(ocr_words))
                        max_score = max(max_score, jaccard * ocr_result.confidence * 0.8)
        
        return min(max_score, 1.0)
    
    def _calculate_temporal_alignment_score(
        self, 
        audio_analysis: AudioAnalysisResult, 
        visual_analysis: List[VisualAnalysisResult]
    ) -> float:
        """시간 정렬 점수 계산"""
        if not audio_analysis.segments or not visual_analysis:
            return 0.0
        
        aligned_count = 0
        total_pairs = 0
        
        for segment in audio_analysis.segments:
            for visual in visual_analysis:
                total_pairs += 1
                
                # 시간 차이 계산
                time_diff = abs(segment.start - visual.frame_timestamp)
                
                # 허용 범위 내이면 정렬됨으로 간주
                if time_diff <= self.time_tolerance:
                    aligned_count += 1
        
        return aligned_count / total_pairs if total_pairs > 0 else 0.0
    
    def _calculate_semantic_coherence_score(
        self, 
        audio_analysis: AudioAnalysisResult, 
        visual_analysis: List[VisualAnalysisResult]
    ) -> float:
        """의미적 일관성 점수 계산"""
        if not audio_analysis.full_text or not visual_analysis:
            return 0.0
        
        # 제품 관련 키워드 검출
        product_keywords = self._extract_product_keywords(audio_analysis.full_text)
        visual_confirmations = 0
        total_keywords = len(product_keywords)
        
        if total_keywords == 0:
            return 0.5  # 제품 언급이 없으면 중간 점수
        
        for keyword in product_keywords:
            for visual in visual_analysis:
                for ocr_result in visual.ocr_results:
                    if keyword.lower() in ocr_result.text.lower():
                        visual_confirmations += 1
                        break
        
        return visual_confirmations / total_keywords
    
    def _extract_product_keywords(self, text: str) -> List[str]:
        """제품 관련 키워드 추출"""
        # 브랜드명, 제품명 패턴 매칭
        patterns = [
            r'[A-Z][a-z]+ [A-Z][a-z]+',  # 브랜드 제품명 (예: Dior Lipstick)
            r'[가-힣]{2,} [가-힣]{2,}',  # 한글 브랜드 제품명
            r'\b[A-Z]{2,}\b',  # 대문자 브랜드명
        ]
        
        keywords = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)
        
        return list(set(keywords))  # 중복 제거
    
    def _extract_product_mentions(self, audio_analysis: AudioAnalysisResult) -> List[str]:
        """음성에서 제품 언급 추출"""
        text = audio_analysis.full_text
        mentions = []
        
        # 제품 언급 패턴
        patterns = [
            r'([가-힣A-Za-z0-9\s]+)(?:을|를|이|가)?\s*(?:사용|써|발라|바르고|쓰고)',
            r'이\s*([가-힣A-Za-z0-9\s]+)',
            r'([가-힣A-Za-z0-9\s]+)\s*(?:브랜드|제품)',
            r'([A-Z][a-z]+\s+[A-Za-z]+)',  # 영문 브랜드명
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                cleaned = match.strip()
                if len(cleaned) >= 2 and cleaned not in mentions:
                    mentions.append(cleaned)
        
        return mentions[:5]  # 최대 5개까지
    
    def _extract_visual_confirmations(
        self, 
        visual_analysis: List[VisualAnalysisResult], 
        product_mentions: List[str]
    ) -> List[str]:
        """시각적으로 확인된 제품명 추출"""
        confirmations = []
        
        for visual in visual_analysis:
            for ocr_result in visual.ocr_results:
                ocr_text = ocr_result.text.strip()
                
                # 제품 언급과 매칭 확인
                for mention in product_mentions:
                    if (mention.lower() in ocr_text.lower() or 
                        ocr_text.lower() in mention.lower()):
                        if ocr_result.confidence >= 0.7:  # 높은 신뢰도만
                            confirmations.append(ocr_text)
                
                # 독립적인 제품명 검출
                if (len(ocr_text) >= 3 and 
                    ocr_result.confidence >= 0.8 and
                    any(char.isalpha() for char in ocr_text)):
                    confirmations.append(ocr_text)
        
        return list(set(confirmations))  # 중복 제거
    
    def _check_consistency(
        self, 
        product_mentions: List[str], 
        visual_confirmations: List[str], 
        fusion_confidence: FusionConfidence
    ) -> bool:
        """음성-시각 일치성 검사"""
        if not product_mentions and not visual_confirmations:
            return True  # 둘 다 없으면 일치
        
        if not product_mentions or not visual_confirmations:
            return False  # 하나만 있으면 불일치
        
        # 텍스트 매칭이 있고 전체 신뢰도가 임계값 이상이면 일치
        return (fusion_confidence.text_matching_score >= self.text_similarity_threshold and
                fusion_confidence.overall_confidence >= self.confidence_threshold)
    
    def _generate_fusion_summary(
        self,
        audio_analysis: AudioAnalysisResult,
        visual_analysis: List[VisualAnalysisResult],
        product_mentions: List[str],
        visual_confirmations: List[str],
        consistency_check: bool
    ) -> str:
        """융합 분석 요약 생성"""
        summary_parts = []
        
        # 시간 정보
        duration = audio_analysis.timeframe_end - audio_analysis.timeframe_start
        summary_parts.append(f"분석 구간: {duration:.1f}초")
        
        # 음성 정보
        if audio_analysis.segments:
            summary_parts.append(f"음성 세그먼트: {len(audio_analysis.segments)}개")
        
        # 시각 정보
        if visual_analysis:
            total_ocr = sum(len(v.ocr_results) for v in visual_analysis)
            total_objects = sum(len(v.object_detection_results) for v in visual_analysis)
            summary_parts.append(f"시각 분석: {len(visual_analysis)}프레임, OCR {total_ocr}개, 객체 {total_objects}개")
        
        # 제품 정보
        if product_mentions:
            summary_parts.append(f"제품 언급: {len(product_mentions)}개")
        
        if visual_confirmations:
            summary_parts.append(f"시각 확인: {len(visual_confirmations)}개")
        
        # 일치성
        consistency_status = "일치" if consistency_check else "불일치"
        summary_parts.append(f"음성-시각 {consistency_status}")
        
        return " | ".join(summary_parts)
    
    def generate_gemini_prompt_data(self, fused_result: FusedAnalysisResult) -> Dict[str, Any]:
        """
        Gemini 2차 분석용 프롬프트 데이터 생성
        
        Args:
            fused_result: 융합 분석 결과
            
        Returns:
            Gemini 2차 분석용 구조화된 데이터
        """
        try:
            self.logger.debug("Gemini 2차 분석용 프롬프트 데이터 생성 시작")
            
            # 음성 정보 정리
            audio_data = {
                'timeframe': {
                    'start': fused_result.timeframe_start,
                    'end': fused_result.timeframe_end,
                    'duration': fused_result.timeframe_end - fused_result.timeframe_start
                },
                'transcription': fused_result.audio_analysis.full_text,
                'segments': [
                    {
                        'start': seg.start,
                        'end': seg.end,
                        'text': seg.text,
                        'confidence': seg.confidence
                    }
                    for seg in fused_result.audio_analysis.segments
                ],
                'product_mentions': fused_result.product_mentions
            }
            
            # 시각 정보 정리
            visual_data = {
                'frame_count': len(fused_result.visual_analysis),
                'frames': []
            }
            
            for visual in fused_result.visual_analysis:
                frame_data = {
                    'timestamp': visual.frame_timestamp,
                    'ocr_results': [
                        {
                            'text': ocr.text,
                            'confidence': ocr.confidence,
                            'language': ocr.language,
                            'bbox': ocr.bbox
                        }
                        for ocr in visual.ocr_results
                    ],
                    'detected_objects': [
                        {
                            'class': obj.class_name,
                            'confidence': obj.confidence,
                            'bbox': obj.bbox
                        }
                        for obj in visual.object_detection_results
                    ]
                }
                visual_data['frames'].append(frame_data)
            
            # 융합 메타데이터
            fusion_metadata = {
                'fusion_confidence': {
                    'text_matching': fused_result.fusion_confidence.text_matching_score,
                    'temporal_alignment': fused_result.fusion_confidence.temporal_alignment_score,
                    'semantic_coherence': fused_result.fusion_confidence.semantic_coherence_score,
                    'overall': fused_result.fusion_confidence.overall_confidence
                },
                'visual_confirmations': fused_result.visual_confirmations,
                'consistency_check': fused_result.consistency_check,
                'summary': fused_result.fusion_summary
            }
            
            # 최종 프롬프트 데이터 구성
            prompt_data = {
                'audio_analysis': audio_data,
                'visual_analysis': visual_data,
                'fusion_metadata': fusion_metadata,
                'analysis_context': {
                    'confidence_level': 'high' if fused_result.fusion_confidence.overall_confidence >= 0.8 else 
                                      'medium' if fused_result.fusion_confidence.overall_confidence >= 0.6 else 'low',
                    'data_quality': self._assess_data_quality(fused_result),
                    'recommended_focus': self._recommend_analysis_focus(fused_result)
                }
            }
            
            self.logger.debug("Gemini 프롬프트 데이터 생성 완료")
            return prompt_data
            
        except Exception as e:
            self.logger.error(f"프롬프트 데이터 생성 실패: {str(e)}")
            raise
    
    def _assess_data_quality(self, fused_result: FusedAnalysisResult) -> str:
        """데이터 품질 평가"""
        # 음성 데이터 품질
        audio_quality = len(fused_result.audio_analysis.segments) > 0 and len(fused_result.audio_analysis.full_text) > 10
        
        # 시각 데이터 품질
        visual_quality = len(fused_result.visual_analysis) > 0 and any(
            len(v.ocr_results) > 0 or len(v.object_detection_results) > 0 
            for v in fused_result.visual_analysis
        )
        
        # 융합 품질
        fusion_quality = fused_result.fusion_confidence.overall_confidence >= 0.5
        
        if audio_quality and visual_quality and fusion_quality:
            return 'excellent'
        elif (audio_quality and visual_quality) or fusion_quality:
            return 'good'
        elif audio_quality or visual_quality:
            return 'fair'
        else:
            return 'poor'
    
    def _recommend_analysis_focus(self, fused_result: FusedAnalysisResult) -> List[str]:
        """분석 포커스 추천"""
        recommendations = []
        
        # 음성 위주 분석
        if fused_result.audio_analysis.full_text and len(fused_result.product_mentions) > 0:
            recommendations.append('focus_on_audio_mentions')
        
        # 시각 위주 분석
        if fused_result.visual_confirmations and len(fused_result.visual_confirmations) > 0:
            recommendations.append('focus_on_visual_confirmations')
        
        # 융합 분석
        if fused_result.consistency_check and fused_result.fusion_confidence.overall_confidence >= 0.7:
            recommendations.append('high_confidence_fusion')
        
        # 품질 개선 필요
        if fused_result.fusion_confidence.overall_confidence < 0.5:
            recommendations.append('require_manual_review')
        
        return recommendations if recommendations else ['general_analysis']
    
    def validate_fusion_result(self, fused_result: FusedAnalysisResult) -> Dict[str, Any]:
        """
        융합 결과 검증
        
        Args:
            fused_result: 검증할 융합 결과
            
        Returns:
            검증 결과 보고서
        """
        try:
            validation_report = {
                'is_valid': True,
                'issues': [],
                'warnings': [],
                'quality_score': 0.0,
                'recommendations': []
            }
            
            # 시간 정합성 검증
            if fused_result.timeframe_start >= fused_result.timeframe_end:
                validation_report['is_valid'] = False
                validation_report['issues'].append('Invalid timeframe: start >= end')
            
            # 음성 데이터 검증
            if not fused_result.audio_analysis.full_text.strip():
                validation_report['warnings'].append('Empty audio transcription')
            
            # 시각 데이터 검증
            if not fused_result.visual_analysis:
                validation_report['warnings'].append('No visual analysis data')
            
            # 융합 신뢰도 검증
            if fused_result.fusion_confidence.overall_confidence < 0.3:
                validation_report['warnings'].append('Low fusion confidence')
                validation_report['recommendations'].append('Consider manual review')
            
            # 일치성 검증
            if not fused_result.consistency_check:
                validation_report['warnings'].append('Audio-visual inconsistency detected')
            
            # 품질 점수 계산
            quality_factors = [
                1.0 if fused_result.audio_analysis.full_text.strip() else 0.0,
                1.0 if fused_result.visual_analysis else 0.0,
                fused_result.fusion_confidence.overall_confidence,
                1.0 if fused_result.consistency_check else 0.5
            ]
            validation_report['quality_score'] = sum(quality_factors) / len(quality_factors)
            
            self.logger.debug(f"융합 결과 검증 완료 - 품질점수: {validation_report['quality_score']:.3f}")
            return validation_report
            
        except Exception as e:
            self.logger.error(f"융합 결과 검증 실패: {str(e)}")
            return {
                'is_valid': False,
                'issues': [f'Validation error: {str(e)}'],
                'warnings': [],
                'quality_score': 0.0,
                'recommendations': ['Manual inspection required']
            }
    
    def get_fusion_info(self) -> Dict[str, Any]:
        """융합 엔진 정보 반환"""
        return {
            'status': 'ready',
            'time_tolerance': self.time_tolerance,
            'text_similarity_threshold': self.text_similarity_threshold,
            'confidence_threshold': self.confidence_threshold,
            'supported_modalities': ['audio', 'visual'],
            'fusion_algorithms': ['text_matching', 'temporal_alignment', 'semantic_coherence']
        }