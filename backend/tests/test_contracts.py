import uuid
from datetime import datetime
import pytest

from crm.contract_repository import ContractRepository
from crm.lead_repository import LeadRepository
from domain.enums import ContractStatus, LeadSource, LeadStatus
from domain.models.contract import Contract


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
