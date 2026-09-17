"""
Contract Service — Sophie (Ecofix).

Orchestrates contract lifecycle operations (Sprint 3 / Package C):
- Deterministic contract draft & PDF specimen creation
- Yousign v3 signature procedure initiation
- HMAC-verified webhook processing (SENT -> SIGNED)
- Transition from LeadStatus.CONTRACT -> LeadStatus.CUSTOMER
- Friends with Benefits trilingual confirmation on contract signature
- 14-day legal withdrawal handling
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from contracts.pdf_generator import generate_contract_pdf
from conversation_engine import rules
from crm.activity_repository import ActivityRepository
from crm.contract_repository import ContractRepository
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import (
    ActivityType,
    ContractStatus,
    ConversationChannel,
    ConversationState,
    LeadStatus,
    MessageRole,
)
from domain.models.contract import Contract
from domain.models.lead import Lead
from integrations.yousign import (
    YousignClient,
    verify_yousign_webhook_signature,
)

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/contracts")

CONFIRMATION_SIGNED_FR = (
    "Félicitations et bienvenue chez Ecofix ! Votre contrat a été validé et signé. "
    "Vous bénéficiez également de notre programme 'Friends with Benefits' : "
    "recevez 5 €/mois de réduction par ami parrainé qui souscrit un contrat actif !"
)

CONFIRMATION_SIGNED_NL = (
    "Gefeliciteerd en welkom bij Ecofix! Uw contract is gevalideerd en ondertekend. "
    "U geniet ook van ons 'Friends with Benefits'-programma: "
    "ontvang € 5/maand korting per doorverwezen vriend met een actief contract!"
)

CONFIRMATION_SIGNED_EN = (
    "Congratulations and welcome to Ecofix! Your contract has been validated and signed. "
    "You also benefit from our 'Friends with Benefits' program: "
    "receive €5/month discount per referred friend with an active contract!"
)


class ContractService:
    def __init__(self, db: Session, yousign_client: Optional[YousignClient] = None):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.contract_repo = ContractRepository(db)
        self.conversation_repo = ConversationRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.yousign = yousign_client or YousignClient()

    def create_contract_for_lead(self, lead_id: UUID | str) -> tuple[Contract, bytes, dict[str, Any]]:
        """Create and draft contract for lead, generate PDF and initiate Yousign."""
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead with id={lead_id} not found")

        # 1. Product rule: has_ev/heat_pump/battery -> Motion else Flexy
        product = rules.select_contract_product(lead)

        # 2. Persist initial Contract entity
        contract = self.contract_repo.create(
            lead_id=lead.id,
            product=product,
            status=ContractStatus.DRAFT,
        )

        # 3. Generate PDF specimen
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = STORAGE_DIR / f"contract_{contract.id}.pdf"
        pdf_bytes = generate_contract_pdf(lead, contract, output_path=str(pdf_path))
        self.contract_repo.update_pdf_path(contract, str(pdf_path))

        # 4. Initiate Yousign signature procedure
        yousign_res = self.yousign.initiate_signature_procedure(lead, contract, pdf_bytes)
        sig_req_id = yousign_res.get("signature_request_id")
        doc_id = yousign_res.get("document_id")

        if yousign_res.get("configured") and yousign_res.get("status") == "sent":
            self.contract_repo.update_yousign_info(
                contract,
                signature_request_id=sig_req_id,
                document_id=doc_id,
                status=ContractStatus.SENT,
            )
            self.activity_repo.log(
                lead.id,
                ActivityType.CONTRACT_SENT,
                details=f"Contract {contract.id} ({product}) sent for signature via Yousign",
            )
        else:
            self.contract_repo.update_yousign_info(
                contract,
                signature_request_id=sig_req_id,
                document_id=doc_id,
                status=ContractStatus.DRAFT,
            )
            self.activity_repo.log(
                lead.id,
                ActivityType.CONTRACT_DRAFTED,
                details=f"Contract {contract.id} ({product}) drafted (PDF ready)",
            )

        # 5. Lead status transition: dead state CONTRACT is now real!
        if lead.status != LeadStatus.CONTRACT and lead.status != LeadStatus.CUSTOMER:
            self.lead_repo.set_status(lead, LeadStatus.CONTRACT)
            self.activity_repo.log(
                lead.id,
                ActivityType.STATUS_CHANGED,
                details=f"{lead.status.value} -> CONTRACT",
            )

        self.db.commit()
        return contract, pdf_bytes, yousign_res

    def get_contract_pdf(self, contract_id: UUID | str) -> tuple[Contract, bytes]:
        """Fetch or regenerate the PDF bytes for a contract."""
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        if contract.pdf_path and Path(contract.pdf_path).exists():
            pdf_bytes = Path(contract.pdf_path).read_bytes()
            return contract, pdf_bytes

        # Regenerate if file missing
        lead = self.lead_repo.get_by_id(contract.lead_id)
        if not lead:
            raise ValueError(f"Lead {contract.lead_id} not found for contract {contract_id}")

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = STORAGE_DIR / f"contract_{contract.id}.pdf"
        pdf_bytes = generate_contract_pdf(lead, contract, output_path=str(pdf_path))
        self.contract_repo.update_pdf_path(contract, str(pdf_path))
        self.db.commit()
        return contract, pdf_bytes

    def handle_yousign_webhook(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str],
        parsed_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify HMAC signature and process Yousign event (signature_request.done)."""
        # 1. HMAC verification
        if not verify_yousign_webhook_signature(payload_bytes, signature_header):
            logger.warning("Invalid Yousign webhook signature")
            return {"status": "unauthorized", "error": "Invalid HMAC signature"}

        event_name = parsed_payload.get("event_name") or parsed_payload.get("event") or ""
        sr_data = (
            parsed_payload.get("data", {}).get("signature_request", {})
            or parsed_payload.get("signature_request", {})
            or parsed_payload.get("data", {})
        )
        sig_req_id = sr_data.get("id") or parsed_payload.get("signature_request_id")

        if not sig_req_id:
            return {"status": "ignored", "reason": "No signature_request_id found"}

        contract = self.contract_repo.get_by_yousign_signature_request_id(sig_req_id)
        if not contract:
            logger.info("No contract matching Yousign signature_request_id=%s", sig_req_id)
            return {"status": "ignored", "reason": "Contract not found"}

        # 2. Handle completed signature
        if any(done_token in event_name.lower() for done_token in ("done", "completed", "signed")):
            if contract.status != ContractStatus.SIGNED:
                self.contract_repo.set_status(contract, ContractStatus.SIGNED, signed_at=datetime.utcnow())
                lead = self.lead_repo.get_by_id(contract.lead_id)

                if lead:
                    # Activate dead state CUSTOMER!
                    self.lead_repo.set_status(lead, LeadStatus.CUSTOMER)
                    self.activity_repo.log(
                        lead.id,
                        ActivityType.STATUS_CHANGED,
                        details="CONTRACT -> CUSTOMER",
                    )
                    self.activity_repo.log(
                        lead.id,
                        ActivityType.CONTRACT_SIGNED,
                        details=f"Contract {contract.id} signed via Yousign",
                    )

                    # Send trilingual confirmation with Friends with Benefits mention
                    self._send_signed_confirmation(lead)

                self.db.commit()
                return {"status": "success", "contract_id": str(contract.id), "lead_status": "CUSTOMER"}

        return {"status": "processed", "event": event_name}

    def simulate_signature(self, contract_id: UUID | str) -> Contract:
        """Sandbox trigger: simulate signature transition SENT -> SIGNED."""
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        self.contract_repo.set_status(contract, ContractStatus.SIGNED, signed_at=datetime.utcnow())
        lead = self.lead_repo.get_by_id(contract.lead_id)

        if lead:
            self.lead_repo.set_status(lead, LeadStatus.CUSTOMER)
            self.activity_repo.log(
                lead.id,
                ActivityType.STATUS_CHANGED,
                details="CONTRACT -> CUSTOMER",
            )
            self.activity_repo.log(
                lead.id,
                ActivityType.CONTRACT_SIGNED,
                details=f"Contract {contract.id} signed in sandbox simulation",
            )
            self._send_signed_confirmation(lead)

            # Regenerate PDF with the official certified signed stamp
            try:
                STORAGE_DIR.mkdir(parents=True, exist_ok=True)
                pdf_path = STORAGE_DIR / f"contract_{contract.id}.pdf"
                generate_contract_pdf(lead, contract, output_path=str(pdf_path))
                self.contract_repo.update_pdf_path(contract, str(pdf_path))
            except Exception as exc:
                logger.warning("Could not regenerate signed contract PDF: %s", exc)

        self.db.commit()
        return contract

    def _send_signed_confirmation(self, lead: Lead) -> None:
        """Add trilingual confirmation message with Friends with Benefits mention."""
        lang = (getattr(lead, "language", "fr") or "fr").lower()
        if lang == "nl":
            msg_text = CONFIRMATION_SIGNED_NL
        elif lang == "en":
            msg_text = CONFIRMATION_SIGNED_EN
        else:
            msg_text = CONFIRMATION_SIGNED_FR

        # Look up most recent conversation for this lead
        conv = self.conversation_repo.get_latest_for_lead(lead.id)
        if conv:
            self.conversation_repo.add_message(conv, MessageRole.ASSISTANT, msg_text)
            self.conversation_repo.transition_state(conv, ConversationState.CLOSED)

