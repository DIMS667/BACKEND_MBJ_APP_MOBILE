"""Point d'entrée pour Phusion Passenger (cPanel/LWS).

Passenger ne sait servir que du WSGI ; FastAPI est en ASGI. On enveloppe
donc l'app avec a2wsgi. Conséquence assumée : le protocole ASGI "lifespan"
n'est pas garanti d'être déclenché par ce pont, donc l'auto-migration au
"startup" (voir app/main.py) ne doit pas être le seul mécanisme utilisé en
prod ici — lancer `alembic upgrade head` manuellement après chaque déploiement
(cf. runbook de déploiement). Pour la même raison (pas de vrai canal
bidirectionnel en WSGI), le endpoint WebSocket ne fonctionnera pas sous
Passenger — non bloquant : le frontend mobile ne l'utilise pas aujourd'hui.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from a2wsgi import ASGIMiddleware  # noqa: E402
from app.main import app as _fastapi_app  # noqa: E402

application = ASGIMiddleware(_fastapi_app)
