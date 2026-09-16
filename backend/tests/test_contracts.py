import uuid
from datetime import datetime
import pytest

from contracts.pdf_generator import generate_contract_pdf, get_grid_operator
from conversation_engine.compliance import is_withdrawal_intent
from crm.contract_repository import ContractRepository
from crm.lead_repository import LeadRepository
from domain.enums import ActivityType, ContractStatus, ConversationChannel, ConversationState, LeadSource, LeadStatus
from domain.models.contract import Contract
from application.conversation_service import ConversationRequest, ConversationService
from ai.providers.interface import LLMProvider, LLMResponse, LLMMessage


class FakeProvider(LLMProvider):
    def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        return LLMResponse(content="{}")



def test_contract_crud(db_session):
    lead_repo = LeadRepository(db_session)
    contract_repo = ContractRepository(db_session)

    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="Sophie",
        last_name="Martin",
        email="sophie.martin@test.be",
        phone="0488112233",
    )

    # 1. Create contract
    contract = contract_repo.create(
        lead_id=lead.id,
        product="Flexy",
        status=ContractStatus.DRAFT,
        pdf_path="/tmp/specimen.pdf",
    )
    assert contract.id is not None
    assert contract.lead_id == lead.id
    assert contract.product == "Flexy"
    assert contract.status == ContractStatus.DRAFT
    assert contract.pdf_path == "/tmp/specimen.pdf"

    # 2. Get by ID and latest by lead ID
    fetched = contract_repo.get_by_id(contract.id)
    assert fetched is not None
    assert fetched.id == contract.id

    latest = contract_repo.get_latest_by_lead_id(lead.id)
    assert latest is not None
    assert latest.id == contract.id

    # 3. Update Yousign info
    contract_repo.update_yousign_info(
        contract,
        signature_request_id="req_123456",
        document_id="doc_abcdef",
        status=ContractStatus.SENT,
    )
    assert contract.yousign_signature_request_id == "req_123456"
    assert contract.yousign_document_id == "doc_abcdef"
    assert contract.status == ContractStatus.SENT

    # 4. Lookup by signature request ID
    by_req = contract_repo.get_by_yousign_signature_request_id("req_123456")
    assert by_req is not None
    assert by_req.id == contract.id

    # 5. Set status to SIGNED
    contract_repo.set_status(contract, ContractStatus.SIGNED)
    assert contract.status == ContractStatus.SIGNED
    assert contract.signed_at is not None

    # 6. Count signed
    assert contract_repo.count_signed() >= 1
    assert contract_repo.count_total() >= 1

    # 7. Set status to WITHDRAWN
    contract_repo.set_status(contract, ContractStatus.WITHDRAWN)
    assert contract.status == ContractStatus.WITHDRAWN
    assert contract.withdrawn_at is not None


def test_grid_operator_routing():
    # Flanders
    assert "Fluvius" in get_grid_operator("Flandre")
    assert "Fluvius" in get_grid_operator("Gent")
    assert "Fluvius" in get_grid_operator("Antwerpen")

    # Wallonia
    assert "ORES" in get_grid_operator("Wallonie")
    assert "ORES" in get_grid_operator("Namur")
    assert "ORES" in get_grid_operator("Liège")


def test_generate_contract_pdf(db_session, tmp_path):
    lead_repo = LeadRepository(db_session)
    contract_repo = ContractRepository(db_session)

    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="Marc",
        last_name="Peeters",
        email="marc.peeters@gmail.com",
        phone="0478123456",
        language="fr",
    )
    lead.region = "Wallonie"
    lead.city = "Namur"
    lead.ean = "541448911001234567"
    lead.date_of_birth = "12/04/1988"
    lead.current_supplier = "Luminus"
    lead.has_ev = True
    db_session.flush()

    contract = contract_repo.create(
        lead_id=lead.id,
        product="Motion",
        status=ContractStatus.DRAFT,
    )

    pdf_file = tmp_path / "contract_specimen.pdf"
    pdf_bytes = generate_contract_pdf(lead, contract, output_path=str(pdf_file))

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 2000
    assert pdf_file.exists()
    assert pdf_file.stat().st_size == len(pdf_bytes)


def test_withdrawal_intent_detection():
    assert is_withdrawal_intent("JE RENONCE") is True
    assert is_withdrawal_intent("Je renonce a mon contrat") is True
    assert is_withdrawal_intent("Ik herroep mijn contract") is True
    assert is_withdrawal_intent("I withdraw from the agreement") is True
    assert is_withdrawal_intent("Je souhaite faire valoir mon droit de retractation") is True
    assert is_withdrawal_intent("Bonjour, quel est le prix du kWh ?") is False
    assert is_withdrawal_intent("Oui, je confirme") is False


def test_withdrawal_conversation_flow(db_session):
    lead_repo = LeadRepository(db_session)
    contract_repo = ContractRepository(db_session)

    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="Alice",
        last_name="Lambert",
        email="alice@test.be",
        phone="0499112233",
        language="fr",
    )
    lead.status = LeadStatus.CONTRACT
    contract = contract_repo.create(
        lead_id=lead.id,
        product="Flexy",
        status=ContractStatus.SENT,
    )
    db_session.flush()

    service = ConversationService(db_session, provider=FakeProvider())
    _, conv = service.start_conversation(
        channel=ConversationChannel.WEB,
        email=lead.email,
        phone=lead.phone,
    )


    reply = service.handle_message(
        ConversationRequest(conversation_id=conv.id, text="Je renonce")
    )

    assert reply.state == ConversationState.CLOSED.value
    assert "rétractation" in reply.response_text.lower() or "droit légal" in reply.response_text.lower()

    # Verify contract marked WITHDRAWN
    updated_contract = contract_repo.get_by_id(contract.id)
    assert updated_contract.status == ContractStatus.WITHDRAWN
    assert updated_contract.withdrawn_at is not None

    # Verify lead status updated to CLOSED
    updated_lead = lead_repo.get_by_id(lead.id)
    assert updated_lead.status == LeadStatus.CLOSED
