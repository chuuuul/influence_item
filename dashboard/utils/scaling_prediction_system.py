"""
T03A_S03_M03: 통합 스케일링 예측 시스템
메트릭 수집, 예측 모델, 스케일링 결정을 통합한 시스템
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

# 개발한 모듈들 import
from .scaling_metrics_collector import ScalingMetricsCollector, get_scaling_metrics_collector
from .timeseries_data_manager import TimeSeriesDataManager
from .demand_prediction_model import DemandPredictionModel
from .scaling_decision_engine import ScalingDecisionEngine, ScalingAction
from .model_accuracy_evaluator import ModelAccuracyEvaluator, get_model_accuracy_evaluator

logger = logging.getLogger(__name__)


class ScalingPredictionSystem:
    """통합 스케일링 예측 시스템"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 시스템 설정
        """
        self.config = config or self._get_default_config()
        
        # 컴포넌트 초기화
        self.metrics_collector = get_scaling_metrics_collector(
            db_path=self.config['metrics_db_path']
        )
        
        self.data_manager = TimeSeriesDataManager(
            db_path=self.config['metrics_db_path']
        )
        
        self.prediction_model = DemandPredictionModel(
            model_type=self.config['model_type'],
            model_save_path=self.config['model_save_path']
        )
        
        self.decision_engine = ScalingDecisionEngine(
            db_path=self.config['decisions_db_path']
        )
        
        self.accuracy_evaluator = get_model_accuracy_evaluator(
            db_path=self.config['accuracy_db_path']
        )
        
        # 시스템 상태
        self.is_running = False
        self.system_thread = None
        self.last_prediction_time = None
        self.last_training_time = None
        
        # 성능 카운터
        self.prediction_count = 0
        self.decision_count = 0
        self.training_count = 0
        
        # 모델 로드 시도
        self.prediction_model.load_models()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            'metrics_db_path': 'scaling_metrics.db',
            'decisions_db_path': 'scaling_decisions.db',
            'accuracy_db_path': 'model_accuracy.db',
            'model_save_path': 'models/',
            'model_type': 'random_forest',
            'prediction_interval_minutes': 60,  # 1시간마다 예측
            'training_interval_hours': 24,      # 24시간마다 재훈련
            'accuracy_check_interval_hours': 6, # 6시간마다 정확도 체크
            'metrics_collection_interval': 60,  # 1분마다 메트릭 수집
            'min_training_samples': 100,        # 최소 훈련 샘플 수
            'accuracy_threshold': 80.0,         # 최소 요구 정확도
            'auto_retraining': True,            # 자동 재훈련 활성화
            'enable_predictions': True,         # 예측 기능 활성화
            'enable_decisions': True            # 스케일링 결정 활성화
        }
    
    def start_system(self):
        """시스템 시작"""
        if self.is_running:
            logger.info("Scaling prediction system is already running")
            return
        
        try:
            # 메트릭 수집 시작
            self.metrics_collector.start_collection()
            
            # 시스템 메인 루프 시작
            self.is_running = True
            self.system_thread = threading.Thread(target=self._system_loop, daemon=True)
            self.system_thread.start()
            
            logger.info("Scaling prediction system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start scaling prediction system: {e}")
            self.is_running = False
    
    def stop_system(self):
        """시스템 중지"""
        try:
            self.is_running = False
            
            # 메트릭 수집 중지
            self.metrics_collector.stop_collection()
            
            # 메인 스레드 종료 대기
            if self.system_thread and self.system_thread.is_alive():
                self.system_thread.join(timeout=10)
            
            logger.info("Scaling prediction system stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop scaling prediction system: {e}")
    
    def _system_loop(self):
        """시스템 메인 루프"""
        last_prediction = datetime.min
        last_training = datetime.min
        last_accuracy_check = datetime.min
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # 1. 모델 훈련 체크
                if (current_time - last_training).total_seconds() >= self.config['training_interval_hours'] * 3600:
                    if self._should_retrain_model():
                        self._train_model()
                        last_training = current_time
                        self.training_count += 1
                
                # 2. 예측 수행
                if (current_time - last_prediction).total_seconds() >= self.config['prediction_interval_minutes'] * 60:
                    if self.config['enable_predictions']:
                        self._make_prediction()
                        last_prediction = current_time
                        self.prediction_count += 1
                
                # 3. 정확도 체크
                if (current_time - last_accuracy_check).total_seconds() >= self.config['accuracy_check_interval_hours'] * 3600:
                    self._check_model_accuracy()
                    last_accuracy_check = current_time
                
                # 4. 스케일링 결정 (예측이 있는 경우)
                if self.config['enable_decisions'] and self.last_prediction_time:
                    self._make_scaling_decision()
                    self.decision_count += 1
                
                # 5. 잠시 대기
                time.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"Error in system loop: {e}")
                time.sleep(60)  # 에러 발생 시 1분 대기
    
    def _should_retrain_model(self) -> bool:
        """모델 재훈련 필요성 판단"""
        try:
            # 모델이 훈련되지 않은 경우
            if not self.prediction_model.is_trained:
                return True
            
            # 자동 재훈련이 비활성화된 경우
            if not self.config['auto_retraining']:
                return False
            
            # 충분한 훈련 데이터가 있는지 확인
            training_data = self.data_manager.get_training_data(hours=168)  # 7일
            if training_data is None:
                return False
            
            features, target = training_data
            if len(features) < self.config['min_training_samples']:
                logger.debug(f"Insufficient training samples: {len(features)}")
                return False
            
            # 모델 정확도가 임계값 이하인 경우
            health_report = self.accuracy_evaluator.check_model_health()
            if health_report.get('requires_retraining', False):
                logger.info("Model retraining triggered by accuracy check")
                return True
            
            return True  # 주기적 재훈련
            
        except Exception as e:
            logger.error(f"Failed to check retraining necessity: {e}")
            return False
    
    def _train_model(self):
        """모델 훈련"""
        try:
            logger.info("Starting model training...")
            
            # 훈련 데이터 준비
            training_data = self.data_manager.get_training_data(hours=168)  # 7일
            if training_data is None:
                logger.error("No training data available")
                return
            
            features, target = training_data
            logger.info(f"Training with {len(features)} samples, {len(features.columns)} features")
            
            # 모델 훈련
            results = self.prediction_model.train_models(features, target)
            
            if results:
                self.last_training_time = datetime.now()
                logger.info(f"Model training completed successfully: {results}")
            else:
                logger.error("Model training failed")
                
        except Exception as e:
            logger.error(f"Failed to train model: {e}")
    
    def _make_prediction(self):
        """예측 수행"""
        try:
            if not self.prediction_model.is_trained:
                logger.debug("Model not trained, skipping prediction")
                return
            
            # 최신 특성 데이터 가져오기
            latest_features = self.data_manager.get_latest_features()
            if latest_features is None or latest_features.empty:
                logger.debug("No latest features available for prediction")
                return
            
            # 예측 수행
            prediction_result = self.prediction_model.predict_demand(latest_features, hours_ahead=1)
            
            if prediction_result:
                predicted_value = prediction_result['prediction']
                model_used = prediction_result['model_used']
                confidence = prediction_result.get('confidence_intervals', {}).get(model_used, {}).get('upper', 1.0)
                
                # 예측 기록
                target_time = datetime.now() + timedelta(hours=1)
                record_id = self.accuracy_evaluator.record_prediction(
                    predicted_value=predicted_value,
                    target_time=target_time,
                    model_used=model_used,
                    confidence=confidence
                )
                
                self.last_prediction_time = datetime.now()
                logger.info(f"Prediction made: {predicted_value:.2f} (model: {model_used}, record: {record_id})")
                
                # 메트릭 수집기에 예측 정보 저장
                current_metrics = self.metrics_collector.get_current_metrics()
                if current_metrics:
                    current_metrics.predicted_load_1h = predicted_value
                
            else:
                logger.error("Prediction failed")
                
        except Exception as e:
            logger.error(f"Failed to make prediction: {e}")
    
    def _check_model_accuracy(self):
        """모델 정확도 체크"""
        try:
            # 현재 메트릭으로 예측 검증
            current_metrics = self.metrics_collector.get_current_metrics()
            if current_metrics:
                metrics_dict = {
                    'processing_queue_length': current_metrics.processing_queue_length,
                    'cpu_percent': current_metrics.cpu_percent,
                    'memory_percent': current_metrics.memory_percent
                }
                
                # 배치 검증
                validated_count = self.accuracy_evaluator.batch_validate_predictions(metrics_dict)
                logger.debug(f"Validated {validated_count} predictions")
            
            # 정확도 평가
            accuracy_metrics = self.accuracy_evaluator.evaluate_model_accuracy(hours=24)
            if accuracy_metrics:
                logger.info(f"Model accuracy: {accuracy_metrics.accuracy_percentage:.2f}%")
                
                # 임계값 미달 시 경고
                if accuracy_metrics.accuracy_percentage < self.config['accuracy_threshold']:
                    logger.warning(f"Model accuracy below threshold: {accuracy_metrics.accuracy_percentage:.2f}%")
            
        except Exception as e:
            logger.error(f"Failed to check model accuracy: {e}")
    
    def _make_scaling_decision(self):
        """스케일링 결정"""
        try:
            # 현재 메트릭 가져오기
            current_metrics = self.metrics_collector.get_current_metrics()
            if not current_metrics:
                logger.debug("No current metrics available for scaling decision")
                return
            
            metrics_dict = {
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'processing_queue_length': current_metrics.processing_queue_length,
                'avg_response_time': current_metrics.avg_response_time,
                'success_rate': current_metrics.success_rate,
                'memory_available_gb': current_metrics.memory_available_gb,
                'active_connections': current_metrics.active_connections
            }
            
            # 예측 메트릭 (있는 경우)
            predicted_metrics = None
            if current_metrics.predicted_load_1h is not None:
                predicted_metrics = {
                    'prediction': current_metrics.predicted_load_1h
                }
            
            # 스케일링 결정
            decision = self.decision_engine.make_scaling_decision(
                current_metrics=metrics_dict,
                predicted_metrics=predicted_metrics,
                current_instance_count=1  # 기본값, 실제 환경에서는 동적으로 가져와야 함
            )
            
            # 결정 로깅
            if decision.action != ScalingAction.MAINTAIN:
                logger.info(f"Scaling decision: {decision.action.value} "
                          f"(confidence: {decision.confidence:.2f}, urgency: {decision.urgency})")
                
                # 실제 스케일링 실행은 여기서 구현 (T03B_S03_M03에서 처리)
                # self._execute_scaling_decision(decision)
            
        except Exception as e:
            logger.error(f"Failed to make scaling decision: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        try:
            current_metrics = self.metrics_collector.get_current_metrics()
            model_status = self.prediction_model.get_model_status()
            accuracy_health = self.accuracy_evaluator.check_model_health()
            
            return {
                'system_running': self.is_running,
                'last_prediction_time': self.last_prediction_time.isoformat() if self.last_prediction_time else None,
                'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
                'performance_counters': {
                    'predictions_made': self.prediction_count,
                    'decisions_made': self.decision_count,
                    'training_cycles': self.training_count
                },
                'current_metrics': {
                    'cpu_percent': current_metrics.cpu_percent if current_metrics else 0,
                    'memory_percent': current_metrics.memory_percent if current_metrics else 0,
                    'queue_length': current_metrics.processing_queue_length if current_metrics else 0,
                    'predicted_load': current_metrics.predicted_load_1h if current_metrics else None
                },
                'model_status': model_status,
                'accuracy_health': {
                    'health_score': accuracy_health.get('health_score', 0),
                    'health_grade': accuracy_health.get('health_grade', 'Unknown'),
                    'requires_retraining': accuracy_health.get('requires_retraining', False)
                },
                'configuration': self.config
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {'error': str(e)}
    
    def force_prediction(self) -> Dict[str, Any]:
        """강제 예측 실행"""
        try:
            self._make_prediction()
            return {'success': True, 'message': 'Prediction executed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def force_training(self) -> Dict[str, Any]:
        """강제 모델 훈련"""
        try:
            self._train_model()
            return {'success': True, 'message': 'Model training executed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_recent_decisions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """최근 스케일링 결정 조회"""
        try:
            return self.decision_engine.get_decision_history(hours=hours)
        except Exception as e:
            logger.error(f"Failed to get recent decisions: {e}")
            return []
    
    def get_accuracy_report(self) -> Dict[str, Any]:
        """정확도 보고서 조회"""
        try:
            # 임시 파일로 보고서 생성
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_path = f.name
            
            success = self.accuracy_evaluator.generate_accuracy_report(temp_path)
            if success:
                with open(temp_path, 'r') as f:
                    report = json.load(f)
                Path(temp_path).unlink()  # 임시 파일 삭제
                return report
            else:
                return {'error': 'Failed to generate accuracy report'}
                
        except Exception as e:
            logger.error(f"Failed to get accuracy report: {e}")
            return {'error': str(e)}
    
    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """설정 업데이트"""
        try:
            for key, value in new_config.items():
                if key in self.config:
                    self.config[key] = value
                    logger.info(f"Updated config {key} to {value}")
                else:
                    logger.warning(f"Unknown config parameter: {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            return False


# 전역 스케일링 예측 시스템 인스턴스
_scaling_prediction_system = None


def get_scaling_prediction_system(config: Optional[Dict[str, Any]] = None) -> ScalingPredictionSystem:
    """싱글톤 스케일링 예측 시스템 반환"""
    global _scaling_prediction_system
    if _scaling_prediction_system is None:
        _scaling_prediction_system = ScalingPredictionSystem(config)
    return _scaling_prediction_system