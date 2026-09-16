"""
Yousign v3 Integration Client — Sophie (Ecofix).

Provides integration with Yousign electronic signature v3 API:
- Signature request creation & document upload
- Signer assignment and ceremony activation
- HMAC SHA-256 webhook signature verification
- Graceful degradation when YOUSIGN_API_KEY is unset (stops cleanly at PDF,
  returns honest status without crashing)
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
from typing import Any, Optional

import httpx


from domain.models.contract import Contract
from domain.models.lead import Lead

logger = logging.getLogger(__name__)


def get_yousign_env() -> str:
    return os.getenv("YOUSIGN_ENV", "sandbox").strip().lower()


def get_yousign_api_key() -> Optional[str]:
    key = os.getenv("YOUSIGN_API_KEY")
    return key.strip() if key else None


def get_yousign_webhook_secret() -> Optional[str]:
    sec = os.getenv("YOUSIGN_WEBHOOK_SECRET")
    return sec.strip() if sec else None


def is_yousign_configured() -> bool:
    return bool(get_yousign_api_key())


def get_yousign_base_url() -> str:
    env = get_yousign_env()
    if env == "production":
        return "https://api.yousign.app/v3"
    return "https://api-sandbox.yousign.app/v3"


def verify_yousign_webhook_signature(
    payload_bytes: bytes,
    signature_header: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """Verify incoming Yousign webhook HMAC SHA-256 signature.

    If secret is configured, header must be present and match.
    If secret is not configured and not in production, returns True for local dev.
    """
    secret_key = secret or get_yousign_webhook_secret()
    if not secret_key:
        if get_yousign_env() == "production":
            logger.error("Yousign webhook secret not configured in production.")
            return False
        return True

    if not signature_header:
        logger.warning("Missing Yousign signature header.")
        return False

    raw_header = signature_header.strip()
    if raw_header.startswith("sha256="):
        raw_header = raw_header[7:]

    computed = hmac.new(
        secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed.lower(), raw_header.lower())


class YousignClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or get_yousign_api_key()
        self.base_url = (base_url or get_yousign_base_url()).rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def initiate_signature_procedure(
        self,
        lead: Lead,
        contract: Contract,
        pdf_bytes: bytes,
    ) -> dict[str, Any]:
        """Initiate signature request in Yousign v3 or degrade gracefully."""
        if not self.is_configured:
            logger.info("Yousign API key not configured — using sandbox simulation mode.")
            simulated_id = f"sim_{contract.id.hex[:12]}"
            return {
                "configured": False,
                "status": "simulated",
                "signature_request_id": simulated_id,
                "document_id": f"doc_{contract.id.hex[:8]}",
                "label": "Yousign non configuré — mode simulation / PDF local",
                "signature_link": None,
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        try:
            # 1. Create Signature Request
            sr_resp = httpx.post(
                f"{self.base_url}/signature_requests",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "name": f"Contrat Ecofix {contract.product} - {lead.first_name} {lead.last_name}",
                    "delivery_mode": "email",
                    "timezone": "Europe/Brussels",
                },
                timeout=10,
            )
            sr_resp.raise_for_status()
            sr_data = sr_resp.json()
            sig_request_id = sr_data["id"]

            # 2. Upload Document
            files = {
                "file": (
                    f"contrat_ecofix_{contract.product.lower()}.pdf",
                    pdf_bytes,
                    "application/pdf",
                ),
            }
            data = {"nature": "signable_document"}
            doc_resp = httpx.post(
                f"{self.base_url}/signature_requests/{sig_request_id}/documents",
                headers=headers,
                data=data,
                files=files,
                timeout=15,
            )
            doc_resp.raise_for_status()
            doc_id = doc_resp.json()["id"]

            # 3. Add Signer
            signer_payload = {
                "info": {
                    "first_name": lead.first_name or "Client",
                    "last_name": lead.last_name or "Ecofix",
                    "email": lead.email or "client@example.be",
                    "phone_number": lead.phone or "+32470123456",
                    "locale": getattr(lead, "language", "fr") or "fr",
                },
                "fields": [
                    {
                        "document_id": doc_id,
                        "type": "signature",
                        "page": 1,
                        "x": 350,
                        "y": 680,
                        "width": 180,
                        "height": 50,
                    }
                ],
                "signature_level": "electronic_signature",
            }
            signer_resp = httpx.post(
                f"{self.base_url}/signature_requests/{sig_request_id}/signers",
                headers={**headers, "Content-Type": "application/json"},
                json=signer_payload,
                timeout=10,
            )
            signer_resp.raise_for_status()
            signer_data = signer_resp.json()
            sig_link = signer_data.get("signature_link")

            # 4. Activate Signature Request
            httpx.post(
                f"{self.base_url}/signature_requests/{sig_request_id}/activate",
                headers=headers,
                timeout=10,
            )


            return {
                "configured": True,
                "status": "sent",
                "signature_request_id": sig_request_id,
                "document_id": doc_id,
                "signature_link": sig_link,
                "label": "Envoyé via Yousign Sandbox",
            }

        except Exception as exc:
            logger.warning("Yousign API call failed (%s), falling back to local draft.", exc)
            return {
                "configured": True,
                "status": "fallback_draft",
                "signature_request_id": f"fallback_{contract.id.hex[:12]}",
                "document_id": None,
                "label": f"Erreur Yousign API ({exc}) — conservé en PDF local",
                "signature_link": None,
            }
