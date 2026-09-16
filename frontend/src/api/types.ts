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
  address?: string | null;
  current_supplier: string | null;
  ean?: string | null;
  consumption?: string | null;
  change_intent?: boolean | null;
  opt_out_at?: string | null;
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
  language?: string | null;
  has_ev?: boolean | null;
  has_heat_pump?: boolean | null;
  has_battery?: boolean | null;
}

export type ContractStatus = "DRAFT" | "SENT" | "SIGNED" | "WITHDRAWN" | "CANCELLED";

export interface ContractSummary {
  id: string;
  lead_id: string;
  product: "Flexy" | "Motion" | string;
  status: ContractStatus;
  pdf_path: string | null;
  yousign_signature_request_id: string | null;
  yousign_document_id: string | null;
  created_at: string;
  updated_at: string;
  signed_at: string | null;
  withdrawn_at: string | null;
  digi_subscribed?: boolean;
}

export interface ContractListResponse {
  items: ContractSummary[];
  total: number;
  limit: number;
  offset: number;
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
  cost_per_conversation?: number;
  cost_per_sale?: number;
  estimated_ca?: number;
  currency?: string;
  signed_contracts?: number;
  optional_digi_revenue?: number;
}

// Matches backend/api/campaign_schemas.py's CampaignSummary exactly -
// the previous version of this type ("ACTIVE" status, leads_count,
// target_rules as an object) never matched the real API at all, which is
// how CampaignsPage.tsx ended up rendering fabricated numbers instead of
// a real, empty response.
export type CampaignStatus = "DRAFT" | "RUNNING" | "PAUSED" | "COMPLETED";

export interface CampaignSummary {
  id: string;
  name: string;
  status: CampaignStatus;
  channel: string;
  total_leads: number;
  sent: number;
  target_rules: string | null; // JSON-encoded, e.g. '{"region": "Wallonie"}'
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: CampaignSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface CampaignDetailResponse {
  campaign: CampaignSummary;
  leads: LeadSummary[];
  leads_total: number;
  leads_limit: number;
  leads_offset: number;
}

export interface CampaignAnalyticsResponse {
  campaign_id: string;
  total: number;
  pending: number;
  contacted: number;
  replied: number;
  qualified: number;
  rejected: number;
  handoff: number;
  response_rate: number;
  qualification_rate: number;
}

export interface CampaignPreviewResponse {
  campaign_id: string;
  matched_leads: number;
  channel: string;
  disclosure_preview: string;
  limit: number;
  offset: number;
}

export interface ApiError {
  message: string;
  status?: number;
  detail?: string;
}

export interface ConversationListItem {
  id: string;
  lead_id: string;
  lead_name: string;
  lead_phone: string | null;
  lead_email: string | null;
  channel: string;
  language: string;
  current_state: string;
  started_at: string;
  last_message_at: string;
  messages: MessageSummary[];
  last_message_preview: string | null;
  message_count: number;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OptOutJournalEntry {
  id: string;
  lead_id: string;
  lead_name: string;
  channel: string;
  timestamp: string;
  details: string | null;
  confirmation_sent: boolean;
}

export interface KnowledgeEntry {
  id: string;
  category: string;
  question: string;
  keywords: string[];
  answer_fr: string;
  answer_nl: string | null;
  answer_en: string | null;
  active: boolean;
  updated_at: string;
}

export interface KnowledgeEntryListResponse {
  items: KnowledgeEntry[];
  total: number;
}

export interface ComplianceOverviewResponse {
  guard_status: string;
  guard_tests_count: number;
  guard_last_run: string;
  retention_months: number;
  auto_purge_enabled: boolean;
  suppression_list_count: number;
  groq_dpa_signed: boolean;
  scc_status: string;
  anonymization_before_llm: boolean;
  opt_out_events: OptOutJournalEntry[];
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  source_type: string;
  language: string;
  status: "draft" | "published" | "archived" | string;
  version: number;
  review_date: string | null;
  chunk_count: number;
  created_at: string;
  published_at: string | null;
}

export interface UploadDocumentResponse {
  document_id: string;
  chunks_created: number;
  status: string;
}

export interface ObsolescenceItem {
  id: string;
  title: string;
  review_date: string;
  status: string;
  language: string;
}

export interface ObsolescenceStatusResponse {
  due_soon: ObsolescenceItem[];
  overdue: ObsolescenceItem[];
  archived_today_count: number;
}

export interface KnowledgeStatsResponse {
  documents_by_status: {
    draft: number;
    published: number;
    archived: number;
  };
  total_chunks: number;
  chunks_by_language: Record<string, number>;
  estimated_embedding_cost_eur: number;
  obsolescence_summary: ObsolescenceStatusResponse;
}

export interface TestQueryChunk {
  content_preview: string;
  score: number;
  document_title: string;
  version: number;
}

export interface TestQueryResponse {
  chunks: TestQueryChunk[];
  would_refuse: boolean;
}

export interface KeyHealthPayload {
  provider: string;
  status: string;
  percent_used: number | null;
}

