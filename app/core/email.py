import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi.concurrency import run_in_threadpool

from app.config import settings


def _send_sync(to_email: str, subject: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], message.as_string())


async def send_email(to_email: str, subject: str, html_body: str) -> None:
    """Envoie un email via le relais SMTP configuré.

    `smtplib` est synchrone/bloquant : on le pousse dans le threadpool pour
    ne pas geler la boucle asyncio le temps de la connexion SMTP.
    """
    if not settings.SMTP_HOST:
        raise RuntimeError(
            "Envoi d'email impossible : SMTP_HOST n'est pas configuré dans .env."
        )
    await run_in_threadpool(_send_sync, to_email, subject, html_body)
