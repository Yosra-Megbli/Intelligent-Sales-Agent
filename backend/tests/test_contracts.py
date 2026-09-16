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


def test_contract_service_create_and_simulate_sign(db_session):
    from application.contract_service import ContractService

    lead_repo = LeadRepository(db_session)
    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="David",
        last_name="Willems",
        email="david@test.be",
        phone="0471234567",
        language="nl",
    )
    lead.has_heat_pump = True
    db_session.flush()

    service = ContractService(db_session)
    contract, pdf_bytes, yousign_res = service.create_contract_for_lead(lead.id)

    # 1. Product rule: heat_pump -> Motion
    assert contract.product == "Motion"
    assert len(pdf_bytes) > 2000
    assert lead.status == LeadStatus.CONTRACT

    # 2. Simulate signature
    signed_contract = service.simulate_signature(contract.id)
    assert signed_contract.status == ContractStatus.SIGNED
    assert signed_contract.signed_at is not None
    assert lead.status == LeadStatus.CUSTOMER


def test_yousign_hmac_webhook_verification(db_session):
    import hmac
    import hashlib
    import json
    from application.contract_service import ContractService
    from integrations.yousign import verify_yousign_webhook_signature

    secret = "super_webhook_secret_123"
    payload = {
        "event_name": "signature_request.done",
        "data": {
            "signature_request": {
                "id": "sig_req_test_999",
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # 1. Invalid signature
    assert verify_yousign_webhook_signature(raw_body, "bad_signature", secret=secret) is False

    # 2. Valid signature
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    assert verify_yousign_webhook_signature(raw_body, valid_sig, secret=secret) is True
    assert verify_yousign_webhook_signature(raw_body, f"sha256={valid_sig}", secret=secret) is True

    # 3. Process webhook event
    lead_repo = LeadRepository(db_session)
    contract_repo = ContractRepository(db_session)
    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="Elena",
        last_name="Vandamme",
        email="elena@test.be",
        language="en",
    )
    lead.status = LeadStatus.CONTRACT
    contract = contract_repo.create(
        lead_id=lead.id,
        product="Flexy",
        status=ContractStatus.SENT,
        yousign_signature_request_id="sig_req_test_999",
    )
    db_session.flush()

    service = ContractService(db_session)
    res = service.handle_yousign_webhook(
        payload_bytes=raw_body,
        signature_header=valid_sig,
        parsed_payload=payload,
    )
    assert res.get("status") == "success"
    assert contract.status == ContractStatus.SIGNED
    assert lead.status == LeadStatus.CUSTOMER


def test_contract_api_endpoints():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from api.main import app
    from api.routes import get_db_session
    from database.postgres import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True)

    def override_get_db_session():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    # Seed lead
    db = TestingSession()
    lead_repo = LeadRepository(db)
    lead = lead_repo.create(
        source=LeadSource.WEBSITE,
        first_name="Thomas",
        last_name="Bernard",
        email="thomas@test.be",
        phone="0489998877",
    )
    db.commit()
    lead_id_str = str(lead.id)
    db.close()

    client = TestClient(app)
    headers = {"X-API-Key": "test-api-key"}

    # 1. POST /api/contracts
    post_res = client.post("/api/contracts", json={"lead_id": lead_id_str}, headers=headers)
    assert post_res.status_code == 201
    contract_data = post_res.json()
    contract_id = contract_data["id"]
    assert contract_data["product"] == "Flexy"

    # 2. GET /api/contracts
    list_res = client.get("/api/contracts", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 3. GET /api/contracts/{id}
    detail_res = client.get(f"/api/contracts/{contract_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == contract_id

    # 4. GET /api/contracts/{id}/pdf
    pdf_res = client.get(f"/api/contracts/{contract_id}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

    # 5. POST /api/contracts/{id}/simulate-sign
    sign_res = client.post(f"/api/contracts/{contract_id}/simulate-sign", headers=headers)
    assert sign_res.status_code == 200
    assert sign_res.json()["status"] == "SIGNED"

    app.dependency_overrides.clear()


