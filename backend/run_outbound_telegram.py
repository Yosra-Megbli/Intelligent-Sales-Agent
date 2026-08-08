"""
Example: running an outbound Telegram campaign with full delivery wiring.

Same shape as `run_outbound.py`, except:
- `OutboundSender` is built with `outbound.senders.build_default_senders()`,
  so if `TELEGRAM_BOT_TOKEN` is set in the environment (.env), the opening
  message is actually posted to Telegram's Bot API `sendMessage` - not just
  computed and recorded.
- The channel is `ConversationChannel.TELEGRAM`. Per
  `outbound/scheduler.py`'s `_resolve_external_id` docstring: Telegram
  can't be cold-DMed by phone number, only by `chat_id` of someone who
  already started a chat with the bot - this script demonstrates that with
  an explicit `external_id`, standing in for "a chat_id you already have on
  file" (e.g. from a lead that came in via the Telegram webhook first).

Run with `python run_outbound_telegram.py` after setting `TELEGRAM_BOT_TOKEN`
in `backend/.env` (see `.env.example`) and pointing `chat_id` below at a
real chat that has started your bot - otherwise this still runs end-to-end
(greeting generated, lead marked CONTACTED), it just has nothing real to
deliver to and logs a warning instead of sending.
"""

import uuid

from dotenv import load_dotenv

load_dotenv()

from database.postgres import SessionLocal
from domain.enums import CampaignStatus, ConversationChannel, LeadSource
from domain.models.lead import Lead
from crm.campaign_repository import CampaignRepository
from outbound.campaign_engine import CampaignEngine
from outbound.sender import OutboundSender
from outbound.senders import build_default_senders

# Replace with a real Telegram chat_id (e.g. your own, after messaging your
# bot once) to see this actually land in Telegram.
TELEGRAM_CHAT_ID = "123456789"

db = SessionLocal()
try:
    lead = Lead(
        id=uuid.uuid4(),
        first_name="Marie",
        last_name="Lambert",
        phone="0491234567",
        region="Wallonie",
        source=LeadSource.CRM_IMPORT,
    )
    db.add(lead)
    db.flush()

    campaign_repo = CampaignRepository(db)
    campaign = campaign_repo.create(name="Campagne Telegram Wallonie", target_rules='{"region": "Wallonie"}')
    campaign_repo.set_status(campaign, CampaignStatus.RUNNING)

    engine = CampaignEngine(db)
    assigned = engine.select_and_assign_leads(campaign, limit=10)
    print(f"Leads assignes: {len(assigned)}")

    # Full wiring: real TelegramBotAPISender.send if TELEGRAM_BOT_TOKEN is
    # configured, otherwise the same compute-only behaviour as before.
    sender = OutboundSender(db, senders=build_default_senders())
    for lead in assigned:
        response = sender.send_opening_message(
            lead, campaign, ConversationChannel.TELEGRAM, external_id=TELEGRAM_CHAT_ID
        )
        print(f"-> {lead.first_name} {lead.last_name}: {response.response_text!r}")

    db.commit()
    print("Campagne Telegram executee, leads passes a CONTACTED")
finally:
    db.close()
