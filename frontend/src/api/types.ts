export type LeadStatus =
  | "NEW"
  | "CONTACTED"
  | "QUALIFIED_FLEXY"
  | "QUALIFIED_MOTION"
  | "FIXED_SEEKER"
  | "OPT_OUT"
  | "LOST"
  | "HUMAN_HANDOFF";

export interface LeadSummary {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  telegram_chat_id: string | null;
  source: string;
  status: LeadStatus | string;
  rejection_reason: string | null;
  customer_type: string | null;
  region: string | null;
  city: string | null;
  date_of_birth: string | null;
  current_supplier: string | null;
  provider: string | null;
  notes: string | null;
  qualification_score: number | null;
  created_at: string;
  updated_at: string;
  next_follow_up_date: string | null;
  follow_up_category: string | null;
  campaign_id: string | null;
  campaign_name: string | null;
  last_contact_date: string | null;
}

export interface LeadListResponse {
  items: LeadSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface MessageSummary {
  id: string;
  role: "customer" | "assistant" | "system";
  content: string;
  intent_detected: string | null;
  timestamp: string;
}

export interface ConversationSummary {
  id: string;
  channel: string;
  current_state: string;
  started_at: string;
  last_message_at: string;
  messages: MessageSummary[];
}

export interface ActivitySummary {
  id: string;
  type: string;
  details: string | null;
  created_at: string;
}

export interface LeadDetailResponse {
  lead: LeadSummary;
  conversations: ConversationSummary[];
  activities: ActivitySummary[];
}

export interface HandoffEntryResponse {
  lead: LeadSummary;
  conversation_id: string;
  channel: string;
  handoff_at: string;
  reason: string | null;
}

export interface HandoffListResponse {
  items: HandoffEntryResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface StatsSummaryResponse {
  total_leads: number;
  by_status: Record<string, number>;
}

export interface ActivityFeedEntryResponse {
  id: string;
  type: string;
  details: string | null;
  created_at: string;
  lead_id: string;
  lead_name: string;
}

export interface ActivityFeedListResponse {
  items: ActivityFeedEntryResponse[];
}

export interface OverviewResponse {
  total_leads: number;
  active_conversations: number;
  active_campaigns: number;
  contacted: number;
  qualified: number;
  rejected: number;
  human_handoff: number;
  conversion_rate: number;
}

export interface CampaignSummary {
  id: string;
  name: string;
  channel: string;
  status: "DRAFT" | "ACTIVE" | "PAUSED" | "COMPLETED";
  target_rules: Record<string, unknown>;
  leads_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: CampaignSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiError {
  message: string;
  status?: number;
  detail?: string;
}
