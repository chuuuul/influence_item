"""
T03B_S03_M03: 클라우드 인스턴스 자동 스케일링 실행 시스템
T03A에서 제공하는 메트릭과 예측 정보를 기반으로 실제 클라우드 인스턴스의 생성, 삭제, 로드 밸런서 설정을 자동으로 수행
"""

import asyncio
import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
from botocore.exceptions import ClientError
import time

from .scaling_decision_engine import ScalingDecisionEngine, ScalingDecision, ScalingAction

logger = logging.getLogger(__name__)


class InstanceType(Enum):
    """인스턴스 타입"""
    GPU_SMALL = "g4dn.xlarge"      # GPU 처리용
    GPU_MEDIUM = "g4dn.2xlarge"    # GPU 처리용
    CPU_SMALL = "t3.medium"        # CPU 처리용
    CPU_MEDIUM = "t3.large"        # CPU 처리용
    CPU_LARGE = "t3.xlarge"        # CPU 처리용


class ScalingExecutionStatus(Enum):
    """스케일링 실행 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class InstanceConfig:
    """인스턴스 설정"""
    instance_type: InstanceType
    ami_id: str
    key_name: str
    security_group_ids: List[str]
    subnet_ids: List[str]
    user_data: str = ""
    tags: Optional[Dict[str, str]] = None


@dataclass
class LoadBalancerConfig:
    """로드 밸런서 설정"""
    name: str
    vpc_id: str
    subnet_ids: List[str]
    security_group_ids: List[str]
    target_group_name: str
    health_check_path: str = "/health"
    health_check_port: int = 80


@dataclass
class ScalingExecution:
    """스케일링 실행 기록"""
    execution_id: str
    decision_id: int
    status: ScalingExecutionStatus
    action: ScalingAction
    target_instances: int
    created_instances: List[str]
    terminated_instances: List[str]
    load_balancer_updated: bool
    execution_time: datetime
    completion_time: Optional[datetime]
    error_message: Optional[str]
    rollback_performed: bool
    cost_estimate: float


class CloudScalingExecutor:
    """클라우드 스케일링 실행기"""
    
    def __init__(self, region: str = 'us-west-2', 
                 instance_config: Optional[InstanceConfig] = None,
                 load_balancer_config: Optional[LoadBalancerConfig] = None,
                 db_path: str = "cloud_scaling.db"):
        """
        Args:
            region: AWS 리전
            instance_config: 인스턴스 설정
            load_balancer_config: 로드 밸런서 설정
            db_path: 실행 이력 저장 데이터베이스 경로
        """
        self.region = region
        self.db_path = db_path
        
        # AWS 클라이언트 초기화
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.ec2_resource = boto3.resource('ec2', region_name=region)
        self.elb_client = boto3.client('elbv2', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        
        # 설정
        self.instance_config = instance_config or self._get_default_instance_config()
        self.load_balancer_config = load_balancer_config or self._get_default_load_balancer_config()
        
        # 스케일링 결정 엔진 연동
        self.decision_engine = ScalingDecisionEngine()
        
        # 비용 추적
        self.cost_tracker = {}
        
        # 쿨다운 관리
        self.cooldown_periods = {
            ScalingAction.SCALE_UP: 300,      # 5분
            ScalingAction.SCALE_DOWN: 900,    # 15분
            ScalingAction.URGENT_SCALE_UP: 60 # 1분
        }
        
        self._init_database()
        
    def _init_database(self):
        """실행 이력 데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scaling_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT UNIQUE NOT NULL,
                        decision_id INTEGER,
                        status TEXT NOT NULL,
                        action TEXT NOT NULL,
                        target_instances INTEGER NOT NULL,
                        created_instances TEXT,
                        terminated_instances TEXT,
                        load_balancer_updated BOOLEAN DEFAULT FALSE,
                        execution_time DATETIME NOT NULL,
                        completion_time DATETIME,
                        error_message TEXT,
                        rollback_performed BOOLEAN DEFAULT FALSE,
                        cost_estimate REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS instance_inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instance_id TEXT UNIQUE NOT NULL,
                        instance_type TEXT NOT NULL,
                        state TEXT NOT NULL,
                        launch_time DATETIME,
                        termination_time DATETIME,
                        cost_per_hour REAL,
                        tags TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_scaling_executions_time 
                    ON scaling_executions(execution_time)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_instance_inventory_state 
                    ON instance_inventory(state)
                ''')
                
                conn.commit()
                logger.info("Cloud scaling database initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize cloud scaling database: {e}")
            raise
    
    async def execute_scaling_decision(self, decision: ScalingDecision, 
                                     override_cooldown: bool = False) -> ScalingExecution:
        """스케일링 결정 실행"""
        execution_id = f"exec_{int(time.time())}"
        logger.info(f"Starting scaling execution {execution_id} for decision {decision.action.value}")
        
        try:
            # 쿨다운 확인
            if not override_cooldown and await self._is_in_execution_cooldown(decision.action):
                logger.warning(f"Scaling action {decision.action.value} is in cooldown period")
                raise Exception("Action is in cooldown period")
            
            # 실행 기록 생성
            execution = ScalingExecution(
                execution_id=execution_id,
                decision_id=0,  # DB에서 결정 ID 조회 필요
                status=ScalingExecutionStatus.PENDING,
                action=decision.action,
                target_instances=decision.recommended_instances,
                created_instances=[],
                terminated_instances=[],
                load_balancer_updated=False,
                execution_time=datetime.now(),
                completion_time=None,
                error_message=None,
                rollback_performed=False,
                cost_estimate=decision.cost_impact or 0.0
            )
            
            # DB에 실행 기록 저장
            await self._save_execution(execution)
            
            # 실행 시작
            execution.status = ScalingExecutionStatus.IN_PROGRESS
            await self._update_execution(execution)
            
            # 현재 인스턴스 상태 확인
            current_instances = await self._get_current_instances()
            current_count = len([i for i in current_instances if i['State']['Name'] == 'running'])
            
            logger.info(f"Current instances: {current_count}, Target: {decision.recommended_instances}")
            
            # 스케일링 작업 수행
            if decision.action in [ScalingAction.SCALE_UP, ScalingAction.URGENT_SCALE_UP]:
                await self._scale_up(execution, decision.recommended_instances - current_count)
            elif decision.action == ScalingAction.SCALE_DOWN:
                await self._scale_down(execution, current_count - decision.recommended_instances)
            
            # 로드 밸런서 업데이트
            if execution.created_instances or execution.terminated_instances:
                await self._update_load_balancer(execution)
            
            # 실행 완료
            execution.status = ScalingExecutionStatus.COMPLETED
            execution.completion_time = datetime.now()
            await self._update_execution(execution)
            
            logger.info(f"Scaling execution {execution_id} completed successfully")
            return execution
            
        except Exception as e:
            logger.error(f"Scaling execution {execution_id} failed: {e}")
            
            # 실행 실패 처리
            execution.status = ScalingExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completion_time = datetime.now()
            
            # 롤백 시도
            try:
                await self._rollback_execution(execution)
            except Exception as rollback_error:
                logger.error(f"Rollback failed for execution {execution_id}: {rollback_error}")
            
            await self._update_execution(execution)
            raise
    
    async def _scale_up(self, execution: ScalingExecution, instances_to_add: int):
        """스케일 업 실행"""
        if instances_to_add <= 0:
            return
        
        logger.info(f"Scaling up by {instances_to_add} instances")
        
        try:
            # 인스턴스 생성
            created_instances = await self._create_instances(instances_to_add)
            execution.created_instances.extend(created_instances)
            
            # 인스턴스가 running 상태가 될 때까지 대기
            await self._wait_for_instances_running(created_instances)
            
            # 인벤토리 업데이트
            await self._update_instance_inventory(created_instances, 'running')
            
            logger.info(f"Successfully created {len(created_instances)} instances")
            
        except Exception as e:
            logger.error(f"Failed to scale up: {e}")
            raise
    
    async def _scale_down(self, execution: ScalingExecution, instances_to_remove: int):
        """스케일 다운 실행"""
        if instances_to_remove <= 0:
            return
        
        logger.info(f"Scaling down by {instances_to_remove} instances")
        
        try:
            # 제거할 인스턴스 선택 (가장 오래된 인스턴스 우선)
            current_instances = await self._get_current_instances()
            running_instances = [i for i in current_instances if i['State']['Name'] == 'running']
            
            # 안전 확인: 최소 1개 인스턴스는 유지
            if len(running_instances) - instances_to_remove < 1:
                instances_to_remove = max(len(running_instances) - 1, 0)
                logger.warning(f"Adjusted removal count to maintain minimum instances: {instances_to_remove}")
            
            if instances_to_remove <= 0:
                return
            
            # 가장 오래된 인스턴스들 선택
            instances_to_terminate = sorted(running_instances, 
                                          key=lambda x: x.get('LaunchTime', datetime.now()))[:instances_to_remove]
            
            terminated_ids = []
            for instance in instances_to_terminate:
                instance_id = instance['InstanceId']
                
                # 로드 밸런서에서 제거
                await self._remove_from_load_balancer(instance_id)
                
                # 안전한 종료를 위한 대기
                await asyncio.sleep(30)
                
                # 인스턴스 종료
                await self._terminate_instance(instance_id)
                terminated_ids.append(instance_id)
            
            execution.terminated_instances.extend(terminated_ids)
            
            # 인벤토리 업데이트
            await self._update_instance_inventory(terminated_ids, 'terminated')
            
            logger.info(f"Successfully terminated {len(terminated_ids)} instances")
            
        except Exception as e:
            logger.error(f"Failed to scale down: {e}")
            raise
    
    async def _create_instances(self, count: int) -> List[str]:
        """인스턴스 생성"""
        try:
            user_data_script = f"""#!/bin/bash
# AI Pipeline Instance Setup
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

# Pull and run the application
docker pull {self.instance_config.ami_id}
docker run -d --name ai-pipeline -p 80:8000 {self.instance_config.ami_id}

# Health check endpoint
echo "Health check ready" > /tmp/health_check_ready
"""
            
            response = self.ec2_client.run_instances(
                ImageId=self.instance_config.ami_id,
                MinCount=count,
                MaxCount=count,
                InstanceType=self.instance_config.instance_type.value,
                KeyName=self.instance_config.key_name,
                SecurityGroupIds=self.instance_config.security_group_ids,
                SubnetId=self.instance_config.subnet_ids[0],  # 첫 번째 서브넷 사용
                UserData=user_data_script,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'AI-Pipeline-Auto-{int(time.time())}'},
                            {'Key': 'Purpose', 'Value': 'AutoScaling'},
                            {'Key': 'Environment', 'Value': 'Production'},
                            {'Key': 'ManagedBy', 'Value': 'AutoScalingSystem'}
                        ] + ([{'Key': k, 'Value': v} for k, v in self.instance_config.tags.items()] 
                             if self.instance_config.tags else [])
                    }
                ]
            )
            
            instance_ids = [instance['InstanceId'] for instance in response['Instances']]
            logger.info(f"Created instances: {instance_ids}")
            
            return instance_ids
            
        except ClientError as e:
            logger.error(f"Failed to create instances: {e}")
            raise
    
    async def _terminate_instance(self, instance_id: str):
        """인스턴스 종료"""
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated instance: {instance_id}")
            
        except ClientError as e:
            logger.error(f"Failed to terminate instance {instance_id}: {e}")
            raise
    
    async def _wait_for_instances_running(self, instance_ids: List[str], timeout: int = 300):
        """인스턴스가 running 상태가 될 때까지 대기"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
                
                all_running = True
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] != 'running':
                            all_running = False
                            break
                    if not all_running:
                        break
                
                if all_running:
                    logger.info(f"All instances are running: {instance_ids}")
                    return
                
                await asyncio.sleep(10)
                
            except ClientError as e:
                logger.error(f"Error checking instance status: {e}")
                await asyncio.sleep(10)
        
        raise Exception(f"Timeout waiting for instances to be running: {instance_ids}")
    
    async def _get_current_instances(self) -> List[Dict[str, Any]]:
        """현재 인스턴스 목록 조회"""
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:ManagedBy', 'Values': ['AutoScalingSystem']},
                    {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopping', 'stopped']}
                ]
            )
            
            instances = []
            for reservation in response['Reservations']:
                instances.extend(reservation['Instances'])
            
            return instances
            
        except ClientError as e:
            logger.error(f"Failed to get current instances: {e}")
            return []
    
    async def _update_load_balancer(self, execution: ScalingExecution):
        """로드 밸런서 업데이트"""
        try:
            # 타겟 그룹 조회
            target_groups = self.elb_client.describe_target_groups(
                Names=[self.load_balancer_config.target_group_name]
            )
            
            if not target_groups['TargetGroups']:
                logger.warning(f"Target group not found: {self.load_balancer_config.target_group_name}")
                return
            
            target_group_arn = target_groups['TargetGroups'][0]['TargetGroupArn']
            
            # 새로운 인스턴스를 타겟 그룹에 추가
            if execution.created_instances:
                targets = [{'Id': instance_id, 'Port': 80} for instance_id in execution.created_instances]
                
                self.elb_client.register_targets(
                    TargetGroupArn=target_group_arn,
                    Targets=targets
                )
                
                logger.info(f"Registered {len(targets)} targets to load balancer")
            
            # 종료된 인스턴스를 타겟 그룹에서 제거
            if execution.terminated_instances:
                targets = [{'Id': instance_id, 'Port': 80} for instance_id in execution.terminated_instances]
                
                self.elb_client.deregister_targets(
                    TargetGroupArn=target_group_arn,
                    Targets=targets
                )
                
                logger.info(f"Deregistered {len(targets)} targets from load balancer")
            
            execution.load_balancer_updated = True
            
        except ClientError as e:
            logger.error(f"Failed to update load balancer: {e}")
            raise
    
    async def _remove_from_load_balancer(self, instance_id: str):
        """로드 밸런서에서 인스턴스 제거"""
        try:
            target_groups = self.elb_client.describe_target_groups(
                Names=[self.load_balancer_config.target_group_name]
            )
            
            if target_groups['TargetGroups']:
                target_group_arn = target_groups['TargetGroups'][0]['TargetGroupArn']
                
                self.elb_client.deregister_targets(
                    TargetGroupArn=target_group_arn,
                    Targets=[{'Id': instance_id, 'Port': 80}]
                )
                
                logger.info(f"Removed instance {instance_id} from load balancer")
                
        except ClientError as e:
            logger.error(f"Failed to remove instance {instance_id} from load balancer: {e}")
    
    async def _rollback_execution(self, execution: ScalingExecution):
        """실행 롤백"""
        logger.info(f"Starting rollback for execution {execution.execution_id}")
        
        try:
            # 생성된 인스턴스 종료
            if execution.created_instances:
                for instance_id in execution.created_instances:
                    try:
                        await self._terminate_instance(instance_id)
                    except Exception as e:
                        logger.error(f"Failed to terminate instance {instance_id} during rollback: {e}")
            
            # 종료된 인스턴스는 롤백 불가 (로그만 남김)
            if execution.terminated_instances:
                logger.warning(f"Cannot rollback terminated instances: {execution.terminated_instances}")
            
            execution.rollback_performed = True
            logger.info(f"Rollback completed for execution {execution.execution_id}")
            
        except Exception as e:
            logger.error(f"Rollback failed for execution {execution.execution_id}: {e}")
            raise
    
    async def _is_in_execution_cooldown(self, action: ScalingAction) -> bool:
        """실행 쿨다운 확인"""
        try:
            cooldown_seconds = self.cooldown_periods.get(action, 300)
            cutoff_time = datetime.now() - timedelta(seconds=cooldown_seconds)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) FROM scaling_executions 
                    WHERE action = ? AND execution_time > ? AND status = ?
                ''', (action.value, cutoff_time, ScalingExecutionStatus.COMPLETED.value))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Failed to check execution cooldown: {e}")
            return False
    
    async def _save_execution(self, execution: ScalingExecution):
        """실행 기록 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO scaling_executions (
                        execution_id, decision_id, status, action, target_instances,
                        created_instances, terminated_instances, load_balancer_updated,
                        execution_time, completion_time, error_message, rollback_performed,
                        cost_estimate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    execution.execution_id,
                    execution.decision_id,
                    execution.status.value,
                    execution.action.value,
                    execution.target_instances,
                    json.dumps(execution.created_instances),
                    json.dumps(execution.terminated_instances),
                    execution.load_balancer_updated,
                    execution.execution_time,
                    execution.completion_time,
                    execution.error_message,
                    execution.rollback_performed,
                    execution.cost_estimate
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save execution: {e}")
    
    async def _update_execution(self, execution: ScalingExecution):
        """실행 기록 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE scaling_executions SET
                        status = ?, created_instances = ?, terminated_instances = ?,
                        load_balancer_updated = ?, completion_time = ?, error_message = ?,
                        rollback_performed = ?
                    WHERE execution_id = ?
                ''', (
                    execution.status.value,
                    json.dumps(execution.created_instances),
                    json.dumps(execution.terminated_instances),
                    execution.load_balancer_updated,
                    execution.completion_time,
                    execution.error_message,
                    execution.rollback_performed,
                    execution.execution_id
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update execution: {e}")
    
    async def _update_instance_inventory(self, instance_ids: List[str], state: str):
        """인스턴스 인벤토리 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for instance_id in instance_ids:
                    if state == 'running':
                        cursor.execute('''
                            INSERT OR REPLACE INTO instance_inventory (
                                instance_id, instance_type, state, launch_time, cost_per_hour
                            ) VALUES (?, ?, ?, ?, ?)
                        ''', (
                            instance_id,
                            self.instance_config.instance_type.value,
                            state,
                            datetime.now(),
                            self._get_instance_cost_per_hour()
                        ))
                    elif state == 'terminated':
                        cursor.execute('''
                            UPDATE instance_inventory SET 
                                state = ?, termination_time = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE instance_id = ?
                        ''', (state, datetime.now(), instance_id))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update instance inventory: {e}")
    
    def _get_instance_cost_per_hour(self) -> float:
        """인스턴스 시간당 비용 조회"""
        cost_map = {
            InstanceType.GPU_SMALL: 0.526,    # g4dn.xlarge
            InstanceType.GPU_MEDIUM: 1.052,   # g4dn.2xlarge
            InstanceType.CPU_SMALL: 0.0464,   # t3.medium
            InstanceType.CPU_MEDIUM: 0.0928,  # t3.large
            InstanceType.CPU_LARGE: 0.1856    # t3.xlarge
        }
        return cost_map.get(self.instance_config.instance_type, 0.05)
    
    def _get_default_instance_config(self) -> InstanceConfig:
        """기본 인스턴스 설정"""
        return InstanceConfig(
            instance_type=InstanceType.CPU_MEDIUM,
            ami_id="ami-0c94855ba95b798c7",  # Amazon Linux 2023
            key_name="ai-pipeline-key",
            security_group_ids=["sg-default"],
            subnet_ids=["subnet-default"],
            user_data="",
            tags={"Project": "AIInfluenceItems", "AutoScaling": "true"}
        )
    
    def _get_default_load_balancer_config(self) -> LoadBalancerConfig:
        """기본 로드 밸런서 설정"""
        return LoadBalancerConfig(
            name="ai-pipeline-alb",
            vpc_id="vpc-default",
            subnet_ids=["subnet-default"],
            security_group_ids=["sg-default"],
            target_group_name="ai-pipeline-targets",
            health_check_path="/health",
            health_check_port=80
        )
    
    async def get_execution_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """실행 이력 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM scaling_executions 
                    WHERE execution_time >= ? 
                    ORDER BY execution_time DESC
                ''', (cutoff_time,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    row_dict = dict(zip(columns, row))
                    # JSON 필드 파싱
                    if row_dict['created_instances']:
                        row_dict['created_instances'] = json.loads(row_dict['created_instances'])
                    if row_dict['terminated_instances']:
                        row_dict['terminated_instances'] = json.loads(row_dict['terminated_instances'])
                    
                    results.append(row_dict)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return []
    
    async def get_current_cost_estimate(self) -> Dict[str, float]:
        """현재 비용 추정"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*), AVG(cost_per_hour) FROM instance_inventory 
                    WHERE state = 'running'
                ''')
                
                result = cursor.fetchone()
                running_count = result[0] or 0
                avg_cost_per_hour = result[1] or 0
                
                # 시간별, 일별, 월별 비용 추정
                hourly_cost = running_count * avg_cost_per_hour
                daily_cost = hourly_cost * 24
                monthly_cost = daily_cost * 30
                
                return {
                    'running_instances': running_count,
                    'cost_per_hour': hourly_cost,
                    'cost_per_day': daily_cost,
                    'cost_per_month': monthly_cost,
                    'currency': 'USD'
                }
                
        except Exception as e:
            logger.error(f"Failed to get cost estimate: {e}")
            return {}
    
    async def manual_override_scaling(self, target_instances: int, reason: str = "Manual Override") -> ScalingExecution:
        """수동 스케일링 오버라이드"""
        logger.info(f"Manual scaling override to {target_instances} instances: {reason}")
        
        try:
            # 현재 인스턴스 수 확인
            current_instances = await self._get_current_instances()
            current_count = len([i for i in current_instances if i['State']['Name'] == 'running'])
            
            # 가상의 스케일링 결정 생성
            if target_instances > current_count:
                action = ScalingAction.SCALE_UP
            elif target_instances < current_count:
                action = ScalingAction.SCALE_DOWN
            else:
                action = ScalingAction.MAINTAIN
            
            # 가상 결정으로 실행
            mock_decision = ScalingDecision(
                action=action,
                reasons=[],
                confidence=1.0,
                urgency=5,
                recommended_instances=target_instances,
                current_metrics={},
                predicted_metrics=None,
                cost_impact=0.0,
                decision_time=datetime.now(),
                cooldown_until=None
            )
            
            return await self.execute_scaling_decision(mock_decision, override_cooldown=True)
            
        except Exception as e:
            logger.error(f"Manual scaling override failed: {e}")
            raise


# 유틸리티 함수들
async def create_auto_scaling_system(region: str = 'us-west-2') -> CloudScalingExecutor:
    """자동 스케일링 시스템 생성"""
    try:
        # 기본 설정으로 시스템 생성
        executor = CloudScalingExecutor(region=region)
        
        logger.info(f"Auto scaling system created for region {region}")
        return executor
        
    except Exception as e:
        logger.error(f"Failed to create auto scaling system: {e}")
        raise


async def test_scaling_system():
    """스케일링 시스템 테스트"""
    try:
        executor = await create_auto_scaling_system()
        
        # 현재 상태 확인
        instances = await executor._get_current_instances()
        cost_estimate = await executor.get_current_cost_estimate()
        
        print(f"Current instances: {len(instances)}")
        print(f"Cost estimate: ${cost_estimate.get('cost_per_hour', 0):.4f}/hour")
        
        # 실행 이력 확인
        history = await executor.get_execution_history(hours=24)
        print(f"Recent executions: {len(history)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Scaling system test failed: {e}")
        return False


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(test_scaling_system())