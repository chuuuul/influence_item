"""
T03A_S03_M03: 시계열 데이터 관리자
스케일링 예측을 위한 시계열 데이터 처리 및 특성 엔지니어링
"""

import sqlite3
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class TimeSeriesDataManager:
    """시계열 데이터 관리자"""
    
    def __init__(self, db_path: str = "scaling_metrics.db"):
        """
        Args:
            db_path: 메트릭 데이터베이스 경로
        """
        self.db_path = db_path
    
    def get_time_series_data(self, hours: int = 168, resample_freq: str = '5T') -> Optional[pd.DataFrame]:
        """
        시계열 데이터 조회 및 전처리
        
        Args:
            hours: 조회할 시간 범위 (시간)
            resample_freq: 리샘플링 주기 ('5T' = 5분, '1H' = 1시간)
        
        Returns:
            전처리된 시계열 데이터프레임
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT 
                        timestamp,
                        processing_queue_length,
                        pending_requests,
                        active_analyses,
                        cpu_percent,
                        memory_percent,
                        memory_available_gb,
                        gpu_utilization,
                        gpu_memory_percent,
                        avg_response_time,
                        p95_response_time,
                        completed_requests_last_hour,
                        failed_requests_last_hour,
                        success_rate,
                        network_io_mbps,
                        active_connections
                    FROM scaling_metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp ASC
                '''
                
                df = pd.read_sql_query(query, conn, params=(cutoff_time,))
            
            if df.empty:
                logger.warning("No time series data available")
                return None
            
            # 타임스탬프를 인덱스로 설정
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 결측값 처리
            df = self._handle_missing_values(df)
            
            # 리샘플링 (시간 간격 정규화)
            df_resampled = self._resample_data(df, resample_freq)
            
            # 특성 엔지니어링
            df_engineered = self._engineer_features(df_resampled)
            
            return df_engineered
            
        except Exception as e:
            logger.error(f"Failed to get time series data: {e}")
            return None
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """결측값 처리"""
        try:
            # GPU 메트릭이 없는 경우 0으로 채움
            gpu_columns = ['gpu_utilization', 'gpu_memory_percent']
            for col in gpu_columns:
                if col in df.columns:
                    df[col] = df[col].fillna(0)
            
            # 숫자형 컬럼들의 결측값을 forward fill 후 backward fill
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df[numeric_columns].fillna(method='ffill').fillna(method='bfill')
            
            # 여전히 결측값이 있으면 0으로 채움
            df = df.fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to handle missing values: {e}")
            return df
    
    def _resample_data(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """데이터 리샘플링"""
        try:
            # 숫자형 컬럼들을 평균으로 리샘플링
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            # 각 컬럼별로 적절한 집계 방법 적용
            agg_methods = {}
            for col in numeric_columns:
                if 'queue_length' in col or 'requests' in col or 'analyses' in col:
                    agg_methods[col] = 'mean'  # 카운트 계열은 평균
                elif 'percent' in col or 'rate' in col:
                    agg_methods[col] = 'mean'  # 비율/퍼센트는 평균
                elif 'response_time' in col:
                    agg_methods[col] = 'mean'  # 응답시간은 평균
                elif 'connections' in col:
                    agg_methods[col] = 'mean'  # 연결수는 평균
                else:
                    agg_methods[col] = 'mean'  # 기본값은 평균
            
            df_resampled = df.resample(freq).agg(agg_methods)
            
            # 리샘플링으로 인한 결측값 제거
            df_resampled = df_resampled.dropna()
            
            return df_resampled
            
        except Exception as e:
            logger.error(f"Failed to resample data: {e}")
            return df
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """특성 엔지니어링"""
        try:
            # 이동 평균 계산 (5개 구간)
            window = 5
            for col in ['processing_queue_length', 'cpu_percent', 'memory_percent', 'avg_response_time']:
                if col in df.columns:
                    df[f'{col}_ma_{window}'] = df[col].rolling(window=window, min_periods=1).mean()
            
            # 변화율 계산
            for col in ['processing_queue_length', 'active_analyses', 'cpu_percent', 'memory_percent']:
                if col in df.columns:
                    df[f'{col}_pct_change'] = df[col].pct_change().fillna(0)
            
            # 시간대별 특성
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)
            
            # 업무시간 여부 (월-금 9-18시)
            df['is_business_hours'] = (
                (df.index.dayofweek < 5) & 
                (df.index.hour >= 9) & 
                (df.index.hour < 18)
            ).astype(int)
            
            # 시스템 부하 종합 지표
            if all(col in df.columns for col in ['cpu_percent', 'memory_percent', 'processing_queue_length']):
                df['system_load_composite'] = (
                    df['cpu_percent'] * 0.3 + 
                    df['memory_percent'] * 0.3 + 
                    df['processing_queue_length'] * 0.4
                )
            
            # GPU 부하 지표 (GPU가 있는 경우)
            if 'gpu_utilization' in df.columns and df['gpu_utilization'].sum() > 0:
                df['gpu_load_composite'] = (
                    df['gpu_utilization'] * 0.6 + 
                    df['gpu_memory_percent'] * 0.4
                )
            else:
                df['gpu_load_composite'] = 0
            
            # 처리 효율성 지표
            if all(col in df.columns for col in ['completed_requests_last_hour', 'avg_response_time']):
                # 시간당 처리량 / 평균 응답시간으로 효율성 계산
                df['processing_efficiency'] = np.where(
                    df['avg_response_time'] > 0,
                    df['completed_requests_last_hour'] / (df['avg_response_time'] / 1000),  # ms를 초로 변환
                    0
                )
            
            # 이상치 탐지를 위한 Z-score
            for col in ['processing_queue_length', 'cpu_percent', 'memory_percent']:
                if col in df.columns:
                    mean = df[col].mean()
                    std = df[col].std()
                    if std > 0:
                        df[f'{col}_zscore'] = (df[col] - mean) / std
                    else:
                        df[f'{col}_zscore'] = 0
            
            # 추세 방향 (증가/감소/유지)
            for col in ['processing_queue_length', 'cpu_percent', 'memory_percent']:
                if col in df.columns:
                    trend = df[col].diff().fillna(0)
                    df[f'{col}_trend'] = np.where(trend > 0, 1, np.where(trend < 0, -1, 0))
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to engineer features: {e}")
            return df
    
    def get_training_data(self, hours: int = 168, target_column: str = 'processing_queue_length') -> Optional[Tuple[pd.DataFrame, pd.Series]]:
        """
        모델 훈련용 데이터 준비
        
        Args:
            hours: 조회할 시간 범위
            target_column: 예측 대상 컬럼
        
        Returns:
            (features, target) 튜플
        """
        try:
            df = self.get_time_series_data(hours=hours)
            if df is None or df.empty:
                return None
            
            # 예측 대상 생성 (1시간 후 값)
            if target_column not in df.columns:
                logger.error(f"Target column '{target_column}' not found in data")
                return None
            
            # 1시간 후 값을 target으로 설정 (12개 구간 후, 5분 간격이므로)
            periods_ahead = 12
            target = df[target_column].shift(-periods_ahead).dropna()
            
            # 특성 선택
            feature_columns = [
                'processing_queue_length', 'pending_requests', 'active_analyses',
                'cpu_percent', 'memory_percent', 'memory_available_gb',
                'avg_response_time', 'p95_response_time',
                'completed_requests_last_hour', 'success_rate',
                'network_io_mbps', 'active_connections',
                'hour', 'day_of_week', 'is_weekend', 'is_business_hours',
                'system_load_composite', 'processing_efficiency'
            ]
            
            # GPU 특성 추가 (있는 경우)
            if 'gpu_load_composite' in df.columns:
                feature_columns.append('gpu_load_composite')
            
            # 이동평균 특성 추가
            ma_columns = [col for col in df.columns if '_ma_' in col]
            feature_columns.extend(ma_columns)
            
            # 변화율 특성 추가
            pct_change_columns = [col for col in df.columns if '_pct_change' in col]
            feature_columns.extend(pct_change_columns)
            
            # 실제로 존재하는 컬럼만 필터링
            available_features = [col for col in feature_columns if col in df.columns]
            
            # 특성 데이터프레임 생성 (target과 길이 맞춤)
            features = df[available_features].iloc[:-periods_ahead]
            
            # 길이 검증
            if len(features) != len(target):
                min_length = min(len(features), len(target))
                features = features.iloc[:min_length]
                target = target.iloc[:min_length]
            
            logger.info(f"Training data prepared: {len(features)} samples, {len(available_features)} features")
            return features, target
            
        except Exception as e:
            logger.error(f"Failed to prepare training data: {e}")
            return None
    
    def get_latest_features(self, target_column: str = 'processing_queue_length') -> Optional[pd.DataFrame]:
        """최신 데이터의 특성 벡터 조회 (예측용)"""
        try:
            df = self.get_time_series_data(hours=24)  # 최근 24시간
            if df is None or df.empty:
                return None
            
            # 마지막 데이터포인트의 특성 반환
            latest_features = df.iloc[-1:].copy()
            
            # 특성 선택 (훈련 데이터와 동일)
            feature_columns = [
                'processing_queue_length', 'pending_requests', 'active_analyses',
                'cpu_percent', 'memory_percent', 'memory_available_gb',
                'avg_response_time', 'p95_response_time',
                'completed_requests_last_hour', 'success_rate',
                'network_io_mbps', 'active_connections',
                'hour', 'day_of_week', 'is_weekend', 'is_business_hours',
                'system_load_composite', 'processing_efficiency'
            ]
            
            # GPU 특성 추가 (있는 경우)
            if 'gpu_load_composite' in df.columns:
                feature_columns.append('gpu_load_composite')
            
            # 이동평균 특성 추가
            ma_columns = [col for col in latest_features.columns if '_ma_' in col]
            feature_columns.extend(ma_columns)
            
            # 변화율 특성 추가
            pct_change_columns = [col for col in latest_features.columns if '_pct_change' in col]
            feature_columns.extend(pct_change_columns)
            
            # 실제로 존재하는 컬럼만 필터링
            available_features = [col for col in feature_columns if col in latest_features.columns]
            
            return latest_features[available_features]
            
        except Exception as e:
            logger.error(f"Failed to get latest features: {e}")
            return None
    
    def get_demand_patterns(self, days: int = 30) -> Dict[str, Any]:
        """수요 패턴 분석"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT 
                        datetime(timestamp) as timestamp,
                        processing_queue_length,
                        active_analyses,
                        completed_requests_last_hour
                    FROM scaling_metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp ASC
                '''
                
                df = pd.read_sql_query(query, conn, params=(cutoff_time,))
            
            if df.empty:
                return {}
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            
            # 시간대별 평균 수요
            hourly_pattern = df.groupby('hour')[['processing_queue_length', 'active_analyses']].mean()
            
            # 요일별 평균 수요
            daily_pattern = df.groupby('day_of_week')[['processing_queue_length', 'active_analyses']].mean()
            
            # 피크 시간대 식별
            peak_hours = hourly_pattern['processing_queue_length'].nlargest(3).index.tolist()
            low_hours = hourly_pattern['processing_queue_length'].nsmallest(3).index.tolist()
            
            return {
                'hourly_patterns': {
                    'hours': hourly_pattern.index.tolist(),
                    'queue_length': hourly_pattern['processing_queue_length'].tolist(),
                    'active_analyses': hourly_pattern['active_analyses'].tolist()
                },
                'daily_patterns': {
                    'days': daily_pattern.index.tolist(),
                    'queue_length': daily_pattern['processing_queue_length'].tolist(),
                    'active_analyses': daily_pattern['active_analyses'].tolist()
                },
                'peak_hours': peak_hours,
                'low_hours': low_hours,
                'analysis_period_days': days
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze demand patterns: {e}")
            return {}
    
    def export_training_data(self, filepath: str, hours: int = 168):
        """훈련 데이터를 파일로 내보내기"""
        try:
            training_data = self.get_training_data(hours=hours)
            if training_data is None:
                logger.error("No training data available for export")
                return False
            
            features, target = training_data
            
            # 특성과 타겟을 합쳐서 저장
            export_df = features.copy()
            export_df['target'] = target
            
            if filepath.endswith('.csv'):
                export_df.to_csv(filepath)
            elif filepath.endswith('.json'):
                export_df.to_json(filepath, orient='records', date_format='iso')
            else:
                # 기본적으로 CSV로 저장
                export_df.to_csv(f"{filepath}.csv")
            
            logger.info(f"Training data exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            return False