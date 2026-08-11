import asyncio
import time
from typing import Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import structlog
from observability.metrics_collector import websocket_active_connections

from configs.config import settings

logger = structlog.get_logger(__name__)

class IncidentFeedManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_ips: Dict[str, str] = {}  # client_id -> ip
        self.ip_counts: Dict[str, int] = {}  # ip -> count
        self.queues: Dict[str, asyncio.Queue] = {}
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        self.global_limit = settings.WS_GLOBAL_LIMIT
        self.ip_limit = settings.WS_IP_LIMIT
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str, ip: str):
        async with self._lock:
            # 1. Global limit check
            if len(self.active_connections) >= self.global_limit:
                logger.warning("Global WebSocket limit reached", limit=self.global_limit)
                await websocket.close(code=1008, reason="Global connection limit reached")
                return False

            # 2. Per-IP limit check
            current_ip_count = self.ip_counts.get(ip, 0)
            if current_ip_count >= self.ip_limit:
                logger.warning("IP WebSocket limit reached", ip=ip, limit=self.ip_limit)
                await websocket.close(code=1008, reason="Too many connections from this IP")
                return False

            await websocket.accept()
            
            # 3. Handle existing connection for same client_id (Enforce ONE connection)
            if client_id in self.active_connections:
                logger.info("Closing duplicate connection", client_id=client_id)
                await self._close_connection(client_id)
            
            # 4. Register new connection
            self.active_connections[client_id] = websocket
            self.client_ips[client_id] = ip
            self.ip_counts[ip] = self.ip_counts.get(ip, 0) + 1
            self.queues[client_id] = asyncio.Queue(maxsize=100) # Backpressure buffer
            
            # Start sender task for this client
            self.heartbeat_tasks[client_id] = asyncio.create_task(self._client_sender(client_id))
            
            websocket_active_connections.inc()
            logger.info("WebSocket client connected", 
                        client_id=client_id, 
                        ip=ip, 
                        total=len(self.active_connections))
            return True

    async def _client_sender(self, client_id: str):
        """Background task to send messages from the queue to the client."""
        ws = self.active_connections.get(client_id)
        queue = self.queues.get(client_id)
        if not ws or not queue:
            return

        try:
            while True:
                message = await queue.get()
                try:
                    await ws.send_json(message)
                except Exception:
                    logger.debug("Failed to send message to client", client_id=client_id)
                    break
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Sender task error", client_id=client_id, error=str(e))
        finally:
            # Connection cleanup is handled by disconnect()
            pass

    async def _close_connection(self, client_id: str):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.close(code=1000)
            except Exception:
                pass
        self.disconnect(client_id)

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            
            ip = self.client_ips.pop(client_id, None)
            if ip and ip in self.ip_counts:
                self.ip_counts[ip] -= 1
                if self.ip_counts[ip] <= 0:
                    del self.ip_counts[ip]
            
            self.queues.pop(client_id, None)
            
            task = self.heartbeat_tasks.pop(client_id, None)
            if task:
                task.cancel()
            
            websocket_active_connections.dec()
            logger.info("WebSocket client disconnected", 
                        client_id=client_id, 
                        total=len(self.active_connections))

    async def broadcast(self, message: dict):
        """Broadcast message to all clients with backpressure (drop if queue full)."""
        for client_id, queue in list(self.queues.items()):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Backpressure: Client queue full - dropping message", client_id=client_id)

    async def shutdown(self):
        """Graceful cleanup of all connections."""
        logger.info("Shutting down WebSocket manager", total=len(self.active_connections))
        client_ids = list(self.active_connections.keys())
        tasks = [self._close_connection(cid) for cid in client_ids]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

feed_manager = IncidentFeedManager()
