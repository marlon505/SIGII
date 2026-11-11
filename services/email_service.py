from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import os
import smtplib

from PySide6.QtCore import QThread, Signal
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")


class EmailServiceError(Exception):
    """Se lanza cuando el envío de correo falla, con un mensaje ya listo para mostrar al usuario."""
    pass


def enviar_codigo_recuperacion(destinatario: str, codigo: str) -> None:
    if not SMTP_USER or not SMTP_APP_PASSWORD:
        raise EmailServiceError(
            "Configuración SMTP incompleta. Revisa tu archivo .env."
        )

    mensaje = MIMEMultipart()
    mensaje["From"] = SMTP_USER
    mensaje["To"] = destinatario
    mensaje["Subject"] = "SIGII - Código de recuperación de contraseña"

    cuerpo = (
        f"Tu código de verificación es: {codigo}\n\n"
        "Este código expira en 15 minutos y solo puede usarse una vez.\n"
        "Si no solicitaste este cambio, ignora este mensaje."
    )
    mensaje.attach(MIMEText(cuerpo, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(SMTP_USER, SMTP_APP_PASSWORD)
            servidor.send_message(mensaje)
    except smtplib.SMTPAuthenticationError:
        raise EmailServiceError(
            "Credenciales SMTP inválidas. Verifica SMTP_USER y SMTP_APP_PASSWORD."
        )
    except (smtplib.SMTPException, OSError):
        raise EmailServiceError(
            "No se pudo enviar el correo. Verifica tu conexión a internet."
        )

# Consolidado desde services/email_worker.py: worker asincrono de correo.


class EmailWorker(QThread):
    exito = Signal()
    error = Signal(str)

    def __init__(self, destinatario: str, codigo: str):
        super().__init__()
        self.destinatario = destinatario
        self.codigo = codigo

    def run(self):
        try:
            enviar_codigo_recuperacion(self.destinatario, self.codigo)
            self.exito.emit()
        except EmailServiceError as e:
            self.error.emit(str(e))