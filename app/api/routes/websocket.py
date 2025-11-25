from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from typing import Dict, Set
import json
from uuid import UUID
import asyncio
from loguru import logger

from app.models.user import User
from app.core.security.auth import verify_token

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time bidding updates"""

    def __init__(self):
        # Map of lot_id to set of websockets watching that lot
        self.lot_watchers: Dict[str, Set[WebSocket]] = {}
        # Map of websocket to user
        self.socket_users: Dict[WebSocket, User] = {}
        # Map of user_id to set of websockets for that user
        self.user_connections: Dict[UUID, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user: User, lot_id: str = None):
        """Connect a new WebSocket"""
        await websocket.accept()

        # Store user for this socket
        self.socket_users[websocket] = user

        # Track user connections
        if user.id not in self.user_connections:
            self.user_connections[user.id] = set()
        self.user_connections[user.id].add(websocket)

        # If watching a specific lot, add to watchers
        if lot_id:
            if lot_id not in self.lot_watchers:
                self.lot_watchers[lot_id] = set()
            self.lot_watchers[lot_id].add(websocket)

        logger.info(f"WebSocket connected: user={user.id}, lot={lot_id}")

    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket"""
        # Remove from lot watchers
        for lot_id, watchers in list(self.lot_watchers.items()):
            if websocket in watchers:
                watchers.remove(websocket)
                if not watchers:
                    del self.lot_watchers[lot_id]

        # Remove from user tracking
        user = self.socket_users.get(websocket)
        if user and user.id in self.user_connections:
            self.user_connections[user.id].discard(websocket)
            if not self.user_connections[user.id]:
                del self.user_connections[user.id]

        # Remove from socket users map
        if websocket in self.socket_users:
            del self.socket_users[websocket]

        logger.info(f"WebSocket disconnected: user={user.id if user else 'unknown'}")

    async def subscribe_to_lot(self, websocket: WebSocket, lot_id: str):
        """Subscribe a WebSocket to a specific lot"""
        if lot_id not in self.lot_watchers:
            self.lot_watchers[lot_id] = set()
        self.lot_watchers[lot_id].add(websocket)

        # Confirm subscription
        await websocket.send_json({
            "type": "subscribed",
            "lot_id": lot_id,
            "message": f"Subscribed to lot {lot_id}"
        })

    async def unsubscribe_from_lot(self, websocket: WebSocket, lot_id: str):
        """Unsubscribe a WebSocket from a specific lot"""
        if lot_id in self.lot_watchers and websocket in self.lot_watchers[lot_id]:
            self.lot_watchers[lot_id].remove(websocket)
            if not self.lot_watchers[lot_id]:
                del self.lot_watchers[lot_id]

        # Confirm unsubscription
        await websocket.send_json({
            "type": "unsubscribed",
            "lot_id": lot_id,
            "message": f"Unsubscribed from lot {lot_id}"
        })

    async def broadcast_to_lot(self, lot_id: str, message: dict):
        """Broadcast a message to all watchers of a specific lot"""
        if lot_id in self.lot_watchers:
            disconnected = set()
            for websocket in self.lot_watchers[lot_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to websocket: {e}")
                    disconnected.add(websocket)

            # Clean up disconnected sockets
            for websocket in disconnected:
                self.disconnect(websocket)

    async def send_to_user(self, user_id: UUID, message: dict):
        """Send a message to all connections of a specific user"""
        if user_id in self.user_connections:
            disconnected = set()
            for websocket in self.user_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to websocket: {e}")
                    disconnected.add(websocket)

            # Clean up disconnected sockets
            for websocket in disconnected:
                self.disconnect(websocket)

    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = set()
        for websocket in list(self.socket_users.keys()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.add(websocket)

        # Clean up disconnected sockets
        for websocket in disconnected:
            self.disconnect(websocket)


# Global connection manager instance
manager = ConnectionManager()


async def get_user_from_token(token: str) -> User:
    """Get user from JWT token"""
    try:
        user = await verify_token(token)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    lot_id: str = Query(None)
):
    """
    WebSocket endpoint for real-time bidding updates

    Query parameters:
    - token: JWT authentication token
    - lot_id: Optional lot ID to watch

    Message types from client:
    - subscribe: {"type": "subscribe", "lot_id": "123"}
    - unsubscribe: {"type": "unsubscribe", "lot_id": "123"}
    - ping: {"type": "ping"}

    Message types from server:
    - bid_placed: New bid on a lot
    - bid_update: Bid status changed
    - lot_update: Lot information changed
    - notification: User notification
    - pong: Response to ping
    """
    # Authenticate user
    try:
        user = await get_user_from_token(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Connect WebSocket
    await manager.connect(websocket, user, lot_id)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to bidding updates",
            "user_id": str(user.id)
        })

        # Listen for messages from client
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                if message_type == "subscribe":
                    lot_id = message.get("lot_id")
                    if lot_id:
                        await manager.subscribe_to_lot(websocket, lot_id)

                elif message_type == "unsubscribe":
                    lot_id = message.get("lot_id")
                    if lot_id:
                        await manager.unsubscribe_from_lot(websocket, lot_id)

                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected: user={user.id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Helper functions for sending updates (to be used from bid services)

async def notify_bid_placed(lot_id: str, bid_data: dict):
    """Notify all watchers that a new bid was placed"""
    await manager.broadcast_to_lot(lot_id, {
        "type": "bid_placed",
        "lot_id": lot_id,
        "bid": bid_data
    })


async def notify_bid_update(lot_id: str, bid_id: str, status: str):
    """Notify about bid status update"""
    await manager.broadcast_to_lot(lot_id, {
        "type": "bid_update",
        "lot_id": lot_id,
        "bid_id": bid_id,
        "status": status
    })


async def notify_lot_update(lot_id: str, update_data: dict):
    """Notify about lot information update"""
    await manager.broadcast_to_lot(lot_id, {
        "type": "lot_update",
        "lot_id": lot_id,
        "data": update_data
    })


async def notify_user(user_id: UUID, notification_data: dict):
    """Send notification to a specific user"""
    await manager.send_to_user(user_id, {
        "type": "notification",
        "data": notification_data
    })


async def broadcast_system_message(message: str):
    """Broadcast a system message to all connected users"""
    await manager.broadcast_to_all({
        "type": "system",
        "message": message
    })
