"""Servicios de llamada y mensajería utilizando Twilio."""
from __future__ import annotations

import os
import re
from typing import Any, Dict

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse


SUCCESS_STATUSES = {"queued", "ringing", "in-progress", "completed"}


class TwilioService:
    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.voice_caller = os.getenv("TWILIO_CALLER_ID")
        self.whatsapp_sender = os.getenv("TWILIO_WHATSAPP_SENDER")
        self.sms_sender = os.getenv("TWILIO_SMS_SENDER")
        self.default_country_code = os.getenv("DEFAULT_COUNTRY_CODE", "+52")
        if not all([self.account_sid, self.auth_token, self.voice_caller]):
            raise RuntimeError("Configura las credenciales de Twilio en el .env")
        self.client = Client(self.account_sid, self.auth_token)

    def _format_number(self, number: str) -> str:
        digits = re.sub(r"[^0-9+]", "", number or "")
        if digits.startswith("+"):
            return digits
        return f"{self.default_country_code}{digits}"

    def trigger_intro_call(self, to_number: str, lead_name: str) -> Dict[str, Any]:
        voice_response = VoiceResponse()
        voice_response.say(
            f"Hola {lead_name}, te habla Javier Virtual del C I I A. "
            "Confirmamos que recibimos tu solicitud y queremos ayudarte a avanzar. ",
            voice="Polly.Miguel",
            language="es-MX",
        )
        voice_response.pause(length=1)
        voice_response.say(
            "Si deseas agendar ahora, revisa el enlace que te enviamos por correo o WhatsApp. ¡Gracias!",
            voice="Polly.Miguel",
            language="es-MX",
        )
        try:
            call = self.client.calls.create(
                to=self._format_number(to_number),
                from_=self.voice_caller,
                twiml=str(voice_response),
            )
        except TwilioRestException as exc:  # pragma: no cover - depende de Twilio
            return {"status": "failed", "error": str(exc)}
        return {"sid": call.sid, "status": call.status}

    def call_successful(self, call_response: Dict[str, Any]) -> bool:
        return bool(call_response) and call_response.get("status") in SUCCESS_STATUSES

    def send_followup_message(self, to_number: str, lead_name: str) -> Dict[str, Any]:
        normalized = self._format_number(to_number)
        body = (
            f"Hola {lead_name}, soy Javier Virtual del CII.IA. "
            "Intenté llamarte y quiero ayudarte a agendar una sesión. "
            "Puedes reservar aquí: {}"
        ).format(os.getenv("BOOKING_URL", "https://cal.com"))

        if self.whatsapp_sender:
            try:
                msg = self.client.messages.create(
                    from_=f"whatsapp:{self.whatsapp_sender}",
                    to=f"whatsapp:{normalized}",
                    body=body,
                )
                return {"sid": msg.sid, "channel": "whatsapp"}
            except TwilioRestException as exc:  # pragma: no cover
                if not self.sms_sender:
                    raise
                error = exc
        else:
            error = None

        if not self.sms_sender:
            raise RuntimeError("Configura TWILIO_SMS_SENDER para enviar SMS de respaldo")

        try:
            msg = self.client.messages.create(
                from_=self.sms_sender,
                to=normalized,
                body=body,
            )
        except TwilioRestException as exc:  # pragma: no cover
            raise RuntimeError(str(exc)) from exc

        result = {"sid": msg.sid, "channel": "sms"}
        if error:
            result["fallback_reason"] = str(error)
        return result


_twilio_service: TwilioService | None = None


def get_twilio_service() -> TwilioService:
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service
