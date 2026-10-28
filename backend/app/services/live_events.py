"""Notificaciones en memoria para la instancia única del laboratorio."""
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class LiveEvents:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def publish(self, event: dict) -> None:
        async def send(socket: WebSocket) -> None:
            try:
                await asyncio.wait_for(socket.send_json(event), timeout=1)
            except Exception:
                self.connections.discard(socket)

        await asyncio.gather(*(send(socket) for socket in tuple(self.connections)))


live_events = LiveEvents()
