from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.security import decode_token
from app.modules.auth.models import User
from app.modules.children.models import Child
from .manager import manager
import json

router = APIRouter()


async def _authenticate_ws(
    token: str, child_id: int, db: AsyncSession
) -> bool:
    """
    Vérifie que le token JWT est valide et que
    l'utilisateur a accès à cet enfant.
    """
    if not token:
        return False

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        return False

    # Vérifier que l'utilisateur existe
    user_result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        return False

    # Vérifier que l'enfant appartient à cet utilisateur
    child_result = await db.execute(
        select(Child).where(
            Child.id == child_id,
            Child.parent_id == user.id,
        )
    )
    child = child_result.scalar_one_or_none()
    return child is not None


@router.websocket("/ws/{child_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    child_id: int,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Point d'entrée WebSocket.

    Connexion : ws://localhost:8000/ws/{child_id}?token=<access_token>

    Événements reçus du client :
      { "type": "ping" }

    Événements envoyés au client :
      { "type": "emotion_recorded", "data": {...} }
      { "type": "routine_step_validated", "data": {...} }
      { "type": "game_score_submitted", "data": {...} }
      { "type": "connection_confirmed", "data": {...} }
    """

    # ── Authentification ──────────────────────────────────────────
    is_authenticated = await _authenticate_ws(token, child_id, db)
    if not is_authenticated:
        await websocket.close(code=4001, reason="Non autorisé")
        return

    # ── Connexion acceptée ────────────────────────────────────────
    await manager.connect(websocket, child_id)

    # Confirmer la connexion
    await manager.send_to_child(child_id, {
        "type": "connection_confirmed",
        "data": {
            "child_id": child_id,
            "message": "Connexion établie avec succès.",
            "connected_clients": len(
                manager.active_connections.get(child_id, [])
            ),
        }
    })

    try:
        # ── Boucle d'écoute ───────────────────────────────────────
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                event_type = data.get("type")

                # Répondre au ping (keepalive)
                if event_type == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": str(__import__('datetime').datetime.utcnow()),
                    }))

                # Écho pour debug
                elif event_type == "echo":
                    await websocket.send_text(json.dumps({
                        "type": "echo_response",
                        "data": data.get("data"),
                    }))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Format JSON invalide.",
                }))

    except WebSocketDisconnect:
        manager.disconnect(websocket, child_id)