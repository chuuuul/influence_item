"""
T03A_S03_M03: 수요 예측 모델
Random Forest와 ARIMA를 활용한 시계열 수요 예측 및 스케일링 결정 시스템
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
import sqlite3
from pathlib import Path

# ARIMA 모델을 위한 imports (선택적)
try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.seasonal import seasonal_decompose
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False
    logging.warning("statsmodels not available, ARIMA functionality disabled")

logger = logging.getLogger(__name__)


class DemandPredictionModel:
    """수요 예측 모델"""
    
    def __init__(self, model_type: str = 'random_forest', model_save_path: str = "models/"):
        """
        Args:
            model_type: 모델 타입 ('random_forest', 'arima', 'ensemble')
            model_save_path: 모델 저장 경로
        """
        self.model_type = model_type
        self.model_save_path = Path(model_save_path)
        self.model_save_path.mkdir(exist_ok=True)
        
        # 모델 초기화
        self.rf_model = None
        self.arima_model = None
        self.is_trained = False
        self.feature_names = []
        self.target_column = 'processing_queue_length'
        
        # 모델 성능 메트릭
        self.model_metrics = {}
        
        # 예측 정확도 추적
        self.prediction_history = []
        
    def train_random_forest(self, features: pd.DataFrame, target: pd.Series, 
                           test_size: float = 0.2) -> Dict[str, float]:
        """Random Forest 모델 훈련"""
        try:
            # 데이터 분할
            X_train, X_test, y_train, y_test = train_test_split(
                features, target, test_size=test_size, shuffle=False, random_state=42
            )
            
            # Random Forest 모델 생성
            self.rf_model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
            
            # 모델 훈련
            self.rf_model.fit(X_train, y_train)
            
            # 예측 및 평가
            y_pred_train = self.rf_model.predict(X_train)
            y_pred_test = self.rf_model.predict(X_test)
            
            # 성능 메트릭 계산
            metrics = {
                'train_mae': mean_absolute_error(y_train, y_pred_train),
                'train_mse': mean_squared_error(y_train, y_pred_train),
                'train_r2': r2_score(y_train, y_pred_train),
                'test_mae': mean_absolute_error(y_test, y_pred_test),
                'test_mse': mean_squared_error(y_test, y_pred_test),
                'test_r2': r2_score(y_test, y_pred_test),
                'accuracy_percentage': max(0, 100 - (mean_absolute_error(y_test, y_pred_test) / y_test.mean() * 100))
            }
            
            self.model_metrics['random_forest'] = metrics
            self.feature_names = features.columns.tolist()
            
            logger.info(f"Random Forest trained successfully. Test accuracy: {metrics['accuracy_percentage']:.2f}%")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to train Random Forest model: {e}")
            return {}
    
    def train_arima(self, target_series: pd.Series, order: Tuple[int, int, int] = (2, 1, 2)) -> Dict[str, float]:
        """ARIMA 모델 훈련"""
        if not ARIMA_AVAILABLE:
            logger.error("ARIMA not available - statsmodels not installed")
            return {}
        
        try:
            # 시계열 데이터 준비
            ts_data = target_series.dropna()
            
            if len(ts_data) < 50:
                logger.error("Insufficient data for ARIMA training (minimum 50 points required)")
                return {}
            
            # 트레인/테스트 분할 (시계열이므로 순차적)
            split_point = int(len(ts_data) * 0.8)
            train_data = ts_data.iloc[:split_point]
            test_data = ts_data.iloc[split_point:]
            
            # ARIMA 모델 생성 및 훈련
            self.arima_model = ARIMA(train_data, order=order)
            arima_result = self.arima_model.fit()
            
            # 예측
            forecast_steps = len(test_data)
            forecast = arima_result.forecast(steps=forecast_steps)
            
            # 성능 메트릭 계산
            mae = mean_absolute_error(test_data, forecast)
            mse = mean_squared_error(test_data, forecast)
            r2 = r2_score(test_data, forecast)
            accuracy = max(0, 100 - (mae / test_data.mean() * 100))
            
            metrics = {
                'test_mae': mae,
                'test_mse': mse,
                'test_r2': r2,
                'accuracy_percentage': accuracy,
                'aic': arima_result.aic,
                'bic': arima_result.bic
            }
            
            self.model_metrics['arima'] = metrics
            
            logger.info(f"ARIMA model trained successfully. Test accuracy: {accuracy:.2f}%")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to train ARIMA model: {e}")
            return {}
    
    def train_models(self, features: pd.DataFrame, target: pd.Series) -> Dict[str, Any]:
        """모델들을 훈련하고 최적 모델 선택"""
        try:
            results = {}
            
            if self.model_type in ['random_forest', 'ensemble']:
                rf_metrics = self.train_random_forest(features, target)
                results['random_forest'] = rf_metrics
            
            if self.model_type in ['arima', 'ensemble'] and ARIMA_AVAILABLE:
                arima_metrics = self.train_arima(target)
                results['arima'] = arima_metrics
            
            # 최적 모델 선택
            best_model = self._select_best_model()
            results['best_model'] = best_model
            
            self.is_trained = True
            
            # 모델 저장
            self.save_models()
            
            logger.info(f"Model training completed. Best model: {best_model}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to train models: {e}")
            return {}
    
    def _select_best_model(self) -> str:
        """최적 모델 선택"""
        try:
            if not self.model_metrics:
                return 'random_forest'  # 기본값
            
            best_accuracy = 0
            best_model = 'random_forest'
            
            for model_name, metrics in self.model_metrics.items():
                accuracy = metrics.get('accuracy_percentage', 0)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_model = model_name
            
            return best_model
            
        except Exception as e:
            logger.error(f"Failed to select best model: {e}")
            return 'random_forest'
    
    def predict_demand(self, features: pd.DataFrame = None, hours_ahead: int = 1) -> Dict[str, Any]:
        """수요 예측"""
        try:
            if not self.is_trained:
                logger.error("Model not trained yet")
                return {}
            
            predictions = {}
            confidence_intervals = {}
            
            # Random Forest 예측
            if self.rf_model is not None and features is not None:
                rf_pred = self.rf_model.predict(features)
                predictions['random_forest'] = float(rf_pred[0]) if len(rf_pred) > 0 else 0.0
                
                # Random Forest 신뢰구간 (트리들의 표준편차 기반)
                tree_predictions = np.array([tree.predict(features)[0] for tree in self.rf_model.estimators_])
                std = np.std(tree_predictions)
                mean_pred = np.mean(tree_predictions)
                confidence_intervals['random_forest'] = {
                    'lower': float(mean_pred - 1.96 * std),
                    'upper': float(mean_pred + 1.96 * std)
                }
            
            # ARIMA 예측
            if self.arima_model is not None and ARIMA_AVAILABLE:
                try:
                    arima_forecast = self.arima_model.forecast(steps=hours_ahead)
                    predictions['arima'] = float(arima_forecast[0]) if len(arima_forecast) > 0 else 0.0
                except:
                    logger.warning("ARIMA prediction failed, using Random Forest")
            
            # 앙상블 예측 (가중평균)
            if 'random_forest' in predictions and 'arima' in predictions:
                rf_weight = 0.7  # Random Forest에 더 높은 가중치
                arima_weight = 0.3
                ensemble_pred = (predictions['random_forest'] * rf_weight + 
                               predictions['arima'] * arima_weight)
                predictions['ensemble'] = float(ensemble_pred)
            
            # 최적 모델의 예측값 선택
            best_model = self._select_best_model()
            final_prediction = predictions.get(best_model, predictions.get('random_forest', 0.0))
            
            # 예측 결과 구성
            result = {
                'prediction': final_prediction,
                'model_used': best_model,
                'all_predictions': predictions,
                'confidence_intervals': confidence_intervals,
                'timestamp': datetime.now().isoformat(),
                'hours_ahead': hours_ahead
            }
            
            # 예측 이력에 추가
            self.prediction_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to predict demand: {e}")
            return {}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """특성 중요도 조회"""
        try:
            if self.rf_model is None:
                return {}
            
            importance_scores = self.rf_model.feature_importances_
            feature_importance = dict(zip(self.feature_names, importance_scores))
            
            # 중요도 순으로 정렬
            sorted_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))
            
            return sorted_importance
            
        except Exception as e:
            logger.error(f"Failed to get feature importance: {e}")
            return {}
    
    def validate_model_accuracy(self, actual_values: List[float], predicted_values: List[float]) -> Dict[str, float]:
        """모델 정확도 검증"""
        try:
            if len(actual_values) != len(predicted_values):
                logger.error("Actual and predicted values must have the same length")
                return {}
            
            mae = mean_absolute_error(actual_values, predicted_values)
            mse = mean_squared_error(actual_values, predicted_values)
            r2 = r2_score(actual_values, predicted_values)
            
            # MAPE (Mean Absolute Percentage Error)
            mape = np.mean(np.abs((np.array(actual_values) - np.array(predicted_values)) / np.array(actual_values))) * 100
            
            # 정확도 (100% - MAPE)
            accuracy = max(0, 100 - mape)
            
            validation_metrics = {
                'mae': mae,
                'mse': mse,
                'r2': r2,
                'mape': mape,
                'accuracy_percentage': accuracy,
                'validation_samples': len(actual_values)
            }
            
            logger.info(f"Model validation completed. Accuracy: {accuracy:.2f}%")
            return validation_metrics
            
        except Exception as e:
            logger.error(f"Failed to validate model accuracy: {e}")
            return {}
    
    def save_models(self):
        """모델 저장"""
        try:
            # Random Forest 모델 저장
            if self.rf_model is not None:
                rf_path = self.model_save_path / "random_forest_model.joblib"
                joblib.dump(self.rf_model, rf_path)
            
            # 메타데이터 저장
            metadata = {
                'model_type': self.model_type,
                'feature_names': self.feature_names,
                'target_column': self.target_column,
                'is_trained': self.is_trained,
                'model_metrics': self.model_metrics,
                'saved_at': datetime.now().isoformat()
            }
            
            metadata_path = self.model_save_path / "model_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info("Models saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    def load_models(self) -> bool:
        """모델 로드"""
        try:
            # 메타데이터 로드
            metadata_path = self.model_save_path / "model_metadata.json"
            if not metadata_path.exists():
                logger.warning("No saved model metadata found")
                return False
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.feature_names = metadata.get('feature_names', [])
            self.target_column = metadata.get('target_column', 'processing_queue_length')
            self.model_metrics = metadata.get('model_metrics', {})
            
            # Random Forest 모델 로드
            rf_path = self.model_save_path / "random_forest_model.joblib"
            if rf_path.exists():
                self.rf_model = joblib.load(rf_path)
                self.is_trained = True
                logger.info("Random Forest model loaded successfully")
            
            return self.is_trained
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False
    
    def retrain_if_needed(self, features: pd.DataFrame, target: pd.Series, 
                         accuracy_threshold: float = 80.0) -> bool:
        """필요시 모델 재훈련"""
        try:
            if not self.is_trained:
                logger.info("Model not trained, performing initial training")
                results = self.train_models(features, target)
                return len(results) > 0
            
            # 최근 예측 정확도 확인
            recent_accuracy = self._get_recent_accuracy()
            
            if recent_accuracy < accuracy_threshold:
                logger.info(f"Model accuracy ({recent_accuracy:.2f}%) below threshold ({accuracy_threshold:.2f}%), retraining...")
                results = self.train_models(features, target)
                return len(results) > 0
            
            logger.info(f"Model accuracy ({recent_accuracy:.2f}%) is acceptable, no retraining needed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to check/retrain model: {e}")
            return False
    
    def _get_recent_accuracy(self) -> float:
        """최근 예측 정확도 계산"""
        try:
            if not self.prediction_history:
                return 0.0
            
            # 최근 10개 예측의 평균 정확도 (실제 구현에서는 실제 값과 비교)
            # 현재는 모델 메트릭의 정확도 반환
            best_model = self._select_best_model()
            return self.model_metrics.get(best_model, {}).get('accuracy_percentage', 0.0)
            
        except Exception as e:
            logger.error(f"Failed to get recent accuracy: {e}")
            return 0.0
    
    def get_model_status(self) -> Dict[str, Any]:
        """모델 상태 조회"""
        try:
            return {
                'is_trained': self.is_trained,
                'model_type': self.model_type,
                'feature_count': len(self.feature_names),
                'target_column': self.target_column,
                'model_metrics': self.model_metrics,
                'prediction_history_count': len(self.prediction_history),
                'recent_accuracy': self._get_recent_accuracy(),
                'models_available': {
                    'random_forest': self.rf_model is not None,
                    'arima': self.arima_model is not None and ARIMA_AVAILABLE
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get model status: {e}")
            return {}