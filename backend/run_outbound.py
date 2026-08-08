import uuid
from dotenv import load_dotenv
load_dotenv()

from database.postgres import SessionLocal
from domain.enums import ConversationChannel, CampaignStatus, LeadSource
from domain.models.lead import Lead
from crm.campaign_repository import CampaignRepository
from outbound.campaign_engine import CampaignEngine
from outbound.sender import OutboundSender

db = SessionLocal()
try:
    lead = Lead(id=uuid.uuid4(), first_name="Marie", last_name="Lambert",
                email="marie@example.com", phone="0491234567", region="Wallonie",
                source=LeadSource.CRM_IMPORT)
    db.add(lead)
    db.flush()

    campaign_repo = CampaignRepository(db)
    campaign = campaign_repo.create(name="Campagne Wallonie", target_rules='{"region": "Wallonie"}')
    campaign_repo.set_status(campaign, CampaignStatus.RUNNING)

    engine = CampaignEngine(db)
    assigned = engine.select_and_assign_leads(campaign, limit=10)
    print(f"Leads assignes: {len(assigned)}")

    sender = OutboundSender(db)
    for lead in assigned:
        response = sender.send_opening_message(lead, campaign, ConversationChannel.WEB, external_id=str(lead.id))
        print(f"-> {lead.first_name} {lead.last_name}: {response.response_text!r}")

    db.commit()
    print("Campagne executee, leads passes a CONTACTED")
finally:
    db.close()