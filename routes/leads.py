"""Rutas principales para recepción de leads y webhooks."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from services.email import get_email_service
from services.kommo import get_kommo_client
from services.logger import log_action
from services.twilio import get_twilio_service

leads_bp = Blueprint("leads", __name__)
CALCOM_SECRET = os.getenv("CALCOM_WEBHOOK_SECRET")

REQUIRED_FIELDS = ["nombre", "email", "telefono", "empresa", "servicio", "fuente"]


def _validate_payload(payload: Dict[str, Any], required_fields: List[str]) -> List[str]:
    missing = []
    for field in required_fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


@leads_bp.route("/lead", methods=["POST"])
def create_lead():
    payload = request.get_json(silent=True) or {}
    missing = _validate_payload(payload, REQUIRED_FIELDS)
    if missing:
        return (
            jsonify({"ok": False, "error": f"Campos requeridos faltantes: {', '.join(missing)}"}),
            400,
        )

    try:
        kommo_client = get_kommo_client()
        # Guardamos contacto y lead en Kommo antes de lanzar las acciones
        contact_id = kommo_client.find_or_create_contact(
            name=payload["nombre"],
            email=payload["email"],
            phone=payload["telefono"],
            empresa=payload.get("empresa"),
        )
        lead = kommo_client.create_lead(
            name=f"{payload['servicio']} - {payload['nombre']}",
            contact_id=contact_id,
            empresa=payload.get("empresa"),
            servicio=payload.get("servicio"),
            fuente=payload.get("fuente"),
        )
        lead_id = lead.get("id") if isinstance(lead, dict) else lead
        log_action("kommo", {
            "action": "lead_created",
            "lead_id": lead_id,
            "payload": payload,
        })

        email_service = get_email_service()
        email_result = email_service.send_welcome_email(
            to_email=payload["email"],
            to_name=payload["nombre"],
            servicio=payload.get("servicio"),
        )
        log_action("email", {"lead_id": lead_id, "provider": email_result.get("provider", "sendinblue")})

        twilio_service = get_twilio_service()
        # Disparamos llamada inmediata
        call_response = twilio_service.trigger_intro_call(
            to_number=payload["telefono"],
            lead_name=payload["nombre"],
        )
        log_action("call", {"lead_id": lead_id, "status": call_response.get("status")})

        if not twilio_service.call_successful(call_response):
            # Si la llamada no se completa, usamos WhatsApp/SMS
            message_response = twilio_service.send_followup_message(
                to_number=payload["telefono"],
                lead_name=payload["nombre"],
            )
            log_action("message", {"lead_id": lead_id, "sid": message_response.get("sid")})

        return jsonify({"ok": True, "lead_id": lead_id})
    except Exception as exc:  # pragma: no cover - errores críticos
        log_action("error", {"message": str(exc)})
        return jsonify({"ok": False, "error": str(exc)}), 500


@leads_bp.route("/calcom", methods=["POST"])
def calcom_webhook():
    payload = request.get_json(silent=True) or {}
    event_type = payload.get("event") or payload.get("type")

    if event_type != "BOOKING_CREATED":
        return jsonify({"ok": True, "message": "Evento ignorado"})

    if CALCOM_SECRET:
        incoming_secret = request.headers.get("x-webhook-secret")
        if incoming_secret != CALCOM_SECRET:
            return jsonify({"ok": False, "error": "Webhook no autorizado"}), 401

    metadata = payload.get("payload", {}).get("metadata", {})
    lead_id = metadata.get("lead_id") or payload.get("lead_id")
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id ausente en el webhook"}), 400

    try:
        kommo_client = get_kommo_client()
        kommo_client.update_lead_status(lead_id)
        log_action("kommo", {"action": "lead_agendado", "lead_id": lead_id})
        return jsonify({"ok": True})
    except Exception as exc:  # pragma: no cover
        log_action("error", {"context": "calcom_webhook", "message": str(exc)})
        return jsonify({"ok": False, "error": str(exc)}), 500
