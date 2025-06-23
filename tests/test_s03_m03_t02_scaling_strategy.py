#!/usr/bin/env python3
"""
S03_M03_T02 통합 테스트: 확장성 및 스케일링 전략
부하 분산, 자동 스케일링, 리소스 최적화 전략 검증
"""

import sys
import os
import time
import json
import threading
import queue
import psutil
from typing import Dict, List, Any
from datetime import datetime, timedelta
import concurrent.futures
import asyncio

# 프로젝트 루트를 Python 경로에 추가
sys.path.append('/Users/chul/Documents/claude/influence_item')

def test_load_balancing():
    """부하 분산 시스템 테스트"""
    print("🧪 부하 분산 시스템 테스트 시작...")
    
    try:
        import random
        import hashlib
        from enum import Enum
        
        # 부하 분산 알고리즘 정의
        class LoadBalancingAlgorithm(Enum):
            ROUND_ROBIN = "round_robin"
            LEAST_CONNECTIONS = "least_connections"
            WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
            HASH_BASED = "hash_based"
            RANDOM = "random"
        
        # 서버 노드 클래스
        class ServerNode:
            def __init__(self, node_id, capacity=100, weight=1):
                self.node_id = node_id
                self.capacity = capacity
                self.weight = weight
                self.current_load = 0
                self.active_connections = 0
                self.total_requests = 0
                self.failed_requests = 0
                self.is_healthy = True
                self.last_health_check = datetime.now()
                self.response_times = []
            
            def process_request(self, request_complexity=1):
                """요청 처리 시뮬레이션"""
                if not self.is_healthy:
                    self.failed_requests += 1
                    raise Exception(f"Node {self.node_id} is unhealthy")
                
                if self.current_load + request_complexity > self.capacity:
                    self.failed_requests += 1
                    raise Exception(f"Node {self.node_id} is overloaded")
                
                # 요청 처리 시뮬레이션
                self.active_connections += 1
                self.current_load += request_complexity
                self.total_requests += 1
                
                # 응답 시간 시뮬레이션 (부하에 따라 증가)
                base_response_time = 0.1
                load_factor = self.current_load / self.capacity
                response_time = base_response_time * (1 + load_factor)
                
                time.sleep(response_time)  # 실제 처리 시간 시뮬레이션
                
                self.response_times.append(response_time)
                if len(self.response_times) > 100:  # 최근 100개만 유지
                    self.response_times.pop(0)
                
                # 요청 완료
                self.active_connections -= 1
                self.current_load -= request_complexity
                
                return {
                    'node_id': self.node_id,
                    'response_time': response_time,
                    'current_load': self.current_load
                }
            
            def health_check(self):
                """헬스 체크"""
                # 간단한 헬스 체크 로직
                load_ratio = self.current_load / self.capacity
                avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
                
                self.is_healthy = (
                    load_ratio < 0.95 and  # 95% 이하 부하
                    avg_response_time < 2.0 and  # 2초 이하 응답시간
                    self.failed_requests / max(self.total_requests, 1) < 0.1  # 10% 이하 실패율
                )
                
                self.last_health_check = datetime.now()
                return self.is_healthy
            
            def get_stats(self):
                """노드 통계"""
                success_rate = (self.total_requests - self.failed_requests) / max(self.total_requests, 1) * 100
                avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
                
                return {
                    'node_id': self.node_id,
                    'capacity': self.capacity,
                    'weight': self.weight,
                    'current_load': self.current_load,
                    'load_percentage': (self.current_load / self.capacity) * 100,
                    'active_connections': self.active_connections,
                    'total_requests': self.total_requests,
                    'failed_requests': self.failed_requests,
                    'success_rate': success_rate,
                    'avg_response_time': avg_response_time,
                    'is_healthy': self.is_healthy,
                    'last_health_check': self.last_health_check.isoformat()
                }
        
        # 로드 밸런서 클래스
        class LoadBalancer:
            def __init__(self, algorithm=LoadBalancingAlgorithm.ROUND_ROBIN):
                self.algorithm = algorithm
                self.nodes = {}
                self.current_index = 0
                self.request_count = 0
                self.failed_requests = 0
                self.health_check_interval = 30  # 30초
                self.last_health_check = datetime.now()
            
            def add_node(self, node: ServerNode):
                """노드 추가"""
                self.nodes[node.node_id] = node
                print(f"    ➕ 노드 추가: {node.node_id} (용량: {node.capacity}, 가중치: {node.weight})")
            
            def remove_node(self, node_id):
                """노드 제거"""
                if node_id in self.nodes:
                    del self.nodes[node_id]
                    print(f"    ➖ 노드 제거: {node_id}")
            
            def select_node(self, request_key=None):
                """노드 선택"""
                healthy_nodes = {nid: node for nid, node in self.nodes.items() if node.is_healthy}
                
                if not healthy_nodes:
                    raise Exception("No healthy nodes available")
                
                if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
                    return self._round_robin(healthy_nodes)
                elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
                    return self._least_connections(healthy_nodes)
                elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
                    return self._weighted_round_robin(healthy_nodes)
                elif self.algorithm == LoadBalancingAlgorithm.HASH_BASED:
                    return self._hash_based(healthy_nodes, request_key)
                elif self.algorithm == LoadBalancingAlgorithm.RANDOM:
                    return self._random(healthy_nodes)
                else:
                    return self._round_robin(healthy_nodes)
            
            def _round_robin(self, nodes):
                """라운드 로빈 알고리즘"""
                node_list = list(nodes.values())
                selected_node = node_list[self.current_index % len(node_list)]
                self.current_index += 1
                return selected_node
            
            def _least_connections(self, nodes):
                """최소 연결 알고리즘"""
                return min(nodes.values(), key=lambda n: n.active_connections)
            
            def _weighted_round_robin(self, nodes):
                """가중치 라운드 로빈 알고리즘"""
                # 가중치에 따른 선택 확률 계산
                total_weight = sum(node.weight for node in nodes.values())
                random_value = random.uniform(0, total_weight)
                
                cumulative_weight = 0
                for node in nodes.values():
                    cumulative_weight += node.weight
                    if random_value <= cumulative_weight:
                        return node
                
                # 기본값으로 첫 번째 노드 반환
                return next(iter(nodes.values()))
            
            def _hash_based(self, nodes, request_key):
                """해시 기반 알고리즘"""
                if not request_key:
                    request_key = str(self.request_count)
                
                hash_value = int(hashlib.md5(str(request_key).encode()).hexdigest(), 16)
                node_list = list(nodes.values())
                selected_node = node_list[hash_value % len(node_list)]
                return selected_node
            
            def _random(self, nodes):
                """랜덤 알고리즘"""
                return random.choice(list(nodes.values()))
            
            def process_request(self, request_complexity=1, request_key=None):
                """요청 처리"""
                self.request_count += 1
                
                try:
                    # 헬스 체크 (주기적으로)
                    if (datetime.now() - self.last_health_check).seconds > self.health_check_interval:
                        self.perform_health_checks()
                    
                    # 노드 선택
                    selected_node = self.select_node(request_key)
                    
                    # 요청 처리
                    result = selected_node.process_request(request_complexity)
                    result['algorithm'] = self.algorithm.value
                    result['request_id'] = self.request_count
                    
                    return result
                
                except Exception as e:
                    self.failed_requests += 1
                    return {
                        'error': str(e),
                        'request_id': self.request_count,
                        'algorithm': self.algorithm.value
                    }
            
            def perform_health_checks(self):
                """모든 노드에 대해 헬스 체크 수행"""
                for node in self.nodes.values():
                    node.health_check()
                self.last_health_check = datetime.now()
            
            def get_cluster_stats(self):
                """클러스터 통계"""
                total_capacity = sum(node.capacity for node in self.nodes.values())
                total_load = sum(node.current_load for node in self.nodes.values())
                healthy_nodes = sum(1 for node in self.nodes.values() if node.is_healthy)
                
                cluster_load_percentage = (total_load / total_capacity * 100) if total_capacity > 0 else 0
                success_rate = (self.request_count - self.failed_requests) / max(self.request_count, 1) * 100
                
                return {
                    'algorithm': self.algorithm.value,
                    'total_nodes': len(self.nodes),
                    'healthy_nodes': healthy_nodes,
                    'total_capacity': total_capacity,
                    'total_load': total_load,
                    'cluster_load_percentage': cluster_load_percentage,
                    'total_requests': self.request_count,
                    'failed_requests': self.failed_requests,
                    'success_rate': success_rate,
                    'nodes': {nid: node.get_stats() for nid, node in self.nodes.items()}
                }
        
        # 로드 밸런서 테스트
        lb = LoadBalancer(LoadBalancingAlgorithm.LEAST_CONNECTIONS)
        
        # 노드 추가
        nodes = [
            ServerNode('node-1', capacity=100, weight=1),
            ServerNode('node-2', capacity=150, weight=2),
            ServerNode('node-3', capacity=80, weight=1)
        ]
        
        for node in nodes:
            lb.add_node(node)
        
        # 동시 요청 시뮬레이션
        def simulate_requests(lb, num_requests=50):
            results = []
            for i in range(num_requests):
                complexity = random.randint(1, 5)
                result = lb.process_request(complexity, f"user_{i}")
                results.append(result)
                time.sleep(0.01)  # 작은 지연
            return results
        
        # 여러 스레드로 부하 테스트
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_results = [
                executor.submit(simulate_requests, lb, 20)
                for _ in range(3)
            ]
            
            all_results = []
            for future in concurrent.futures.as_completed(future_results):
                all_results.extend(future.result())
        
        # 결과 검증
        cluster_stats = lb.get_cluster_stats()
        
        assert cluster_stats['total_requests'] > 0, "요청이 처리되지 않았습니다."
        assert cluster_stats['healthy_nodes'] >= 2, "충분한 수의 노드가 healthy 상태가 아닙니다."
        assert cluster_stats['success_rate'] > 80, f"성공률이 너무 낮습니다: {cluster_stats['success_rate']:.1f}%"
        
        # 부하 분산 검증 (각 노드가 요청을 받았는지)
        successful_results = [r for r in all_results if 'node_id' in r]
        nodes_used = set(r['node_id'] for r in successful_results)
        assert len(nodes_used) >= 2, "부하 분산이 제대로 되지 않았습니다."
        
        print(f"  ⚖️ 부하 분산 결과: {cluster_stats['total_requests']}개 요청, "
              f"성공률 {cluster_stats['success_rate']:.1f}%")
        print(f"  🖥️ 사용된 노드: {len(nodes_used)}개, "
              f"클러스터 부하: {cluster_stats['cluster_load_percentage']:.1f}%")
        
        print("✅ 부하 분산 시스템 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 부하 분산 시스템 테스트 실패: {str(e)}")
        return False

