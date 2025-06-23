"""
T03A_S03_M03: 예측 모델 정확도 평가 시스템
실시간 예측 정확도 모니터링 및 모델 성능 평가
"""

import numpy as np
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
from dataclasses import dataclass, asdict
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """정확도 메트릭"""
    mae: float  # Mean Absolute Error
    mse: float  # Mean Squared Error
    rmse: float  # Root Mean Squared Error
    mape: float  # Mean Absolute Percentage Error
    r2: float  # R-squared
    accuracy_percentage: float
    samples_count: int
    evaluation_period: str
    timestamp: datetime


@dataclass
class PredictionRecord:
    """예측 기록"""
    prediction_time: datetime
    predicted_value: float
    actual_value: Optional[float]
    target_time: datetime
    model_used: str
    confidence: float
    error: Optional[float] = None
    percentage_error: Optional[float] = None


class ModelAccuracyEvaluator:
    """모델 정확도 평가기"""
    
    def __init__(self, db_path: str = "model_accuracy.db"):
        """
        Args:
            db_path: 정확도 평가 데이터베이스 경로
        """
        self.db_path = db_path
        self.accuracy_threshold = 80.0  # 최소 요구 정확도 (%)
        self.evaluation_window = 24  # 평가 윈도우 (시간)
        
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 예측 기록 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS prediction_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_time DATETIME NOT NULL,
                        target_time DATETIME NOT NULL,
                        predicted_value REAL NOT NULL,
                        actual_value REAL,
                        model_used TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        error REAL,
                        percentage_error REAL,
                        is_validated BOOLEAN DEFAULT FALSE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 정확도 평가 결과 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS accuracy_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        evaluation_time DATETIME NOT NULL,
                        evaluation_period TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        mae REAL NOT NULL,
                        mse REAL NOT NULL,
                        rmse REAL NOT NULL,
                        mape REAL NOT NULL,
                        r2 REAL NOT NULL,
                        accuracy_percentage REAL NOT NULL,
                        samples_count INTEGER NOT NULL,
                        meets_threshold BOOLEAN NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 모델 성능 추적 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS model_performance_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tracking_time DATETIME NOT NULL,
                        model_name TEXT NOT NULL,
                        accuracy_trend TEXT NOT NULL,
                        performance_score REAL NOT NULL,
                        recommendations TEXT,
                        requires_retraining BOOLEAN DEFAULT FALSE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 인덱스 생성
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_prediction_records_time ON prediction_records(prediction_time)",
                    "CREATE INDEX IF NOT EXISTS idx_prediction_records_target ON prediction_records(target_time)",
                    "CREATE INDEX IF NOT EXISTS idx_accuracy_evaluations_time ON accuracy_evaluations(evaluation_time)",
                    "CREATE INDEX IF NOT EXISTS idx_performance_tracking_time ON model_performance_tracking(tracking_time)"
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                conn.commit()
                logger.info("Model accuracy database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize model accuracy database: {e}")
            raise
    
    def record_prediction(self, predicted_value: float, target_time: datetime, 
                         model_used: str, confidence: float) -> int:
        """예측 기록"""
        try:
            prediction_time = datetime.now()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO prediction_records (
                        prediction_time, target_time, predicted_value, 
                        model_used, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (prediction_time, target_time, predicted_value, model_used, confidence))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                logger.debug(f"Prediction recorded: ID={record_id}, Value={predicted_value}")
                return record_id
                
        except Exception as e:
            logger.error(f"Failed to record prediction: {e}")
            return -1
    
    def validate_prediction(self, record_id: int, actual_value: float) -> bool:
        """예측 검증 (실제값과 비교)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 예측 기록 조회
                cursor.execute('''
                    SELECT predicted_value FROM prediction_records 
                    WHERE id = ? AND is_validated = FALSE
                ''', (record_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"Prediction record {record_id} not found or already validated")
                    return False
                
                predicted_value = result[0]
                
                # 오차 계산
                error = abs(actual_value - predicted_value)
                percentage_error = (error / actual_value * 100) if actual_value != 0 else 0
                
                # 검증 정보 업데이트
                cursor.execute('''
                    UPDATE prediction_records 
                    SET actual_value = ?, error = ?, percentage_error = ?, is_validated = TRUE
                    WHERE id = ?
                ''', (actual_value, error, percentage_error, record_id))
                
                conn.commit()
                
                logger.debug(f"Prediction validated: ID={record_id}, Error={error:.2f}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to validate prediction: {e}")
            return False
    
    def batch_validate_predictions(self, actual_metrics: Dict[str, Any]) -> int:
        """배치 예측 검증"""
        try:
            current_time = datetime.now()
            validation_window = timedelta(minutes=10)  # ±10분 윈도우
            
            validated_count = 0
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 검증 가능한 예측들 조회 (타겟 시간이 현재 시간 근처)
                cursor.execute('''
                    SELECT id, predicted_value, target_time 
                    FROM prediction_records 
                    WHERE is_validated = FALSE 
                    AND target_time BETWEEN ? AND ?
                ''', (current_time - validation_window, current_time + validation_window))
                
                predictions = cursor.fetchall()
                
                for pred_id, predicted_value, target_time in predictions:
                    # 실제값 추출 (메트릭 이름에 따라)
                    actual_value = actual_metrics.get('processing_queue_length')
                    
                    if actual_value is not None:
                        if self.validate_prediction(pred_id, actual_value):
                            validated_count += 1
                
                logger.info(f"Batch validated {validated_count} predictions")
                return validated_count
                
        except Exception as e:
            logger.error(f"Failed to batch validate predictions: {e}")
            return 0
    
    def evaluate_model_accuracy(self, model_name: str = "all", 
                               hours: int = 24) -> Optional[AccuracyMetrics]:
        """모델 정확도 평가"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 검증된 예측 데이터 조회
                if model_name == "all":
                    cursor.execute('''
                        SELECT predicted_value, actual_value 
                        FROM prediction_records 
                        WHERE is_validated = TRUE 
                        AND prediction_time >= ?
                    ''', (cutoff_time,))
                else:
                    cursor.execute('''
                        SELECT predicted_value, actual_value 
                        FROM prediction_records 
                        WHERE is_validated = TRUE 
                        AND model_used = ?
                        AND prediction_time >= ?
                    ''', (model_name, cutoff_time))
                
                data = cursor.fetchall()
                
                if len(data) < 5:  # 최소 5개 샘플 필요
                    logger.warning(f"Insufficient validated predictions for accuracy evaluation: {len(data)}")
                    return None
                
                predicted_values = np.array([row[0] for row in data])
                actual_values = np.array([row[1] for row in data])
                
                # 메트릭 계산
                mae = mean_absolute_error(actual_values, predicted_values)
                mse = mean_squared_error(actual_values, predicted_values)
                rmse = np.sqrt(mse)
                
                # MAPE 계산 (0으로 나누기 방지)
                mask = actual_values != 0
                if np.any(mask):
                    mape = np.mean(np.abs((actual_values[mask] - predicted_values[mask]) / actual_values[mask])) * 100
                else:
                    mape = 0.0
                
                # R² 계산
                r2 = r2_score(actual_values, predicted_values)
                
                # 정확도 백분율 (100% - MAPE)
                accuracy_percentage = max(0, 100 - mape)
                
                # 결과 생성
                metrics = AccuracyMetrics(
                    mae=mae,
                    mse=mse,
                    rmse=rmse,
                    mape=mape,
                    r2=r2,
                    accuracy_percentage=accuracy_percentage,
                    samples_count=len(data),
                    evaluation_period=f"{hours}h",
                    timestamp=datetime.now()
                )
                
                # 평가 결과 저장
                self._save_evaluation_result(model_name, metrics)
                
                logger.info(f"Model accuracy evaluated: {accuracy_percentage:.2f}% ({len(data)} samples)")
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to evaluate model accuracy: {e}")
            return None
    
    def _save_evaluation_result(self, model_name: str, metrics: AccuracyMetrics):
        """평가 결과 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                meets_threshold = metrics.accuracy_percentage >= self.accuracy_threshold
                
                cursor.execute('''
                    INSERT INTO accuracy_evaluations (
                        evaluation_time, evaluation_period, model_name, mae, mse, rmse,
                        mape, r2, accuracy_percentage, samples_count, meets_threshold
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.timestamp, metrics.evaluation_period, model_name,
                    metrics.mae, metrics.mse, metrics.rmse, metrics.mape, metrics.r2,
                    metrics.accuracy_percentage, metrics.samples_count, meets_threshold
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save evaluation result: {e}")
    
    def get_accuracy_trend(self, model_name: str = "all", days: int = 7) -> Dict[str, Any]:
        """정확도 추세 분석"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if model_name == "all":
                    cursor.execute('''
                        SELECT evaluation_time, accuracy_percentage, samples_count
                        FROM accuracy_evaluations 
                        WHERE evaluation_time >= ?
                        ORDER BY evaluation_time ASC
                    ''', (cutoff_time,))
                else:
                    cursor.execute('''
                        SELECT evaluation_time, accuracy_percentage, samples_count
                        FROM accuracy_evaluations 
                        WHERE evaluation_time >= ? AND model_name = ?
                        ORDER BY evaluation_time ASC
                    ''', (cutoff_time, model_name))
                
                data = cursor.fetchall()
                
                if not data:
                    return {}
                
                timestamps = [row[0] for row in data]
                accuracies = [row[1] for row in data]
                sample_counts = [row[2] for row in data]
                
                # 추세 분석
                if len(accuracies) >= 2:
                    trend_slope = np.polyfit(range(len(accuracies)), accuracies, 1)[0]
                    if trend_slope > 0.5:
                        trend = "improving"
                    elif trend_slope < -0.5:
                        trend = "degrading"
                    else:
                        trend = "stable"
                else:
                    trend = "insufficient_data"
                
                return {
                    'trend': trend,
                    'current_accuracy': accuracies[-1] if accuracies else 0,
                    'avg_accuracy': np.mean(accuracies),
                    'min_accuracy': np.min(accuracies),
                    'max_accuracy': np.max(accuracies),
                    'total_samples': sum(sample_counts),
                    'evaluation_count': len(data),
                    'timestamps': timestamps,
                    'accuracy_values': accuracies,
                    'meets_threshold': accuracies[-1] >= self.accuracy_threshold if accuracies else False
                }
                
        except Exception as e:
            logger.error(f"Failed to get accuracy trend: {e}")
            return {}
    
    def check_model_health(self, model_name: str = "all") -> Dict[str, Any]:
        """모델 건강성 체크"""
        try:
            # 최근 24시간 정확도
            recent_metrics = self.evaluate_model_accuracy(model_name, hours=24)
            
            # 7일 추세
            trend_data = self.get_accuracy_trend(model_name, days=7)
            
            # 건강성 점수 계산
            health_score = 0
            health_issues = []
            recommendations = []
            
            if recent_metrics:
                # 정확도 점수 (40%)
                accuracy_score = min(recent_metrics.accuracy_percentage / 100, 1.0) * 40
                health_score += accuracy_score
                
                if recent_metrics.accuracy_percentage < self.accuracy_threshold:
                    health_issues.append(f"Accuracy below threshold: {recent_metrics.accuracy_percentage:.1f}%")
                    recommendations.append("Consider model retraining with recent data")
                
                # 샘플 수 점수 (20%)
                if recent_metrics.samples_count >= 50:
                    health_score += 20
                elif recent_metrics.samples_count >= 20:
                    health_score += 15
                elif recent_metrics.samples_count >= 10:
                    health_score += 10
                else:
                    health_issues.append("Insufficient validation samples")
                    recommendations.append("Increase prediction frequency for better validation")
                
                # R² 점수 (20%)
                r2_score_normalized = max(0, min(recent_metrics.r2, 1.0)) * 20
                health_score += r2_score_normalized
                
                if recent_metrics.r2 < 0.7:
                    health_issues.append(f"Low R² score: {recent_metrics.r2:.3f}")
                    recommendations.append("Review feature engineering and model complexity")
            
            if trend_data:
                # 추세 점수 (20%)
                if trend_data['trend'] == 'improving':
                    health_score += 20
                elif trend_data['trend'] == 'stable':
                    health_score += 15
                elif trend_data['trend'] == 'degrading':
                    health_score += 5
                    health_issues.append("Accuracy trend is degrading")
                    recommendations.append("Immediate model retraining recommended")
            
            # 건강성 등급
            if health_score >= 80:
                health_grade = "Excellent"
            elif health_score >= 60:
                health_grade = "Good"
            elif health_score >= 40:
                health_grade = "Fair"
            else:
                health_grade = "Poor"
            
            requires_retraining = health_score < 60 or (recent_metrics and recent_metrics.accuracy_percentage < self.accuracy_threshold)
            
            health_report = {
                'health_score': health_score,
                'health_grade': health_grade,
                'requires_retraining': requires_retraining,
                'health_issues': health_issues,
                'recommendations': recommendations,
                'recent_metrics': asdict(recent_metrics) if recent_metrics else None,
                'trend_data': trend_data,
                'evaluation_time': datetime.now().isoformat()
            }
            
            # 성능 추적 기록 저장
            self._save_performance_tracking(model_name, health_report)
            
            return health_report
            
        except Exception as e:
            logger.error(f"Failed to check model health: {e}")
            return {}
    
    def _save_performance_tracking(self, model_name: str, health_report: Dict[str, Any]):
        """성능 추적 기록 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO model_performance_tracking (
                        tracking_time, model_name, accuracy_trend, performance_score,
                        recommendations, requires_retraining
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(),
                    model_name,
                    health_report.get('trend_data', {}).get('trend', 'unknown'),
                    health_report.get('health_score', 0),
                    json.dumps(health_report.get('recommendations', [])),
                    health_report.get('requires_retraining', False)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save performance tracking: {e}")
    
    def generate_accuracy_report(self, output_path: str = "accuracy_report.json") -> bool:
        """정확도 보고서 생성"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'accuracy_threshold': self.accuracy_threshold,
                'evaluation_window_hours': self.evaluation_window
            }
            
            # 전체 모델 건강성
            overall_health = self.check_model_health("all")
            report['overall_health'] = overall_health
            
            # 모델별 정확도
            models = ["random_forest", "arima", "ensemble"]
            model_reports = {}
            
            for model in models:
                try:
                    model_health = self.check_model_health(model)
                    if model_health:
                        model_reports[model] = model_health
                except:
                    continue
            
            report['model_reports'] = model_reports
            
            # 최근 예측 통계
            recent_stats = self._get_recent_prediction_stats()
            report['recent_statistics'] = recent_stats
            
            # 보고서 저장
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Accuracy report generated: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate accuracy report: {e}")
            return False
    
    def _get_recent_prediction_stats(self, hours: int = 24) -> Dict[str, Any]:
        """최근 예측 통계"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 예측 수
                cursor.execute('''
                    SELECT COUNT(*) FROM prediction_records 
                    WHERE prediction_time >= ?
                ''', (cutoff_time,))
                total_predictions = cursor.fetchone()[0]
                
                # 검증된 예측 수
                cursor.execute('''
                    SELECT COUNT(*) FROM prediction_records 
                    WHERE prediction_time >= ? AND is_validated = TRUE
                ''', (cutoff_time,))
                validated_predictions = cursor.fetchone()[0]
                
                # 평균 신뢰도
                cursor.execute('''
                    SELECT AVG(confidence) FROM prediction_records 
                    WHERE prediction_time >= ?
                ''', (cutoff_time,))
                avg_confidence = cursor.fetchone()[0] or 0
                
                # 평균 오차
                cursor.execute('''
                    SELECT AVG(error) FROM prediction_records 
                    WHERE prediction_time >= ? AND is_validated = TRUE
                ''', (cutoff_time,))
                avg_error = cursor.fetchone()[0] or 0
                
                validation_rate = (validated_predictions / total_predictions * 100) if total_predictions > 0 else 0
                
                return {
                    'total_predictions': total_predictions,
                    'validated_predictions': validated_predictions,
                    'validation_rate_percent': validation_rate,
                    'average_confidence': avg_confidence,
                    'average_error': avg_error,
                    'period_hours': hours
                }
                
        except Exception as e:
            logger.error(f"Failed to get recent prediction stats: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 30):
        """오래된 기록 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 오래된 예측 기록 삭제
                cursor.execute('DELETE FROM prediction_records WHERE prediction_time < ?', (cutoff_time,))
                deleted_predictions = cursor.rowcount
                
                # 오래된 평가 결과 삭제 (최근 평가 결과는 유지)
                cursor.execute('DELETE FROM accuracy_evaluations WHERE evaluation_time < ?', (cutoff_time,))
                deleted_evaluations = cursor.rowcount
                
                # 오래된 성능 추적 기록 삭제
                cursor.execute('DELETE FROM model_performance_tracking WHERE tracking_time < ?', (cutoff_time,))
                deleted_tracking = cursor.rowcount
                
                conn.commit()
                cursor.execute('VACUUM')
                
                logger.info(f"Cleaned up old records: {deleted_predictions} predictions, {deleted_evaluations} evaluations, {deleted_tracking} tracking records")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")


# 전역 모델 정확도 평가기 인스턴스
_model_accuracy_evaluator = None


def get_model_accuracy_evaluator(db_path: str = "model_accuracy.db") -> ModelAccuracyEvaluator:
    """싱글톤 모델 정확도 평가기 반환"""
    global _model_accuracy_evaluator
    if _model_accuracy_evaluator is None:
        _model_accuracy_evaluator = ModelAccuracyEvaluator(db_path)
    return _model_accuracy_evaluator