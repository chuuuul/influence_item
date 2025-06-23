"""
GPU 서버 API 엔드포인트
Whisper, YOLO, OCR 모델 서빙 및 배치 처리
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import torch
import logging
import asyncio
import base64
import io
from pathlib import Path
import sys

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.config import Config
from src.whisper_processor.whisper_processor import WhisperProcessor
from src.visual_processor.object_detector import ObjectDetector
from src.visual_processor.ocr_processor import OCRProcessor
from src.gpu_optimizer.gpu_optimizer import GPUOptimizer

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Influence Item GPU Server", 
    version="1.0.0",
    description="AI 모델 서빙 API (Whisper, YOLO, OCR)"
)

# 글로벌 모델 객체들
config = Config()
gpu_optimizer = None
whisper_processor = None
object_detector = None
ocr_processor = None

# 모델 로딩 상태
models_loaded = {
    "whisper": False,
    "yolo": False,
    "ocr": False
}

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 모델 초기화"""
    global gpu_optimizer, whisper_processor, object_detector, ocr_processor
    
    logger.info("🚀 GPU 서버 시작 중...")
    logger.info(f"CUDA 사용 가능: {torch.cuda.is_available()}")
    
    try:
        # GPU 최적화 초기화
        logger.info("GPU 최적화 시스템 초기화 중...")
        gpu_optimizer = GPUOptimizer(config)
        
        # Whisper 모델 로딩
        logger.info("Whisper 모델 로딩 중...")
        whisper_processor = WhisperProcessor(config)
        if whisper_processor.model is not None:
            models_loaded["whisper"] = True
            logger.info("✅ Whisper 모델 로딩 완료")
        
        # YOLO 모델 로딩
        logger.info("YOLO 모델 로딩 중...")
        object_detector = ObjectDetector(config, gpu_optimizer=gpu_optimizer)
        if object_detector.model is not None:
            models_loaded["yolo"] = True
            logger.info("✅ YOLO 모델 로딩 완료")
        
        # OCR 모델 로딩
        logger.info("EasyOCR 모델 로딩 중...")
        ocr_processor = OCRProcessor(config)
        if ocr_processor.reader is not None:
            models_loaded["ocr"] = True
            logger.info("✅ EasyOCR 모델 로딩 완료")
        
        logger.info("🎉 모든 모델 로딩 완료")
        
        # GPU 메모리 정보 출력
        if gpu_optimizer and gpu_optimizer.is_gpu_available:
            memory_info = gpu_optimizer.get_memory_info()
            logger.info(f"GPU 메모리 상태: 총 {memory_info['total']}MB, 사용 중 {memory_info['used']}MB")
        
    except Exception as e:
        logger.error(f"모델 로딩 중 오류 발생: {str(e)}")
        # 부분적으로라도 서비스 제공
        logger.warning("일부 모델만으로 서비스 시작")

class AudioRequest(BaseModel):
    audio_url: str
    language: Optional[str] = "ko"

class VideoFrameRequest(BaseModel):
    frames: List[str]  # Base64 encoded frames
    target_objects: Optional[List[str]] = None

class OCRRequest(BaseModel):
    images: List[str]  # Base64 encoded images
    languages: Optional[List[str]] = ["ko", "en"]

