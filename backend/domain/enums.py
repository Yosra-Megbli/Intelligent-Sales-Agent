"""
Central enums for Ecofix AI Sales Agent (Sophie).

These enums are the single source of truth for every fixed vocabulary used
across the CRM, the Conversation State Machine and the Business Rules Engine.
Nothing here depends on the LLM: these values are set exclusively by the
Business Engine / repositories.
"""

from enum import Enum


class LeadSource(str, Enum):
    WEBSITE = "WEBSITE"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    VOICE = "VOICE"
    CSV = "CSV"
    CRM_IMPORT = "CRM_IMPORT"
    CAMPAIGN = "CAMPAIGN"


class LeadStatus(str, Enum):
    """CRM lifecycle - the customer's business journey (not the dialogue state)."""

    NEW = "NEW"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    QUALIFICATION = "QUALIFICATION"
    QUALIFIED = "QUALIFIED"
    APPOINTMENT = "APPOINTMENT"
    CONTRACT = "CONTRACT"
    CUSTOMER = "CUSTOMER"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class RejectionReason(str, Enum):
    NO_INTENT = "NO_INTENT"
    NO_CHANGE_INTENT = "NO_CHANGE_INTENT"
    OUT_OF_COVERAGE = "OUT_OF_COVERAGE"
    INVALID_CUSTOMER = "INVALID_CUSTOMER"
    DUPLICATE_LEAD = "DUPLICATE_LEAD"
    REQUEST_HUMAN_ONLY = "REQUEST_HUMAN_ONLY"


class FollowUpCategory(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    STOPPED = "STOPPED"


class CustomerType(str, Enum):
    PARTICULIER = "particulier"
    PROFESSIONNEL = "professionnel"


class Region(str, Enum):
    WALLONIE = "Wallonie"
    FLANDRE = "Flandre"
    BRUXELLES = "Bruxelles"


class ConversationChannel(str, Enum):
    WEB = "WEB"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    VOICE = "VOICE"


class ConversationState(str, Enum):
    """Internal dialogue state - how Sophie behaves right now.

    This is intentionally separate from LeadStatus: LeadStatus tells us where
    the customer is in the sales journey, ConversationState tells us what
    Sophie should do on the very next turn.
    """

    START = "START"
    GREETING = "GREETING"
    DISCOVERY = "DISCOVERY"
    INTENT_CONFIRMATION = "INTENT_CONFIRMATION"

    # Qualification sub-steps (order matters - see qualification_rules.yaml)
    COLLECT_CUSTOMER_TYPE = "COLLECT_CUSTOMER_TYPE"
    COLLECT_LOCATION = "COLLECT_LOCATION"
    COLLECT_SUPPLIER = "COLLECT_SUPPLIER"
    COLLECT_CONTACT = "COLLECT_CONTACT"
    COLLECT_EAN = "COLLECT_EAN"

    DATA_VALIDATION = "DATA_VALIDATION"
    QUALIFIED = "QUALIFIED"
    HANDOFF = "HANDOFF"
    CLOSED = "CLOSED"

    # Detours that always return to the state that was active before them
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    FAQ = "FAQ"
    OBJECTION = "OBJECTION"
    REJECTED = "REJECTED"
    ERROR_RECOVERY = "ERROR_RECOVERY"


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ActivityType(str, Enum):
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    STATUS_CHANGED = "STATUS_CHANGED"
    STATE_CHANGED = "STATE_CHANGED"
    FOLLOW_UP_SENT = "FOLLOW_UP_SENT"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    LEAD_IMPORTED = "LEAD_IMPORTED"


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
