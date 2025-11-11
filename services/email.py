"""Servicio sencillo para enviar correos de bienvenida vía Sendinblue."""
from __future__ import annotations

import os
from typing import Any, Dict

import requests


class EmailService:
    def __init__(self) -> None:
        self.api_key = os.getenv("SENDINBLUE_API_KEY")
        self.sender_email = os.getenv("SENDINBLUE_SENDER_EMAIL")
        self.sender_name = os.getenv("SENDINBLUE_SENDER_NAME", "Javier Virtual")
        if not all([self.api_key, self.sender_email]):
            raise RuntimeError("Configura las variables de Sendinblue en el .env")
        self.booking_url = os.getenv("BOOKING_URL", "https://cal.com")

    def _headers(self) -> Dict[str, str]:
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    def send_welcome_email(self, to_email: str, to_name: str, servicio: str | None) -> Dict[str, Any]:
        subject = "¡Gracias por contactar a CII.IA!"
        servicio_text = servicio or "nuestros servicios"
        html_content = f"""
        <h1>Hola {to_name}, soy Javier Virtual 🤖</h1>
        <p>Gracias por interesarte en {servicio_text}. Ya registramos tu información en nuestro CRM.</p>
        <p>Puedes agendar una llamada cuando prefieras en el siguiente enlace:</p>
        <p><a href=\"{self.booking_url}\">Agenda aquí</a></p>
        <p>También me pondré en contacto por teléfono y WhatsApp para avanzar más rápido.</p>
        <p>- Equipo Automatización Leads</p>
        """
        payload = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": to_email, "name": to_name}],
            "subject": subject,
            "htmlContent": html_content,
        }
        response = requests.post(
            "https://api.sendinblue.com/v3/smtp/email",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        if not response.ok:
            raise RuntimeError(f"Sendinblue error {response.status_code}: {response.text}")
        data = response.json() if response.text else {}
        data["provider"] = "sendinblue"
        return data


_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