# 배치 처리 엔드포인트들
@app.post("/process/whisper/batch")
async def process_whisper_batch(request: List[AudioRequest]):
    """Whisper 배치 처리"""
    if not models_loaded["whisper"]:
        raise HTTPException(status_code=503, detail="Whisper 모델이 로드되지 않음")
    
    try:
        def process_audio_batch(audio_requests):
            results = []
            for req in audio_requests:
                # 실제 Whisper 처리 로직
                result = whisper_processor.transcribe_from_url(req.audio_url)
                results.append(result)
            return results
        
        # GPU 최적화된 배치 처리
        if gpu_optimizer:
            results = gpu_optimizer.process_batch(request, process_audio_batch)
        else:
            results = process_audio_batch(request)
        
        return {"results": results, "processed_count": len(request)}
    
    except Exception as e:
        logger.error(f"Whisper 배치 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"처리 오류: {str(e)}")

@app.post("/process/yolo/batch")
async def process_yolo_batch(request: List[VideoFrameRequest]):
    """YOLO 배치 처리"""
    if not models_loaded["yolo"]:
        raise HTTPException(status_code=503, detail="YOLO 모델이 로드되지 않음")
    
    try:
        def process_frames_batch(frame_requests):
            results = []
            for req in frame_requests:
                # 실제 YOLO 처리 로직
                batch_result = []
                for frame_b64 in req.frames:
                    # Base64 디코딩 및 객체 탐지
                    result = object_detector.detect_objects_from_base64(frame_b64)
                    batch_result.append(result)
                results.append(batch_result)
            return results
        
        # GPU 최적화된 배치 처리
        if gpu_optimizer:
            results = gpu_optimizer.process_batch(request, process_frames_batch)
        else:
            results = process_frames_batch(request)
        
        return {"results": results, "processed_count": len(request)}
    
    except Exception as e:
        logger.error(f"YOLO 배치 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"처리 오류: {str(e)}")

@app.post("/process/ocr/batch")
async def process_ocr_batch(request: List[OCRRequest]):
    """OCR 배치 처리"""
    if not models_loaded["ocr"]:
        raise HTTPException(status_code=503, detail="OCR 모델이 로드되지 않음")
    
    try:
        def process_images_batch(ocr_requests):
            results = []
            for req in ocr_requests:
                # 실제 OCR 처리 로직
                batch_result = []
                for image_b64 in req.images:
                    # Base64 디코딩 및 텍스트 추출
                    result = ocr_processor.extract_text_from_base64(image_b64)
                    batch_result.append(result)
                results.append(batch_result)
            return results
        
        # GPU 최적화된 배치 처리
        if gpu_optimizer:
            results = gpu_optimizer.process_batch(request, process_images_batch)
        else:
            results = process_images_batch(request)
        
        return {"results": results, "processed_count": len(request)}
    
    except Exception as e:
        logger.error(f"OCR 배치 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"처리 오류: {str(e)}")

@app.get("/health")
async def health_check():
    """헬스 체크"""
    gpu_available = torch.cuda.is_available()
    return {
        "status": "healthy",
        "gpu_available": gpu_available,
        "models_loaded": models_loaded
    }

@app.post("/api/whisper/transcribe")
async def transcribe_audio(request: AudioRequest):
    """Whisper 음성 인식"""
    if not models_loaded["whisper"]:
        raise HTTPException(status_code=503, detail="Whisper 모델이 로드되지 않음")
    
    # TODO: 실제 Whisper 처리 로직 구현
    return {
        "transcript": "Sample transcript",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "Sample segment"}
        ]
    }

@app.post("/api/yolo/detect")
async def detect_objects(request: VideoFrameRequest):
    """YOLO 객체 탐지"""
    if not models_loaded["yolo"]:
        raise HTTPException(status_code=503, detail="YOLO 모델이 로드되지 않음")
    
    # TODO: 실제 YOLO 처리 로직 구현
    return {
        "detections": [
            {"class": "person", "confidence": 0.9, "bbox": [100, 100, 200, 200]}
        ]
    }

@app.post("/api/ocr/extract")
async def extract_text(request: OCRRequest):
    """OCR 텍스트 추출"""
    if not models_loaded["ocr"]:
        raise HTTPException(status_code=503, detail="OCR 모델이 로드되지 않음")
    
    # TODO: 실제 OCR 처리 로직 구현
    return {
        "texts": [
            {"text": "Sample text", "confidence": 0.95, "bbox": [50, 50, 150, 80]}
        ]
    }

@app.get("/api/models/status")
async def get_models_status():
    """모델 상태 조회"""
    return {
        "models": models_loaded,
        "gpu_info": {
            "available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)