"""Cache TTL en mémoire pour les données de référence quasi-statiques
(catégories, catalogues) qui n'ont aucune route de mutation côté API —
elles ne changent qu'au redéploiement/seed, pas via une requête utilisateur.

Volontairement pas de Redis : l'hébergement cible est un process Python
unique par worker (cPanel/Passenger), donc un cache mémoire par process
suffit et évite une dépendance externe supplémentaire à déployer.
"""

import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

_DEFAULT_TTL_SECONDS = 300
_store: dict[str, tuple[float, Any]] = {}


async def cached(
    key: str,
    loader: Callable[[], Awaitable[T]],
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> T:
    """Retourne la valeur en cache si valide, sinon appelle `loader` et la stocke."""
    now = time.monotonic()
    entry = _store.get(key)
    if entry is not None and entry[0] > now:
        return entry[1]
    value = await loader()
    _store[key] = (now + ttl, value)
    return value


def invalidate(prefix: str | None = None) -> None:
    """Vide le cache. Sans préfixe, vide tout ; sinon ne retire que les clés
    qui commencent par ce préfixe (ex: "games:" après un seed des jeux)."""
    if prefix is None:
        _store.clear()
        return
    for key in [k for k in _store if k.startswith(prefix)]:
        del _store[key]
