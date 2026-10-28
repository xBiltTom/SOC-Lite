"""Canal en vivo autenticado; diseñado para una sola instancia del backend."""
import asyncio
import time
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.permissions import P
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.security import Role, User
from app.services.live_events import live_events

router = APIRouter(tags=["Tiempo real"])


@router.websocket("/live")
async def live(socket: WebSocket):
    origin = socket.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await socket.close(code=1008)
        return
    await socket.accept()
    try:
        message = await asyncio.wait_for(socket.receive_json(), timeout=5)
        payload = decode_token(message.get("token", ""), "access")
        user_id = uuid.UUID(payload["sub"])
        async with SessionLocal() as db:
            result = await db.execute(
                select(User).options(selectinload(User.role).selectinload(Role.permissions))
                .where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
            )
            user = result.scalar_one_or_none()
            if user is None or not user.has_permission(P.ALERTS_READ):
                await socket.close(code=4403)
                return
        live_events.connections.add(socket)
        await socket.send_json({"type": "connected"})
        # La conexión no puede sobrevivir al token con el que se autenticó.
        remaining = max(0, payload["exp"] - time.time())
        await asyncio.wait_for(_receive_until_disconnect(socket), timeout=remaining)
    except (jwt.PyJWTError, ValueError, KeyError, TypeError, AttributeError):
        await socket.close(code=4401)
    except asyncio.TimeoutError:
        await socket.close(code=4401)
    except WebSocketDisconnect:
        pass
    finally:
        live_events.connections.discard(socket)


async def _receive_until_disconnect(socket: WebSocket) -> None:
    while True:
        await socket.receive_text()
