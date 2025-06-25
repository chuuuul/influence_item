"""
실시간 WebSocket 통신 시스템 - 즉각적인 데이터 업데이트
Real-time WebSocket Communication System for Instant Data Updates
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid
import weakref
from dataclasses import dataclass, asdict
from enum import Enum
import websockets
import threading
from concurrent.futures import ThreadPoolExecutor
import queue
import sqlite3
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """메시지 타입 정의"""
    DATA_UPDATE = "data_update"
    USER_ACTION = "user_action"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    NOTIFICATION = "notification"
    PERSONALIZATION = "personalization"
    REAL_TIME_METRICS = "real_time_metrics"

@dataclass
class WebSocketMessage:
    """WebSocket 메시지 데이터 클래스"""
    id: str
    type: MessageType
    timestamp: float
    data: Dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: int = 1  # 1=높음, 2=보통, 3=낮음

@dataclass
class UserSession:
    """사용자 세션 정보"""
    session_id: str
    user_id: Optional[str]
    websocket: Any
    last_seen: float
    preferences: Dict[str, Any]
    subscriptions: List[str]  # 구독 중인 데이터 타입
    connected_at: float

class RealTimeWebSocketSystem:
    """실시간 WebSocket 통신 시스템"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.sessions: Dict[str, UserSession] = {}
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        self.data_subscriptions: Dict[str, List[str]] = {}  # data_type -> session_ids
        
        # 메시지 큐 (우선순위별)
        self.high_priority_queue = queue.Queue()
        self.normal_priority_queue = queue.Queue()
        self.low_priority_queue = queue.Queue()
        
        # 백그라운드 작업자
        self.message_processor = ThreadPoolExecutor(max_workers=4)
        self.running = False
        
        # 통계
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'average_latency': 0,
            'peak_connections': 0
        }
        
        # 데이터베이스 (세션 및 메시지 로그)
        self.db_path = "temp/websocket_sessions.db"
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self._init_database()
        
        # 이벤트 핸들러
        self.on_connect_handlers = []
        self.on_disconnect_handlers = []
        self.on_message_handlers = []
        
        logger.info(f"WebSocket system initialized on {host}:{port}")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    connected_at REAL,
                    last_seen REAL,
                    preferences TEXT,
                    subscriptions TEXT
                )
                """)
                
                conn.execute("""
                CREATE TABLE IF NOT EXISTS message_logs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    message_type TEXT,
                    timestamp REAL,
                    data TEXT,
                    processing_time REAL
                )
                """)
                
                conn.commit()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    async def start_server(self):
        """WebSocket 서버 시작"""
        self.running = True
        
        # 메시지 처리 백그라운드 태스크 시작
        asyncio.create_task(self._process_message_queues())
        asyncio.create_task(self._heartbeat_monitor())
        asyncio.create_task(self._cleanup_inactive_sessions())
        
        # WebSocket 서버 시작
        async with websockets.serve(self._handle_client, self.host, self.port):
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            await asyncio.Future()  # 서버 계속 실행
    
    async def _handle_client(self, websocket, path):
        """클라이언트 연결 처리"""
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        # 새 세션 생성
        session = UserSession(
            session_id=session_id,
            user_id=None,
            websocket=websocket,
            last_seen=current_time,
            preferences={},
            subscriptions=[],
            connected_at=current_time
        )
        
        self.sessions[session_id] = session
        self.stats['total_connections'] += 1
        self.stats['active_connections'] += 1
        self.stats['peak_connections'] = max(self.stats['peak_connections'], self.stats['active_connections'])
        
        # 연결 이벤트 처리
        await self._trigger_event('connect', session)
        
        # 환영 메시지 전송
        welcome_message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.SYSTEM_STATUS,
            timestamp=current_time,
            data={
                'status': 'connected',
                'session_id': session_id,
                'server_time': datetime.now().isoformat()
            },
            session_id=session_id
        )
        await self._send_message(websocket, welcome_message)
        
        try:
            # 메시지 수신 루프
            async for message in websocket:
                await self._handle_incoming_message(session, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {session_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {session_id}: {e}")
        finally:
            # 세션 정리
            await self._cleanup_session(session_id)
    
    async def _handle_incoming_message(self, session: UserSession, raw_message: str):
        """수신 메시지 처리"""
        try:
            message_data = json.loads(raw_message)
            message = WebSocketMessage(
                id=message_data.get('id', str(uuid.uuid4())),
                type=MessageType(message_data.get('type', 'user_action')),
                timestamp=time.time(),
                data=message_data.get('data', {}),
                user_id=session.user_id,
                session_id=session.session_id
            )
            
            # 세션 업데이트
            session.last_seen = time.time()
            self.stats['messages_received'] += 1
            
            # 메시지 타입별 처리
            await self._process_incoming_message(session, message)
            
            # 이벤트 핸들러 실행
            await self._trigger_event('message', session, message)
            
        except Exception as e:
            logger.error(f"Error processing message from {session.session_id}: {e}")
            error_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                timestamp=time.time(),
                data={'error': 'Invalid message format', 'details': str(e)},
                session_id=session.session_id
            )
            await self._send_message(session.websocket, error_message)
    
    async def _process_incoming_message(self, session: UserSession, message: WebSocketMessage):
        """수신 메시지 타입별 처리"""
        if message.type == MessageType.USER_ACTION:
            # 사용자 액션 처리
            action = message.data.get('action')
            
            if action == 'subscribe':
                # 데이터 구독
                data_types = message.data.get('data_types', [])
                session.subscriptions.extend(data_types)
                session.subscriptions = list(set(session.subscriptions))  # 중복 제거
                
                # 구독 목록 업데이트
                for data_type in data_types:
                    if data_type not in self.data_subscriptions:
                        self.data_subscriptions[data_type] = []
                    if session.session_id not in self.data_subscriptions[data_type]:
                        self.data_subscriptions[data_type].append(session.session_id)
                
                # 확인 메시지 전송
                response = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.SYSTEM_STATUS,
                    timestamp=time.time(),
                    data={'status': 'subscribed', 'data_types': data_types},
                    session_id=session.session_id
                )
                await self._send_message(session.websocket, response)
                
            elif action == 'unsubscribe':
                # 구독 해제
                data_types = message.data.get('data_types', [])
                for data_type in data_types:
                    if data_type in session.subscriptions:
                        session.subscriptions.remove(data_type)
                    if data_type in self.data_subscriptions:
                        if session.session_id in self.data_subscriptions[data_type]:
                            self.data_subscriptions[data_type].remove(session.session_id)
                
            elif action == 'set_preferences':
                # 사용자 선호도 설정
                preferences = message.data.get('preferences', {})
                session.preferences.update(preferences)
                session.user_id = preferences.get('user_id', session.user_id)
                
                # 개인화 메시지 전송
                personalization_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.PERSONALIZATION,
                    timestamp=time.time(),
                    data={'preferences_updated': True},
                    session_id=session.session_id
                )
                await self._send_message(session.websocket, personalization_message)
        
        elif message.type == MessageType.HEARTBEAT:
            # 하트비트 응답
            pong_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.HEARTBEAT,
                timestamp=time.time(),
                data={'pong': True},
                session_id=session.session_id
            )
            await self._send_message(session.websocket, pong_message)
    
    async def _send_message(self, websocket, message: WebSocketMessage):
        """메시지 전송"""
        try:
            start_time = time.time()
            message_json = json.dumps(asdict(message), default=str)
            await websocket.send(message_json)
            
            # 응답 시간 측정
            latency = time.time() - start_time
            self.stats['average_latency'] = (self.stats['average_latency'] + latency) / 2
            self.stats['messages_sent'] += 1
            
            # 로그 저장
            self._log_message(message, latency)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    def _log_message(self, message: WebSocketMessage, processing_time: float):
        """메시지 로그 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                INSERT INTO message_logs (id, session_id, message_type, timestamp, data, processing_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    message.id,
                    message.session_id,
                    message.type.value,
                    message.timestamp,
                    json.dumps(message.data),
                    processing_time
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log message: {e}")
    
    async def broadcast_data_update(self, data_type: str, data: Dict[str, Any], priority: int = 1):
        """특정 데이터 타입 구독자들에게 업데이트 브로드캐스트"""
        if data_type not in self.data_subscriptions:
            return
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.DATA_UPDATE,
            timestamp=time.time(),
            data={
                'data_type': data_type,
                'content': data,
                'update_time': datetime.now().isoformat()
            },
            priority=priority
        )
        
        # 구독자들에게 메시지 전송
        session_ids = self.data_subscriptions[data_type]
        for session_id in session_ids.copy():  # 복사본으로 순회
            if session_id in self.sessions:
                await self._queue_message(session_id, message)
            else:
                # 세션이 없으면 구독 목록에서 제거
                session_ids.remove(session_id)
    
    async def send_notification(self, user_id: str, title: str, message: str, priority: int = 1):
        """특정 사용자에게 알림 전송"""
        notification_data = {
            'title': title,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        notification_message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.NOTIFICATION,
            timestamp=time.time(),
            data=notification_data,
            user_id=user_id,
            priority=priority
        )
        
        # 해당 사용자의 모든 세션에 전송
        for session in self.sessions.values():
            if session.user_id == user_id:
                await self._queue_message(session.session_id, notification_message)
    
    async def _queue_message(self, session_id: str, message: WebSocketMessage):
        """메시지를 우선순위 큐에 추가"""
        message.session_id = session_id
        
        if message.priority == 1:
            self.high_priority_queue.put(message)
        elif message.priority == 2:
            self.normal_priority_queue.put(message)
        else:
            self.low_priority_queue.put(message)
    
    async def _process_message_queues(self):
        """메시지 큐 처리 (우선순위별)"""
        while self.running:
            try:
                # 우선순위별로 메시지 처리
                for priority_queue in [self.high_priority_queue, self.normal_priority_queue, self.low_priority_queue]:
                    while not priority_queue.empty():
                        try:
                            message = priority_queue.get_nowait()
                            session = self.sessions.get(message.session_id)
                            if session and session.websocket:
                                await self._send_message(session.websocket, message)
                        except queue.Empty:
                            break
                        except Exception as e:
                            logger.error(f"Error processing queued message: {e}")
                
                # 짧은 대기
                await asyncio.sleep(0.01)  # 10ms 간격으로 처리
                
            except Exception as e:
                logger.error(f"Error in message queue processor: {e}")
                await asyncio.sleep(1)
    
    async def _heartbeat_monitor(self):
        """하트비트 모니터링"""
        while self.running:
            try:
                current_time = time.time()
                
                for session_id, session in list(self.sessions.items()):
                    # 30초 이상 비활성 세션 체크
                    if current_time - session.last_seen > 30:
                        try:
                            # 하트비트 전송
                            heartbeat_message = WebSocketMessage(
                                id=str(uuid.uuid4()),
                                type=MessageType.HEARTBEAT,
                                timestamp=current_time,
                                data={'ping': True},
                                session_id=session_id
                            )
                            await self._send_message(session.websocket, heartbeat_message)
                        except Exception:
                            # 연결이 끊어진 세션 제거
                            await self._cleanup_session(session_id)
                
                # 30초마다 하트비트 체크
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup_inactive_sessions(self):
        """비활성 세션 정리"""
        while self.running:
            try:
                current_time = time.time()
                inactive_sessions = []
                
                for session_id, session in self.sessions.items():
                    # 5분 이상 비활성 세션 식별
                    if current_time - session.last_seen > 300:
                        inactive_sessions.append(session_id)
                
                # 비활성 세션 제거
                for session_id in inactive_sessions:
                    await self._cleanup_session(session_id)
                
                # 5분마다 정리
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(300)
    
    async def _cleanup_session(self, session_id: str):
        """세션 정리"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # 구독 목록에서 제거
            for data_type in session.subscriptions:
                if data_type in self.data_subscriptions:
                    if session_id in self.data_subscriptions[data_type]:
                        self.data_subscriptions[data_type].remove(session_id)
            
            # 세션 제거
            del self.sessions[session_id]
            self.stats['active_connections'] -= 1
            
            # 연결 해제 이벤트 처리
            await self._trigger_event('disconnect', session)
            
            logger.info(f"Session {session_id} cleaned up")
    
    async def _trigger_event(self, event_type: str, *args):
        """이벤트 핸들러 실행"""
        handlers = getattr(self, f'on_{event_type}_handlers', [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args)
                else:
                    handler(*args)
            except Exception as e:
                logger.error(f"Error in {event_type} handler: {e}")
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """이벤트 핸들러 추가"""
        handler_list = getattr(self, f'on_{event_type}_handlers', None)
        if handler_list is not None:
            handler_list.append(handler)
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        return {
            **self.stats,
            'active_sessions': len(self.sessions),
            'data_subscriptions': {k: len(v) for k, v in self.data_subscriptions.items()},
            'queue_sizes': {
                'high_priority': self.high_priority_queue.qsize(),
                'normal_priority': self.normal_priority_queue.qsize(),
                'low_priority': self.low_priority_queue.qsize()
            }
        }
    
    async def stop_server(self):
        """서버 종료"""
        self.running = False
        
        # 모든 세션에 종료 알림
        for session in self.sessions.values():
            try:
                shutdown_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.SYSTEM_STATUS,
                    timestamp=time.time(),
                    data={'status': 'server_shutdown'},
                    session_id=session.session_id
                )
                await self._send_message(session.websocket, shutdown_message)
                await session.websocket.close()
            except Exception:
                pass
        
        self.sessions.clear()
        logger.info("WebSocket server stopped")

# 글로벌 WebSocket 시스템 인스턴스
_websocket_system = None

def get_websocket_system() -> RealTimeWebSocketSystem:
    """글로벌 WebSocket 시스템 인스턴스 반환"""
    global _websocket_system
    if _websocket_system is None:
        _websocket_system = RealTimeWebSocketSystem()
    return _websocket_system

# Streamlit 통합을 위한 클래스
class StreamlitWebSocketIntegration:
    """Streamlit과 WebSocket 통합"""
    
    def __init__(self):
        self.websocket_system = get_websocket_system()
        self._setup_streamlit_integration()
    
    def _setup_streamlit_integration(self):
        """Streamlit 통합 설정"""
        import streamlit as st
        
        # WebSocket 클라이언트 JavaScript 코드
        websocket_js = """
        <script>
        class StreamlitWebSocket {
            constructor() {
                this.ws = null;
                this.sessionId = null;
                this.reconnectInterval = 5000;
                this.maxReconnectAttempts = 10;
                this.reconnectAttempts = 0;
                this.subscriptions = new Set();
                this.connect();
            }
            
            connect() {
                try {
                    this.ws = new WebSocket('ws://localhost:8765');
                    
                    this.ws.onopen = (event) => {
                        console.log('WebSocket connected');
                        this.reconnectAttempts = 0;
                        this.sendHeartbeat();
                    };
                    
                    this.ws.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        this.handleMessage(message);
                    };
                    
                    this.ws.onclose = (event) => {
                        console.log('WebSocket disconnected');
                        this.scheduleReconnect();
                    };
                    
                    this.ws.onerror = (error) => {
                        console.error('WebSocket error:', error);
                    };
                } catch (error) {
                    console.error('Failed to connect WebSocket:', error);
                    this.scheduleReconnect();
                }
            }
            
            handleMessage(message) {
                switch (message.type) {
                    case 'data_update':
                        this.handleDataUpdate(message);
                        break;
                    case 'notification':
                        this.handleNotification(message);
                        break;
                    case 'system_status':
                        if (message.data.session_id) {
                            this.sessionId = message.data.session_id;
                        }
                        break;
                    case 'personalization':
                        this.handlePersonalization(message);
                        break;
                }
            }
            
            handleDataUpdate(message) {
                // Streamlit 컴포넌트 업데이트 트리거
                const event = new CustomEvent('streamlit-data-update', {
                    detail: message.data
                });
                window.dispatchEvent(event);
                
                // 특정 데이터 타입에 따른 UI 업데이트
                if (message.data.data_type === 'dashboard_metrics') {
                    this.updateDashboardMetrics(message.data.content);
                }
            }
            
            handleNotification(message) {
                // 브라우저 알림 표시
                if (Notification.permission === 'granted') {
                    new Notification(message.data.title, {
                        body: message.data.message,
                        icon: '/favicon.ico'
                    });
                }
                
                // Streamlit 알림 이벤트
                const event = new CustomEvent('streamlit-notification', {
                    detail: message.data
                });
                window.dispatchEvent(event);
            }
            
            handlePersonalization(message) {
                // 개인화 이벤트 처리
                const event = new CustomEvent('streamlit-personalization', {
                    detail: message.data
                });
                window.dispatchEvent(event);
            }
            
            updateDashboardMetrics(metrics) {
                // 대시보드 메트릭 실시간 업데이트
                Object.keys(metrics).forEach(metricKey => {
                    const element = document.querySelector(`[data-metric="${metricKey}"]`);
                    if (element) {
                        element.textContent = metrics[metricKey];
                    }
                });
            }
            
            subscribe(dataTypes) {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    dataTypes.forEach(type => this.subscriptions.add(type));
                    this.ws.send(JSON.stringify({
                        id: this.generateId(),
                        type: 'user_action',
                        data: {
                            action: 'subscribe',
                            data_types: Array.from(this.subscriptions)
                        }
                    }));
                }
            }
            
            sendHeartbeat() {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        id: this.generateId(),
                        type: 'heartbeat',
                        data: { ping: true }
                    }));
                }
                setTimeout(() => this.sendHeartbeat(), 30000); // 30초마다
            }
            
            scheduleReconnect() {
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    setTimeout(() => {
                        console.log(`Reconnecting... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
                        this.reconnectAttempts++;
                        this.connect();
                    }, this.reconnectInterval);
                }
            }
            
            generateId() {
                return 'ws-' + Math.random().toString(36).substr(2, 9);
            }
        }
        
        // 전역 WebSocket 인스턴스
        window.streamlitWS = new StreamlitWebSocket();
        
        // 알림 권한 요청
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        </script>
        """
        
        # JavaScript 코드를 Streamlit에 삽입
        st.components.v1.html(websocket_js, height=0)
    
    def subscribe_to_updates(self, data_types: List[str]):
        """데이터 업데이트 구독"""
        import streamlit as st
        
        subscribe_js = f"""
        <script>
        if (window.streamlitWS) {{
            window.streamlitWS.subscribe({json.dumps(data_types)});
        }}
        </script>
        """
        
        st.components.v1.html(subscribe_js, height=0)
    
    def send_real_time_update(self, data_type: str, data: Dict[str, Any]):
        """실시간 데이터 업데이트 전송"""
        asyncio.create_task(
            self.websocket_system.broadcast_data_update(data_type, data, priority=1)
        )

# 편의 함수들
def start_websocket_server():
    """WebSocket 서버 시작 (백그라운드)"""
    def run_server():
        asyncio.set_event_loop(asyncio.new_event_loop())
        websocket_system = get_websocket_system()
        asyncio.get_event_loop().run_until_complete(websocket_system.start_server())
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread

def get_streamlit_websocket() -> StreamlitWebSocketIntegration:
    """Streamlit WebSocket 통합 인스턴스 반환"""
    return StreamlitWebSocketIntegration()

if __name__ == "__main__":
    # 테스트 코드
    async def test_websocket():
        system = RealTimeWebSocketSystem()
        
        # 테스트 이벤트 핸들러
        def on_connect(session):
            print(f"Client connected: {session.session_id}")
        
        def on_disconnect(session):
            print(f"Client disconnected: {session.session_id}")
        
        system.add_event_handler('connect', on_connect)
        system.add_event_handler('disconnect', on_disconnect)
        
        # 서버 시작
        await system.start_server()
    
    # 서버 실행
    asyncio.run(test_websocket())