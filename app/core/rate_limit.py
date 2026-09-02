from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """Adresse IP réelle du client.

    L'app tourne derrière le reverse proxy Apache de l'hébergeur (LWS,
    cPanel/Passenger) : `request.client.host` y vaudrait systématiquement
    l'IP du proxy, pas celle de l'appelant. On lit donc `X-Forwarded-For`
    en priorité (posé par le proxy, son premier élément est le client
    d'origine), avec repli sur l'adresse directe pour les tests locaux.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)
