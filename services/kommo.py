"""Cliente ligero para interactuar con Kommo CRM."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests


class KommoClient:
    def __init__(self) -> None:
        base_url = os.getenv("KOMMO_BASE_URL", "").rstrip("/")
        if not base_url:
            raise RuntimeError("Configura KOMMO_BASE_URL en tu .env")
        self.base_url = base_url
        self.token = os.getenv("KOMMO_ACCESS_TOKEN")
        if not self.token:
            raise RuntimeError("Configura KOMMO_ACCESS_TOKEN en tu .env")
        self.pipeline_id = os.getenv("KOMMO_PIPELINE_ID")
        self.status_id_default = os.getenv("KOMMO_STATUS_ID_INICIAL")
        self.status_id_agendado = os.getenv("KOMMO_STATUS_ID_AGENDADO")
        self.field_id_empresa = os.getenv("KOMMO_FIELD_ID_EMPRESA")
        self.field_id_servicio = os.getenv("KOMMO_FIELD_ID_SERVICIO")
        self.field_id_fuente = os.getenv("KOMMO_FIELD_ID_FUENTE")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.request(method=method, url=url, headers=self._headers(), timeout=20, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Kommo respondió {response.status_code}: {response.text}")
        if not response.text:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    def find_contact_by_email(self, email: str) -> Optional[int]:
        if not email:
            return None
        response = self._request("GET", "/api/v4/contacts", params={"query": email})
        embedded = response.get("_embedded", {}) if isinstance(response, dict) else {}
        contacts = embedded.get("contacts", [])
        if contacts:
            return contacts[0].get("id")
        return None

    def create_contact(self, name: str, email: str, phone: str, empresa: Optional[str]) -> int:
        contact_data: Dict[str, Any] = {
            "name": name,
            "custom_fields_values": [
                {
                    "field_code": "EMAIL",
                    "values": [{"enum_code": "WORK", "value": email}],
                },
                {
                    "field_code": "PHONE",
                    "values": [{"enum_code": "WORK", "value": phone}],
                },
            ],
        }
        if empresa:
            contact_data["company_name"] = empresa

        payload = {"add": [contact_data]}
        response = self._request("POST", "/api/v4/contacts", json=payload)
        contact = response.get("_embedded", {}).get("contacts", [{}])[0]
        contact_id = contact.get("id")
        if not contact_id:
            raise RuntimeError("No se pudo crear el contacto en Kommo")
        return contact_id

    def find_or_create_contact(self, name: str, email: str, phone: str, empresa: Optional[str]) -> int:
        existing = self.find_contact_by_email(email)
        if existing:
            return existing
        return self.create_contact(name=name, email=email, phone=phone, empresa=empresa)

    def create_lead(self, name: str, contact_id: int, empresa: Optional[str], servicio: Optional[str], fuente: Optional[str]) -> Dict[str, Any]:
        custom_fields: list[Dict[str, Any]] = []
        if empresa and self.field_id_empresa:
            custom_fields.append({"field_id": int(self.field_id_empresa), "values": [{"value": empresa}]})
        if servicio and self.field_id_servicio:
            custom_fields.append({"field_id": int(self.field_id_servicio), "values": [{"value": servicio}]})
        if fuente and self.field_id_fuente:
            custom_fields.append({"field_id": int(self.field_id_fuente), "values": [{"value": fuente}]})

        lead_data: Dict[str, Any] = {
            "name": name,
            "pipeline_id": self.pipeline_id,
            "status_id": self.status_id_default,
            "_embedded": {"contacts": [{"id": contact_id}]},
        }
        if custom_fields:
            lead_data["custom_fields_values"] = custom_fields

        payload = {"add": [lead_data]}
        response = self._request("POST", "/api/v4/leads", json=payload)
        lead = response.get("_embedded", {}).get("leads", [{}])[0]
        lead_id = lead.get("id")
        if not lead_id:
            raise RuntimeError("No se pudo crear el lead en Kommo")
        return {"id": lead_id, **lead}

    def update_lead_status(self, lead_id: int, status_id: Optional[str] = None) -> Dict[str, Any]:
        status = status_id or self.status_id_agendado
        if not status:
            raise RuntimeError("Configura KOMMO_STATUS_ID_AGENDADO o envía status_id explícito")
        payload = {
            "update": [
                {
                    "id": lead_id,
                    "status_id": status,
                }
            ]
        }
        return self._request("PATCH", "/api/v4/leads", json=payload)
_kommo_client: Optional[KommoClient] = None


def get_kommo_client() -> KommoClient:
    global _kommo_client
    if _kommo_client is None:
        _kommo_client = KommoClient()
    return _kommo_client
