from fastapi import WebSocket
from typing import Dict, List
import json
from datetime import datetime


class ConnectionManager:
    """
    Gère toutes les connexions WebSocket actives.
    Clé : child_id → liste des connexions (parent peut avoir plusieurs onglets)
    """

    def __init__(self):
        # child_id → liste de WebSockets connectés
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, child_id: int) -> None:
        """Accepte et enregistre une nouvelle connexion."""
        await websocket.accept()
        if child_id not in self.active_connections:
            self.active_connections[child_id] = []
        self.active_connections[child_id].append(websocket)
        print(f"🔌 WS connecté — child_id={child_id} "
              f"({len(self.active_connections[child_id])} connexion(s))")

    def disconnect(self, websocket: WebSocket, child_id: int) -> None:
        """Supprime une connexion fermée."""
        if child_id in self.active_connections:
            self.active_connections[child_id].remove(websocket)
            if not self.active_connections[child_id]:
                del self.active_connections[child_id]
        print(f"🔌 WS déconnecté — child_id={child_id}")

    async def send_to_child(self, child_id: int, event: dict) -> None:
        """
        Envoie un événement à toutes les connexions d'un enfant.
        Utilisé quand l'enfant fait une action.
        """
        if child_id not in self.active_connections:
            return

        # Ajouter timestamp automatiquement
        event["timestamp"] = str(datetime.utcnow())

        message = json.dumps(event, ensure_ascii=False)
        dead_connections = []

        for websocket in self.active_connections[child_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.append(websocket)

        # Nettoyer les connexions mortes
        for dead in dead_connections:
            self.active_connections[child_id].remove(dead)

    async def broadcast(self, event: dict) -> None:
        """Envoie un événement à TOUTES les connexions actives."""
        event["timestamp"] = str(datetime.utcnow())
        message = json.dumps(event, ensure_ascii=False)

        for child_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    pass

    def is_connected(self, child_id: int) -> bool:
        """Vérifie si un enfant a des connexions actives."""
        return (
            child_id in self.active_connections
            and len(self.active_connections[child_id]) > 0
        )

    def get_connected_children(self) -> list:
        """Retourne la liste des child_ids connectés."""
        return list(self.active_connections.keys())


# Instance globale — partagée dans toute l'app
manager = ConnectionManager()