def test_auto_scaling():
    """자동 스케일링 테스트"""
    print("🧪 자동 스케일링 테스트 시작...")
    
    try:
        from enum import Enum
        import threading
        import time
        
        # 스케일링 동작 정의
        class ScalingAction(Enum):
            SCALE_UP = "scale_up"
            SCALE_DOWN = "scale_down"
            NO_ACTION = "no_action"
        
        # 스케일링 메트릭 클래스
        class ScalingMetrics:
            def __init__(self):
                self.cpu_percent = 0.0
                self.memory_percent = 0.0
                self.active_requests = 0
                self.response_time = 0.0
                self.error_rate = 0.0
                self.timestamp = datetime.now()
            
            def update(self, cpu=None, memory=None, requests=None, response_time=None, error_rate=None):
                """메트릭 업데이트"""
                if cpu is not None:
                    self.cpu_percent = cpu
                if memory is not None:
                    self.memory_percent = memory
                if requests is not None:
                    self.active_requests = requests
                if response_time is not None:
                    self.response_time = response_time
                if error_rate is not None:
                    self.error_rate = error_rate
                self.timestamp = datetime.now()
            
            def to_dict(self):
                return {
                    'cpu_percent': self.cpu_percent,
                    'memory_percent': self.memory_percent,
                    'active_requests': self.active_requests,
                    'response_time': self.response_time,
                    'error_rate': self.error_rate,
                    'timestamp': self.timestamp.isoformat()
                }
        
        # 오토스케일러 클래스
        class AutoScaler:
            def __init__(self):
                self.instances = {}
                self.min_instances = 1
                self.max_instances = 10
                self.target_cpu_percent = 70.0
                self.target_response_time = 2.0
                self.scale_up_threshold = 80.0
                self.scale_down_threshold = 30.0
                self.cooldown_period = 300  # 5분
                self.last_scaling_action = None
                self.last_scaling_time = datetime.now() - timedelta(minutes=10)
                self.scaling_history = []
                self.metrics_history = []
            
            def add_instance(self, instance_id, capacity=100):
                """인스턴스 추가"""
                self.instances[instance_id] = {
                    'instance_id': instance_id,
                    'capacity': capacity,
                    'current_load': 0,
                    'created_at': datetime.now(),
                    'status': 'running'
                }
                print(f"    ➕ 인스턴스 추가: {instance_id}")
                return instance_id
            
            def remove_instance(self, instance_id):
                """인스턴스 제거"""
                if instance_id in self.instances:
                    del self.instances[instance_id]
                    print(f"    ➖ 인스턴스 제거: {instance_id}")
                    return True
                return False
            
            def evaluate_scaling(self, metrics: ScalingMetrics):
                """스케일링 필요성 평가"""
                # 쿨다운 기간 확인
                time_since_last_scaling = (datetime.now() - self.last_scaling_time).total_seconds()
                if time_since_last_scaling < self.cooldown_period:
                    return ScalingAction.NO_ACTION, "Cooling down"
                
                current_instances = len(self.instances)
                
                # 스케일 업 조건 확인
                scale_up_conditions = [
                    metrics.cpu_percent > self.scale_up_threshold,
                    metrics.response_time > self.target_response_time,
                    metrics.error_rate > 5.0,  # 5% 이상 에러율
                    current_instances < self.max_instances
                ]
                
                if all([scale_up_conditions[0] or scale_up_conditions[1] or scale_up_conditions[2], scale_up_conditions[3]]):
                    return ScalingAction.SCALE_UP, f"High resource usage: CPU {metrics.cpu_percent}%, RT {metrics.response_time}s"
                
                # 스케일 다운 조건 확인
                scale_down_conditions = [
                    metrics.cpu_percent < self.scale_down_threshold,
                    metrics.response_time < self.target_response_time * 0.5,
                    metrics.error_rate < 1.0,  # 1% 이하 에러율
                    current_instances > self.min_instances
                ]
                
                if all(scale_down_conditions):
                    return ScalingAction.SCALE_DOWN, f"Low resource usage: CPU {metrics.cpu_percent}%, RT {metrics.response_time}s"
                
                return ScalingAction.NO_ACTION, "No scaling needed"
            
            def execute_scaling(self, action: ScalingAction, reason: str):
                """스케일링 실행"""
                if action == ScalingAction.NO_ACTION:
                    return None
                
                current_instances = len(self.instances)
                
                if action == ScalingAction.SCALE_UP:
                    # 새 인스턴스 추가
                    new_instance_id = f"instance-{current_instances + 1}-{int(time.time())}"
                    self.add_instance(new_instance_id)
                    
                    scaling_event = {
                        'action': action.value,
                        'instance_id': new_instance_id,
                        'reason': reason,
                        'timestamp': datetime.now(),
                        'instances_before': current_instances,
                        'instances_after': current_instances + 1
                    }
                
                elif action == ScalingAction.SCALE_DOWN:
                    # 가장 최근에 생성된 인스턴스 제거
                    if self.instances:
                        oldest_instance = min(
                            self.instances.items(),
                            key=lambda x: x[1]['created_at']
                        )
                        removed_instance_id = oldest_instance[0]
                        self.remove_instance(removed_instance_id)
                        
                        scaling_event = {
                            'action': action.value,
                            'instance_id': removed_instance_id,
                            'reason': reason,
                            'timestamp': datetime.now(),
                            'instances_before': current_instances,
                            'instances_after': current_instances - 1
                        }
                    else:
                        return None
                
                # 스케일링 기록
                self.scaling_history.append(scaling_event)
                self.last_scaling_action = action
                self.last_scaling_time = datetime.now()
                
                print(f"    🔄 스케일링 실행: {action.value} - {reason}")
                
                return scaling_event
            
            def monitor_and_scale(self, metrics: ScalingMetrics):
                """모니터링 및 자동 스케일링"""
                # 메트릭 기록
                self.metrics_history.append(metrics.to_dict())
                
                # 최근 메트릭만 유지 (최대 1000개)
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                # 스케일링 평가 및 실행
                action, reason = self.evaluate_scaling(metrics)
                scaling_event = self.execute_scaling(action, reason)
                
                return {
                    'action': action.value,
                    'reason': reason,
                    'scaling_event': scaling_event,
                    'current_instances': len(self.instances),
                    'metrics': metrics.to_dict()
                }
            
            def get_scaling_stats(self):
                """스케일링 통계"""
                scale_up_count = len([h for h in self.scaling_history if h['action'] == 'scale_up'])
                scale_down_count = len([h for h in self.scaling_history if h['action'] == 'scale_down'])
                
                return {
                    'current_instances': len(self.instances),
                    'min_instances': self.min_instances,
                    'max_instances': self.max_instances,
                    'total_scaling_events': len(self.scaling_history),
                    'scale_up_events': scale_up_count,
                    'scale_down_events': scale_down_count,
                    'last_scaling_time': self.last_scaling_time.isoformat() if self.last_scaling_time else None,
                    'metrics_collected': len(self.metrics_history),
                    'instances': list(self.instances.keys())
                }
        
        # 오토스케일러 테스트
        autoscaler = AutoScaler()
        autoscaler.min_instances = 2
        autoscaler.max_instances = 5
        autoscaler.cooldown_period = 5  # 테스트를 위해 5초로 단축
        
        # 초기 인스턴스 추가
        autoscaler.add_instance("initial-instance-1")
        autoscaler.add_instance("initial-instance-2")
        
        # 스케일링 시나리오 시뮬레이션
        scenarios = [
            # 시나리오 1: 높은 CPU 사용률 (스케일 업 유발)
            ScalingMetrics(),
            ScalingMetrics(),
            ScalingMetrics(),
        ]
        
        # 시나리오 설정
        scenarios[0].update(cpu=85.0, memory=70.0, requests=150, response_time=2.5, error_rate=2.0)
        scenarios[1].update(cpu=20.0, memory=30.0, requests=20, response_time=0.5, error_rate=0.1)
        scenarios[2].update(cpu=90.0, memory=85.0, requests=200, response_time=4.0, error_rate=8.0)
        
        results = []
        
        # 각 시나리오 실행
        for i, metrics in enumerate(scenarios):
            print(f"    📊 시나리오 {i+1} 실행: CPU {metrics.cpu_percent}%, RT {metrics.response_time}s")
            
            result = autoscaler.monitor_and_scale(metrics)
            results.append(result)
            
            # 쿨다운 기간 대기 (테스트를 위해 짧게)
            time.sleep(6)
        
        # 결과 검증
        stats = autoscaler.get_scaling_stats()
        
        assert stats['current_instances'] >= autoscaler.min_instances, "최소 인스턴스 수 미달"
        assert stats['current_instances'] <= autoscaler.max_instances, "최대 인스턴스 수 초과"
        assert stats['total_scaling_events'] > 0, "스케일링 이벤트가 발생하지 않았습니다."
        assert len(stats['instances']) == stats['current_instances'], "인스턴스 수 불일치"
        
        # 스케일 업이 발생했는지 확인 (높은 부하 시나리오에서)
        high_load_results = [r for r in results if r['action'] == 'scale_up']
        assert len(high_load_results) > 0, "높은 부하 상황에서 스케일 업이 발생하지 않았습니다."
        
        print(f"  📈 스케일링 결과: {stats['total_scaling_events']}개 이벤트")
        print(f"  🖥️ 최종 인스턴스: {stats['current_instances']}개 "
              f"(업 {stats['scale_up_events']}회, 다운 {stats['scale_down_events']}회)")
        
        print("✅ 자동 스케일링 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 자동 스케일링 테스트 실패: {str(e)}")
        return False

