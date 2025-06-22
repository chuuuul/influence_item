"""
파이프라인 상태 관리 시스템

파이프라인 실행 상태를 추적하고 중단 시 복구 지점을 관리합니다.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from config import Config


class StateType(Enum):
    """상태 타입"""
    CHECKPOINT = "checkpoint"
    PROGRESS = "progress"
    ERROR = "error"
    COMPLETION = "completion"


@dataclass
class PipelineState:
    """파이프라인 상태 데이터"""
    video_url: str
    current_step: str
    status: str
    start_time: float
    last_update: float
    completed_steps: list
    step_data: Dict[str, Any]
    error_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineState':
        """딕셔너리에서 생성"""
        return cls(**data)


class StateManager:
    """파이프라인 상태 관리자"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        상태 관리자 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config or Config
        self.logger = self._setup_logger()
        self.state_dir = Path(self.config.get_temp_dir()) / "pipeline_states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _get_state_file_path(self, video_url: str) -> Path:
        """상태 파일 경로 생성"""
        # URL을 안전한 파일명으로 변환
        safe_name = video_url.replace("https://", "").replace("/", "_").replace("?", "_").replace("&", "_")
        return self.state_dir / f"{safe_name}.json"
    
    def save_state(self, state: PipelineState) -> bool:
        """
        파이프라인 상태 저장
        
        Args:
            state: 저장할 상태
            
        Returns:
            저장 성공 여부
        """
        try:
            state_file = self._get_state_file_path(state.video_url)
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"파이프라인 상태 저장: {state_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"상태 저장 실패: {str(e)}")
            return False
    
    def load_state(self, video_url: str) -> Optional[PipelineState]:
        """
        파이프라인 상태 로드
        
        Args:
            video_url: 영상 URL
            
        Returns:
            로드된 상태 또는 None
        """
        try:
            state_file = self._get_state_file_path(video_url)
            
            if not state_file.exists():
                return None
            
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = PipelineState.from_dict(data)
            self.logger.debug(f"파이프라인 상태 로드: {state_file}")
            return state
            
        except Exception as e:
            self.logger.error(f"상태 로드 실패: {str(e)}")
            return None
    
    def delete_state(self, video_url: str) -> bool:
        """
        파이프라인 상태 삭제
        
        Args:
            video_url: 영상 URL
            
        Returns:
            삭제 성공 여부
        """
        try:
            state_file = self._get_state_file_path(video_url)
            
            if state_file.exists():
                state_file.unlink()
                self.logger.debug(f"파이프라인 상태 삭제: {state_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"상태 삭제 실패: {str(e)}")
            return False
    
    def create_checkpoint(
        self, 
        video_url: str, 
        step_name: str, 
        step_data: Dict[str, Any], 
        completed_steps: list
    ) -> Optional[PipelineState]:
        """
        체크포인트 생성
        
        Args:
            video_url: 영상 URL
            step_name: 현재 단계명
            step_data: 단계별 데이터
            completed_steps: 완료된 단계 목록
            
        Returns:
            생성된 상태
        """
        try:
            state = PipelineState(
                video_url=video_url,
                current_step=step_name,
                status="checkpoint",
                start_time=time.time(),
                last_update=time.time(),
                completed_steps=completed_steps.copy(),
                step_data=step_data.copy()
            )
            
            if self.save_state(state):
                return state
            
            return None
            
        except Exception as e:
            self.logger.error(f"체크포인트 생성 실패: {str(e)}")
            return None
    
    def update_progress(
        self, 
        video_url: str, 
        step_name: str, 
        progress_data: Dict[str, Any]
    ) -> bool:
        """
        진행 상황 업데이트
        
        Args:
            video_url: 영상 URL
            step_name: 현재 단계명
            progress_data: 진행 데이터
            
        Returns:
            업데이트 성공 여부
        """
        try:
            state = self.load_state(video_url)
            
            if not state:
                # 새 상태 생성
                state = PipelineState(
                    video_url=video_url,
                    current_step=step_name,
                    status="progress",
                    start_time=time.time(),
                    last_update=time.time(),
                    completed_steps=[],
                    step_data=progress_data
                )
            else:
                # 기존 상태 업데이트
                state.current_step = step_name
                state.status = "progress"
                state.last_update = time.time()
                state.step_data.update(progress_data)
            
            return self.save_state(state)
            
        except Exception as e:
            self.logger.error(f"진행 상황 업데이트 실패: {str(e)}")
            return False
    
    def mark_step_completed(self, video_url: str, step_name: str) -> bool:
        """
        단계 완료 표시
        
        Args:
            video_url: 영상 URL
            step_name: 완료된 단계명
            
        Returns:
            업데이트 성공 여부
        """
        try:
            state = self.load_state(video_url)
            
            if state and step_name not in state.completed_steps:
                state.completed_steps.append(step_name)
                state.last_update = time.time()
                return self.save_state(state)
            
            return True
            
        except Exception as e:
            self.logger.error(f"단계 완료 표시 실패: {str(e)}")
            return False
    
    def mark_error(
        self, 
        video_url: str, 
        step_name: str, 
        error_info: Dict[str, Any]
    ) -> bool:
        """
        에러 상태 표시
        
        Args:
            video_url: 영상 URL
            step_name: 에러 발생 단계명
            error_info: 에러 정보
            
        Returns:
            업데이트 성공 여부
        """
        try:
            state = self.load_state(video_url)
            
            if not state:
                state = PipelineState(
                    video_url=video_url,
                    current_step=step_name,
                    status="error",
                    start_time=time.time(),
                    last_update=time.time(),
                    completed_steps=[],
                    step_data={},
                    error_info=error_info
                )
            else:
                state.current_step = step_name
                state.status = "error"
                state.last_update = time.time()
                state.error_info = error_info
            
            return self.save_state(state)
            
        except Exception as e:
            self.logger.error(f"에러 상태 표시 실패: {str(e)}")
            return False
    
    def mark_completed(self, video_url: str, final_data: Dict[str, Any]) -> bool:
        """
        파이프라인 완료 표시
        
        Args:
            video_url: 영상 URL
            final_data: 최종 결과 데이터
            
        Returns:
            업데이트 성공 여부
        """
        try:
            state = self.load_state(video_url)
            
            if state:
                state.status = "completed"
                state.last_update = time.time()
                state.step_data['final_result'] = final_data
                
                # 상태 저장 후 파일 삭제 (완료된 작업은 영구 저장 불필요)
                if self.save_state(state):
                    # 잠시 후 상태 파일 삭제 (완료 로그 목적으로 짧은 시간 유지)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"완료 상태 표시 실패: {str(e)}")
            return False
    
    def can_resume(self, video_url: str) -> bool:
        """
        파이프라인 재개 가능 여부 확인
        
        Args:
            video_url: 영상 URL
            
        Returns:
            재개 가능 여부
        """
        state = self.load_state(video_url)
        return state is not None and state.status in ["checkpoint", "progress"]
    
    def get_resume_point(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        재개 지점 정보 반환
        
        Args:
            video_url: 영상 URL
            
        Returns:
            재개 지점 정보
        """
        state = self.load_state(video_url)
        
        if not state:
            return None
        
        return {
            'current_step': state.current_step,
            'completed_steps': state.completed_steps,
            'step_data': state.step_data,
            'elapsed_time': time.time() - state.start_time
        }
    
    def cleanup_old_states(self, max_age_hours: int = 24) -> int:
        """
        오래된 상태 파일 정리
        
        Args:
            max_age_hours: 최대 보관 시간 (시간)
            
        Returns:
            삭제된 파일 수
        """
        try:
            deleted_count = 0
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for state_file in self.state_dir.glob("*.json"):
                try:
                    file_age = current_time - state_file.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        state_file.unlink()
                        deleted_count += 1
                        self.logger.debug(f"오래된 상태 파일 삭제: {state_file}")
                        
                except Exception as e:
                    self.logger.warning(f"상태 파일 정리 실패: {state_file}: {str(e)}")
            
            self.logger.info(f"상태 파일 정리 완료 - {deleted_count}개 파일 삭제")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"상태 파일 정리 실패: {str(e)}")
            return 0