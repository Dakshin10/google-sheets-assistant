from fastapi import WebSocket
from typing import List
from monitoring.logger import logger

class WebSocketManager:
    """Manages active WebSockets and handles real-time event broadcasting."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: dict):
        """Broadcasts a structured JSON message to all active clients."""
        if not self.active_connections:
            return

        payload = {
            "event": event_type,
            "data": data
        }
        
        logger.info(f"Broadcasting WebSocket event '{event_type}' to {len(self.active_connections)} clients")
        
        # Collect dead connections to remove
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket client: {e}")
                dead_connections.append(connection)

        # Clean up dead connections
        for dead in dead_connections:
            self.disconnect(dead)

# Global singleton manager
ws_manager = WebSocketManager()