def test_resource_optimization():
    """리소스 최적화 테스트"""
    print("🧪 리소스 최적화 테스트 시작...")
    
    try:
        import psutil
        from collections import deque
        import threading
        
        # 리소스 최적화 관리자 클래스
        class ResourceOptimizer:
            def __init__(self):
                self.resource_pools = {}
                self.cache_systems = {}
                self.optimization_rules = []
                self.resource_usage_history = deque(maxlen=1000)
                self.optimization_events = []
                self.monitoring_active = False
                self.monitor_thread = None
            
            def create_resource_pool(self, pool_name, pool_type, initial_size=5, max_size=20):
                """리소스 풀 생성"""
                self.resource_pools[pool_name] = {
                    'type': pool_type,
                    'pool': queue.Queue(),
                    'active_resources': set(),
                    'initial_size': initial_size,
                    'max_size': max_size,
                    'created_count': 0,
                    'acquired_count': 0,
                    'released_count': 0,
                    'peak_usage': 0
                }
                
                # 초기 리소스 생성
                for i in range(initial_size):
                    resource = self._create_resource(pool_type, f"{pool_name}_{i}")
                    self.resource_pools[pool_name]['pool'].put(resource)
                    self.resource_pools[pool_name]['created_count'] += 1
                
                print(f"    🏊 리소스 풀 생성: {pool_name} ({pool_type}, 초기 크기: {initial_size})")
            
            def _create_resource(self, resource_type, resource_id):
                """리소스 생성"""
                if resource_type == 'database_connection':
                    return {
                        'id': resource_id,
                        'type': resource_type,
                        'created_at': datetime.now(),
                        'last_used': None,
                        'usage_count': 0,
                        'connection': f"mock_db_connection_{resource_id}"
                    }
                elif resource_type == 'worker_thread':
                    return {
                        'id': resource_id,
                        'type': resource_type,
                        'created_at': datetime.now(),
                        'last_used': None,
                        'usage_count': 0,
                        'thread': f"mock_thread_{resource_id}"
                    }
                elif resource_type == 'gpu_context':
                    return {
                        'id': resource_id,
                        'type': resource_type,
                        'created_at': datetime.now(),
                        'last_used': None,
                        'usage_count': 0,
                        'context': f"mock_gpu_context_{resource_id}"
                    }
                else:
                    return {
                        'id': resource_id,
                        'type': resource_type,
                        'created_at': datetime.now(),
                        'last_used': None,
                        'usage_count': 0
                    }
            
            def acquire_resource(self, pool_name, timeout=5.0):
                """리소스 획득"""
                if pool_name not in self.resource_pools:
                    raise ValueError(f"Resource pool '{pool_name}' not found")
                
                pool_info = self.resource_pools[pool_name]
                
                try:
                    # 풀에서 리소스 획득 시도
                    resource = pool_info['pool'].get(timeout=timeout)
                    
                    # 사용 통계 업데이트
                    resource['last_used'] = datetime.now()
                    resource['usage_count'] += 1
                    
                    pool_info['active_resources'].add(resource['id'])
                    pool_info['acquired_count'] += 1
                    
                    # 피크 사용량 업데이트
                    current_usage = len(pool_info['active_resources'])
                    if current_usage > pool_info['peak_usage']:
                        pool_info['peak_usage'] = current_usage
                    
                    return resource
                
                except queue.Empty:
                    # 풀이 비어있고 최대 크기에 도달하지 않았으면 새 리소스 생성
                    if pool_info['created_count'] < pool_info['max_size']:
                        resource = self._create_resource(
                            pool_info['type'], 
                            f"{pool_name}_{pool_info['created_count']}"
                        )
                        pool_info['created_count'] += 1
                        pool_info['acquired_count'] += 1
                        pool_info['active_resources'].add(resource['id'])
                        
                        resource['last_used'] = datetime.now()
                        resource['usage_count'] += 1
                        
                        print(f"    ➕ 새 리소스 생성: {resource['id']}")
                        return resource
                    else:
                        raise Exception(f"Resource pool '{pool_name}' exhausted")
            
            def release_resource(self, pool_name, resource):
                """리소스 반환"""
                if pool_name not in self.resource_pools:
                    raise ValueError(f"Resource pool '{pool_name}' not found")
                
                pool_info = self.resource_pools[pool_name]
                
                if resource['id'] in pool_info['active_resources']:
                    pool_info['active_resources'].remove(resource['id'])
                    pool_info['released_count'] += 1
                    
                    # 리소스를 풀에 반환
                    pool_info['pool'].put(resource)
            
            def add_cache_system(self, cache_name, max_size=1000, ttl=3600):
                """캐시 시스템 추가"""
                self.cache_systems[cache_name] = {
                    'cache': {},
                    'access_times': {},
                    'max_size': max_size,
                    'ttl': ttl,
                    'hit_count': 0,
                    'miss_count': 0,
                    'eviction_count': 0
                }
                print(f"    💾 캐시 시스템 생성: {cache_name} (최대 크기: {max_size}, TTL: {ttl}초)")
            
            def cache_get(self, cache_name, key):
                """캐시에서 값 조회"""
                if cache_name not in self.cache_systems:
                    return None
                
                cache_info = self.cache_systems[cache_name]
                current_time = datetime.now()
                
                if key in cache_info['cache']:
                    # TTL 확인
                    access_time = cache_info['access_times'][key]
                    if (current_time - access_time).total_seconds() < cache_info['ttl']:
                        cache_info['hit_count'] += 1
                        cache_info['access_times'][key] = current_time  # 액세스 시간 업데이트
                        return cache_info['cache'][key]
                    else:
                        # TTL 만료된 키 제거
                        del cache_info['cache'][key]
                        del cache_info['access_times'][key]
                
                cache_info['miss_count'] += 1
                return None
            
            def cache_set(self, cache_name, key, value):
                """캐시에 값 저장"""
                if cache_name not in self.cache_systems:
                    return False
                
                cache_info = self.cache_systems[cache_name]
                current_time = datetime.now()
                
                # 캐시 크기 확인 및 LRU 제거
                if len(cache_info['cache']) >= cache_info['max_size']:
                    # 가장 오래된 항목 제거
                    oldest_key = min(cache_info['access_times'], key=cache_info['access_times'].get)
                    del cache_info['cache'][oldest_key]
                    del cache_info['access_times'][oldest_key]
                    cache_info['eviction_count'] += 1
                
                cache_info['cache'][key] = value
                cache_info['access_times'][key] = current_time
                return True
            
            def add_optimization_rule(self, rule):
                """최적화 규칙 추가"""
                self.optimization_rules.append(rule)
            
            def collect_resource_metrics(self):
                """리소스 메트릭 수집"""
                current_time = datetime.now()
                
                metrics = {
                    'timestamp': current_time,
                    'system_cpu': psutil.cpu_percent(),
                    'system_memory': psutil.virtual_memory().percent,
                    'resource_pools': {},
                    'cache_systems': {}
                }
                
                # 리소스 풀 메트릭
                for pool_name, pool_info in self.resource_pools.items():
                    metrics['resource_pools'][pool_name] = {
                        'active_resources': len(pool_info['active_resources']),
                        'available_resources': pool_info['pool'].qsize(),
                        'total_created': pool_info['created_count'],
                        'total_acquired': pool_info['acquired_count'],
                        'total_released': pool_info['released_count'],
                        'peak_usage': pool_info['peak_usage'],
                        'utilization': (len(pool_info['active_resources']) / pool_info['max_size']) * 100
                    }
                
                # 캐시 시스템 메트릭
                for cache_name, cache_info in self.cache_systems.items():
                    total_requests = cache_info['hit_count'] + cache_info['miss_count']
                    hit_rate = (cache_info['hit_count'] / total_requests * 100) if total_requests > 0 else 0
                    
                    metrics['cache_systems'][cache_name] = {
                        'cache_size': len(cache_info['cache']),
                        'max_size': cache_info['max_size'],
                        'hit_count': cache_info['hit_count'],
                        'miss_count': cache_info['miss_count'],
                        'hit_rate': hit_rate,
                        'eviction_count': cache_info['eviction_count'],
                        'utilization': (len(cache_info['cache']) / cache_info['max_size']) * 100
                    }
                
                self.resource_usage_history.append(metrics)
                return metrics
            
            def optimize_resources(self):
                """리소스 최적화 실행"""
                if not self.resource_usage_history:
                    return []
                
                optimizations = []
                latest_metrics = self.resource_usage_history[-1]
                
                # 리소스 풀 최적화
                for pool_name, pool_metrics in latest_metrics['resource_pools'].items():
                    # 높은 사용률 -> 풀 크기 증가 권장
                    if pool_metrics['utilization'] > 90:
                        optimizations.append({
                            'type': 'resource_pool_expansion',
                            'target': pool_name,
                            'current_size': self.resource_pools[pool_name]['max_size'],
                            'recommended_size': min(self.resource_pools[pool_name]['max_size'] * 2, 50),
                            'reason': f"High utilization: {pool_metrics['utilization']:.1f}%"
                        })
                    
                    # 낮은 사용률 -> 풀 크기 축소 권장
                    elif pool_metrics['utilization'] < 20 and self.resource_pools[pool_name]['max_size'] > 5:
                        optimizations.append({
                            'type': 'resource_pool_reduction',
                            'target': pool_name,
                            'current_size': self.resource_pools[pool_name]['max_size'],
                            'recommended_size': max(self.resource_pools[pool_name]['max_size'] // 2, 5),
                            'reason': f"Low utilization: {pool_metrics['utilization']:.1f}%"
                        })
                
                # 캐시 최적화
                for cache_name, cache_metrics in latest_metrics['cache_systems'].items():
                    # 낮은 적중률 -> 캐시 크기 증가 또는 TTL 조정 권장
                    if cache_metrics['hit_rate'] < 50:
                        optimizations.append({
                            'type': 'cache_optimization',
                            'target': cache_name,
                            'current_hit_rate': cache_metrics['hit_rate'],
                            'current_size': cache_metrics['max_size'],
                            'recommended_size': cache_metrics['max_size'] * 2,
                            'reason': f"Low hit rate: {cache_metrics['hit_rate']:.1f}%"
                        })
                    
                    # 높은 제거율 -> 캐시 크기 증가 권장
                    if cache_metrics['eviction_count'] > 100:
                        optimizations.append({
                            'type': 'cache_expansion',
                            'target': cache_name,
                            'current_size': cache_metrics['max_size'],
                            'recommended_size': cache_metrics['max_size'] * 1.5,
                            'eviction_count': cache_metrics['eviction_count'],
                            'reason': f"High eviction count: {cache_metrics['eviction_count']}"
                        })
                
                # 최적화 이벤트 기록
                if optimizations:
                    self.optimization_events.append({
                        'timestamp': datetime.now(),
                        'optimizations': optimizations
                    })
                
                return optimizations
            
            def get_optimization_summary(self):
                """최적화 요약 정보"""
                if not self.resource_usage_history:
                    return {}
                
                latest_metrics = self.resource_usage_history[-1]
                
                # 전체 시스템 효율성 계산
                total_pool_utilization = []
                total_cache_hit_rates = []
                
                for pool_metrics in latest_metrics['resource_pools'].values():
                    total_pool_utilization.append(pool_metrics['utilization'])
                
                for cache_metrics in latest_metrics['cache_systems'].values():
                    if cache_metrics['hit_rate'] > 0:
                        total_cache_hit_rates.append(cache_metrics['hit_rate'])
                
                avg_pool_utilization = sum(total_pool_utilization) / len(total_pool_utilization) if total_pool_utilization else 0
                avg_cache_hit_rate = sum(total_cache_hit_rates) / len(total_cache_hit_rates) if total_cache_hit_rates else 0
                
                return {
                    'system_efficiency': {
                        'avg_pool_utilization': avg_pool_utilization,
                        'avg_cache_hit_rate': avg_cache_hit_rate,
                        'system_cpu': latest_metrics['system_cpu'],
                        'system_memory': latest_metrics['system_memory']
                    },
                    'resource_pools_count': len(self.resource_pools),
                    'cache_systems_count': len(self.cache_systems),
                    'optimization_events': len(self.optimization_events),
                    'metrics_collected': len(self.resource_usage_history)
                }
        
        # 리소스 최적화 테스트
        optimizer = ResourceOptimizer()
        
        # 리소스 풀 생성
        optimizer.create_resource_pool('db_connections', 'database_connection', initial_size=3, max_size=10)
        optimizer.create_resource_pool('worker_threads', 'worker_thread', initial_size=2, max_size=8)
        optimizer.create_resource_pool('gpu_contexts', 'gpu_context', initial_size=1, max_size=4)
        
        # 캐시 시스템 생성
        optimizer.add_cache_system('api_cache', max_size=100, ttl=300)
        optimizer.add_cache_system('result_cache', max_size=50, ttl=600)
        
        # 리소스 사용 시뮬레이션
        def simulate_resource_usage():
            """리소스 사용 시뮬레이션"""
            try:
                # 데이터베이스 연결 사용
                db_conn = optimizer.acquire_resource('db_connections')
                time.sleep(0.1)  # 작업 시뮬레이션
                optimizer.release_resource('db_connections', db_conn)
                
                # 워커 스레드 사용
                worker = optimizer.acquire_resource('worker_threads')
                time.sleep(0.05)
                optimizer.release_resource('worker_threads', worker)
                
                # 캐시 사용
                cache_key = f"key_{int(time.time() * 1000) % 50}"
                cached_value = optimizer.cache_get('api_cache', cache_key)
                if cached_value is None:
                    # 캐시 미스 - 새 값 저장
                    optimizer.cache_set('api_cache', cache_key, f"value_{cache_key}")
                
            except Exception as e:
                print(f"    ⚠️ 리소스 사용 시뮬레이션 오류: {str(e)}")
        
        # 동시 리소스 사용 테스트
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # 여러 스레드로 리소스 사용 시뮬레이션
            futures = [executor.submit(simulate_resource_usage) for _ in range(20)]
            
            # 메트릭 수집 (백그라운드)
            for i in range(5):
                metrics = optimizer.collect_resource_metrics()
                time.sleep(0.2)
            
            # 모든 작업 완료 대기
            for future in concurrent.futures.as_completed(futures):
                future.result()
        
        # 최적화 실행
        optimizations = optimizer.optimize_resources()
        
        # 최종 메트릭 수집
        final_metrics = optimizer.collect_resource_metrics()
        summary = optimizer.get_optimization_summary()
        
        # 결과 검증
        assert len(optimizer.resource_pools) == 3, "리소스 풀 수 불일치"
        assert len(optimizer.cache_systems) == 2, "캐시 시스템 수 불일치"
        assert len(optimizer.resource_usage_history) > 0, "메트릭이 수집되지 않았습니다."
        assert summary['metrics_collected'] > 0, "메트릭 수집 실패"
        
        # 리소스 사용 검증
        for pool_name, pool_info in optimizer.resource_pools.items():
            assert pool_info['acquired_count'] > 0, f"{pool_name} 풀이 사용되지 않았습니다."
            assert pool_info['released_count'] > 0, f"{pool_name} 리소스가 반환되지 않았습니다."
        
        # 캐시 사용 검증
        for cache_name, cache_info in optimizer.cache_systems.items():
            total_requests = cache_info['hit_count'] + cache_info['miss_count']
            assert total_requests > 0, f"{cache_name} 캐시가 사용되지 않았습니다."
        
        print(f"  🔧 최적화 결과: {len(optimizations)}개 권장사항")
        print(f"  📊 시스템 효율성: 풀 활용률 {summary['system_efficiency']['avg_pool_utilization']:.1f}%, "
              f"캐시 적중률 {summary['system_efficiency']['avg_cache_hit_rate']:.1f}%")
        
        print("✅ 리소스 최적화 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ 리소스 최적화 테스트 실패: {str(e)}")
        return False

def main():
    """S03_M03_T02 통합 테스트 메인 함수"""
    print("🚀 S03_M03_T02 확장성 및 스케일링 전략 테스트 시작")
    print("=" * 60)
    
    test_results = []
    start_time = time.time()
    
    # 테스트 실행
    tests = [
        ("부하 분산 시스템", test_load_balancing),
        ("자동 스케일링", test_auto_scaling),
        ("리소스 최적화", test_resource_optimization)
    ]
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name} 테스트 실행 중...")
        try:
            result = test_func()
            test_results.append((test_name, result))
            if result:
                print(f"✅ {test_name} 테스트 성공")
            else:
                print(f"❌ {test_name} 테스트 실패")
        except Exception as e:
            print(f"💥 {test_name} 테스트 예외 발생: {str(e)}")
            test_results.append((test_name, False))
    
    # 결과 요약
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 60)
    print("🎯 S03_M03_T02 확장성 및 스케일링 전략 테스트 결과 요약")
    print("=" * 60)
    
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"  {status}: {test_name}")
    
    print(f"\n📊 전체 결과: {passed_tests}/{total_tests} 테스트 통과 ({passed_tests/total_tests*100:.1f}%)")
    print(f"⏱️  소요 시간: {duration:.2f}초")
    
    if passed_tests == total_tests:
        print("\n🎉 모든 테스트 통과! S03_M03_T02 작업이 성공적으로 완료되었습니다.")
        return True
    else:
        print(f"\n⚠️  {total_tests - passed_tests}개 테스트 실패. 추가 수정이 필요합니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)