"""
Voice routes.

Thin HTTP wrapper around the Application layer - same discipline as
`api/campaign_routes.py` around `CampaignService`: this module never
imports a repository, `OutboundVoiceSender`, `VoiceSessionManager`, or a
`TelephonyProvider` implementation directly, only `VoiceOutboundService`/
`VoiceInboundService` and the schemas that serialize what they return.
Enforced by `tests/test_architecture_boundaries.py`.

Two routes:

- `POST /api/voice/outbound-calls` places an actual outbound call via the
  configured `TelephonyProvider` when Twilio Voice credentials are set, and
  returns a clear 503 otherwise - guarded by `require_api_key` like every
  other write-triggering endpoint in this API.
- `POST /api/voice/twiml` is the URL `VoiceOutboundService` hands Twilio as
  the call's answer webhook (and as every subsequent `<Gather>`'s own
  `action`). Delegates to `VoiceInboundService`, which runs the real
  `VoiceSessionManager`/`ConversationService` pipeline and returns TwiML.
  Guarded by `verify_twilio_signature` + `enforce_rate_limit`, the exact
  same pair `api/routes.py`'s WhatsApp webhook uses (not `require_api_key`
  - Twilio's own servers are the caller here, not our frontend, same
  reasoning as `verify_telegram_secret` for Telegram).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from api.dependencies import (
    enforce_rate_limit,
    get_llm_provider,
    get_telephony_provider,
    require_api_key,
    verify_twilio_signature,
)
from api.routes import get_db_session
from api.voice_schemas import InitiateOutboundCallRequest, InitiateOutboundCallResponse
from application.voice_inbound_service import VoiceInboundService
from application.voice_outbound_service import (
    CampaignNotFoundError,
    LeadNotFoundError,
    VoiceOutboundNotConfiguredError,
    VoiceOutboundService,
)
from channels.voice.providers.telephony_interface import TelephonyError

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post(
    "/outbound-calls",
    response_model=InitiateOutboundCallResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def initiate_outbound_call(
    payload: InitiateOutboundCallRequest,
    db: Session = Depends(get_db_session),
    telephony_provider=Depends(get_telephony_provider),
) -> InitiateOutboundCallResponse:
    service = VoiceOutboundService(db, telephony_provider=telephony_provider)
    try:
        outcome = service.initiate_outbound_call(payload.lead_id, payload.campaign_id)
    except (LeadNotFoundError, CampaignNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except VoiceOutboundNotConfiguredError as exc:
        # 503, not 500: this isn't a bug, it's an intentionally-degraded
        # deployment (see get_telephony_provider's docstring) - the caller
        # can fix it by setting the Twilio Voice env vars, nothing here
        # needs a code change.
        raise HTTPException(status_code=503, detail=str(exc))
    except TelephonyError as exc:
        # Provider-side failure (bad number, Twilio outage/auth error...) -
        # 502 Bad Gateway: we're a valid request, the upstream telephony
        # provider is what failed.
        raise HTTPException(status_code=502, detail=str(exc))

    return InitiateOutboundCallResponse(
        lead_id=outcome.lead_id,
        campaign_id=outcome.campaign_id,
        provider_call_id=outcome.provider_call_id,
        status=outcome.status,
    )


@router.post("/twiml", status_code=200, include_in_schema=False)
async def twiml_answer_webhook(
    request: Request,
    db: Session = Depends(get_db_session),
    provider=Depends(get_llm_provider),
) -> Response:
    """Twilio calls this the moment an outbound call is answered, and again
    on every subsequent `<Gather>` (see `application/voice_inbound_service.py`
    for the actual conversation-turn logic - this route only verifies the
    request and unwraps its payload).

    `lead_id` is only present as a query param on the very first hit (see
    `application/voice_outbound_service.py`'s `_build_webhook_url`) - every
    turn after that is found again via Twilio's `CallSid`
    (`VoiceInboundService` handles both cases).

    Twilio POSTs this as `application/x-www-form-urlencoded` (CallSid,
    From, To, SpeechResult, Confidence, ...) exactly like its WhatsApp
    webhook - read via `request.form()`, same as `api/routes.py`'s
    `whatsapp_webhook`, so `verify_twilio_signature` gets the exact params
    Twilio signed.
    """
    form = await request.form()
    payload = dict(form)

    verify_twilio_signature(
        url=str(request.url),
        params=payload,
        signature=request.headers.get("X-Twilio-Signature"),
    )

    call_sid = payload.get("CallSid")
    if call_sid:
        enforce_rate_limit(f"voice-twiml:{call_sid}")

    lead_id_param = request.query_params.get("lead_id")
    lead_id = UUID(lead_id_param) if lead_id_param else None

    service = VoiceInboundService(db, provider=provider)
    result = service.handle_webhook(payload, lead_id=lead_id)

    return Response(content=result.xml, media_type="application/xml")
