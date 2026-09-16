import {
  ActivityFeedListResponse,
  CampaignAnalyticsResponse,
  CampaignDetailResponse,
  CampaignListResponse,
  CampaignPreviewResponse,
  CampaignSummary,
  ComplianceOverviewResponse,
  ContractListResponse,
  ContractSummary,
  ConversationListItem,
  ConversationListResponse,
  HandoffListResponse,
  KnowledgeDocument,
  KnowledgeEntry,
  KnowledgeEntryListResponse,
  KnowledgeStatsResponse,
  ImportPreviewResponse,
  ImportReportResponse,
  LeadDetailResponse,
  LeadListResponse,
  LeadSummary,
  ObsolescenceStatusResponse,
  OverviewResponse,
  StatsSummaryResponse,
  TestQueryResponse,
  UploadDocumentResponse,
} from "./types";
import { toast } from "sonner";


export const DEFAULT_API_BASE = "https://intelligent-sales-agent.onrender.com";

export class ApiClient {
  private baseUrl: string;
  // In-memory only, deliberately not persisted: the console shows the login
  // screen on every fresh load (see context/AuthContext.tsx), so nothing
  // here should survive a reload on its own.
  private apiKey: string | null = null;

  constructor(baseUrl?: string) {
    const envUrl =
      typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL
        ? String(import.meta.env.VITE_API_URL).trim()
        : "";

    if (baseUrl) {
      this.baseUrl = baseUrl.replace(/\/$/, "");
    } else if (envUrl) {
      this.baseUrl = envUrl.replace(/\/$/, "");
    } else if (import.meta.env?.DEV) {
      // In dev mode, fall back to relative path so Vite proxy forwards to Render without CORS issues
      this.baseUrl = "";
    } else {
      this.baseUrl = DEFAULT_API_BASE;
    }
  }

  setApiKey(apiKey: string | null): void {
    this.apiKey = apiKey;
  }

  getApiKey(): string | null {
    return this.apiKey;
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retries = 2
  ): Promise<T> {
    const apiKey = this.getApiKey();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }

    const url = `${this.baseUrl.replace(/\/$/, "")}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new Error("UNAUTHORIZED");
        }
        let message = `HTTP ${response.status}: ${response.statusText}`;
        let code: string | undefined;
        try {
          const body = await response.json();
          // FastAPI's `detail` is either a plain string (most routes) or a
          // structured {code, ...} object (e.g. leads_routes.py's
          // duplicate_lead/invalid_field/rijksregisternummer_rejected,
          // campaign_routes.py's channel_not_activated) - `new Error(obj)`
          // would silently stringify it to "[object Object]" otherwise.
          if (body?.detail && typeof body.detail === "object") {
            code = body.detail.code;
            message = body.detail.message || body.detail.code || message;
          } else if (body?.detail) {
            message = body.detail;
          }
        } catch {
          // ignore non-json error responses
        }
        const error = new Error(message) as Error & { code?: string };
        if (code) error.code = code;
        throw error;
      }

      // 204 No Content (leads/campaigns DELETE) has no body - calling
      // .json() on it throws a SyntaxError ("Unexpected end of JSON
      // input"), which the retry logic below would then treat as a
      // transient failure and retry a DELETE that already succeeded.
      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    } catch (err: unknown) {
      const isAuthError = err instanceof Error && err.message === "UNAUTHORIZED";
      if (!isAuthError && retries > 0) {
        // Wait 400ms then retry
        await new Promise((resolve) => setTimeout(resolve, 400));
        return this.request<T>(endpoint, options, retries - 1);
      }
      throw err;
    }
  }

  async verifyApiKey(apiKey: string): Promise<boolean> {
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/dashboard/overview`;
    try {
      const response = await fetch(url, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  async getOverview(): Promise<OverviewResponse> {
    return this.request<OverviewResponse>("/api/dashboard/overview");
  }

  async getStats(): Promise<StatsSummaryResponse> {
    return this.request<StatsSummaryResponse>("/api/dashboard/stats");
  }

  async getLeads(params?: {
    status?: string;
    region?: string;
    source?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<LeadListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.region) searchParams.set("region", params.region);
    if (params?.source) searchParams.set("source", params.source);
    if (params?.search) searchParams.set("search", params.search);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());

    const qs = searchParams.toString();
    return this.request<LeadListResponse>(`/api/dashboard/leads${qs ? `?${qs}` : ""}`);
  }

  async getLeadDetail(leadId: string): Promise<LeadDetailResponse> {
    return this.request<LeadDetailResponse>(`/api/dashboard/leads/${leadId}`);
  }

  async createLead(payload: {
    first_name?: string;
    last_name?: string;
    email?: string;
    phone?: string;
    region?: string;
    city?: string;
    customer_type?: string;
    current_supplier?: string;
    ean?: string;
    date_of_birth?: string;
  }): Promise<LeadSummary> {
    return this.request<LeadSummary>("/api/leads", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateLead(leadId: string, payload: Record<string, string | null>): Promise<LeadSummary> {
    return this.request<LeadSummary>(`/api/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteLead(leadId: string): Promise<void> {
    await this.request<void>(`/api/leads/${leadId}`, { method: "DELETE" });
  }

  async getKnowledgeEntries(): Promise<KnowledgeEntryListResponse> {
    return this.request<KnowledgeEntryListResponse>("/api/knowledge");
  }

  async createKnowledgeEntry(payload: {
    category: string;
    question: string;
    keywords: string[];
    answer_fr: string;
    answer_nl?: string;
    answer_en?: string;
    active?: boolean;
  }): Promise<KnowledgeEntry> {
    return this.request<KnowledgeEntry>("/api/knowledge", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateKnowledgeEntry(entryId: string, payload: Record<string, unknown>): Promise<KnowledgeEntry> {
    return this.request<KnowledgeEntry>(`/api/knowledge/${entryId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async toggleKnowledgeEntryActive(entryId: string): Promise<KnowledgeEntry> {
    return this.request<KnowledgeEntry>(`/api/knowledge/${entryId}/toggle-active`, { method: "POST" });
  }

  async deleteKnowledgeEntry(entryId: string): Promise<void> {
    await this.request<void>(`/api/knowledge/${entryId}`, { method: "DELETE" });
  }

  // ── RAG v2 Documents & QA (Phase 4) ───────────────────────────────────

  async getKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
    return this.request<KnowledgeDocument[]>("/api/knowledge/documents");
  }

  async uploadKnowledgeDocument(formData: FormData): Promise<UploadDocumentResponse> {
    const headers: Record<string, string> = {};
    const apiKey = this.getApiKey();
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/knowledge/documents/upload`;
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}: ${response.statusText}`;
      let code: string | undefined;
      try {
        const body = await response.json();
        if (body?.detail && typeof body.detail === "object") {
          code = body.detail.code;
          message = body.detail.message || body.detail.code || message;
        } else if (body?.detail) {
          message = body.detail;
        }
      } catch {}
      const error = new Error(message) as Error & { code?: string };
      if (code) error.code = code;
      throw error;
    }

    return (await response.json()) as UploadDocumentResponse;
  }

  async publishKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
    return this.request<KnowledgeDocument>(`/api/knowledge/documents/${documentId}/publish`, {
      method: "POST",
    });
  }

  async archiveKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
    return this.request<KnowledgeDocument>(`/api/knowledge/documents/${documentId}/archive`, {
      method: "POST",
    });
  }

  async unpublishKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
    return this.request<KnowledgeDocument>(`/api/knowledge/documents/${documentId}/unpublish`, {
      method: "POST",
    });
  }

  async getKnowledgeStats(): Promise<KnowledgeStatsResponse> {
    return this.request<KnowledgeStatsResponse>("/api/knowledge/stats");
  }

  async getKnowledgeObsolescence(): Promise<ObsolescenceStatusResponse> {
    return this.request<ObsolescenceStatusResponse>("/api/knowledge/obsolescence");
  }

  async testKnowledgeQuery(query: string, language = "fr"): Promise<TestQueryResponse> {
    return this.request<TestQueryResponse>("/api/knowledge/test", {
      method: "POST",
      body: JSON.stringify({ query, language }),
    });
  }

  async getHandoffs(params?: { limit?: number; offset?: number }): Promise<HandoffListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());
    const qs = searchParams.toString();
    return this.request<HandoffListResponse>(`/api/dashboard/handoffs${qs ? `?${qs}` : ""}`);
  }

  async getActivities(limit = 20): Promise<ActivityFeedListResponse> {
    return this.request<ActivityFeedListResponse>(`/api/dashboard/activities?limit=${limit}`);
  }

  async getCampaigns(limit = 50, offset = 0): Promise<CampaignListResponse> {
    return this.request<CampaignListResponse>(`/api/campaigns?limit=${limit}&offset=${offset}`);
  }

  async getCampaignDetail(campaignId: string): Promise<CampaignDetailResponse> {
    return this.request<CampaignDetailResponse>(`/api/campaigns/${campaignId}`);
  }

  async getCampaignAnalytics(campaignId: string): Promise<CampaignAnalyticsResponse> {
    return this.request<CampaignAnalyticsResponse>(`/api/campaigns/${campaignId}/analytics`);
  }

  async createCampaign(payload: { name: string; channel: string; target_rules?: Record<string, unknown> }): Promise<CampaignSummary> {
    return this.request<CampaignSummary>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async previewCampaign(campaignId: string): Promise<CampaignPreviewResponse> {
    return this.request<CampaignPreviewResponse>(`/api/campaigns/${campaignId}/preview`, { method: "POST" });
  }

  async startCampaign(campaignId: string): Promise<CampaignSummary> {
    return this.request<CampaignSummary>(`/api/campaigns/${campaignId}/start`, { method: "POST" });
  }

  async pauseCampaign(campaignId: string): Promise<CampaignSummary> {
    return this.request<CampaignSummary>(`/api/campaigns/${campaignId}/pause`, { method: "POST" });
  }

  async resumeCampaign(campaignId: string): Promise<CampaignSummary> {
    return this.request<CampaignSummary>(`/api/campaigns/${campaignId}/resume`, { method: "POST" });
  }

  async deleteCampaign(campaignId: string): Promise<void> {
    await this.request<void>(`/api/campaigns/${campaignId}`, { method: "DELETE" });
  }

  async getConversations(params?: {
    state?: string;
    channel?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConversationListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.state) searchParams.set("state", params.state);
    if (params?.channel) searchParams.set("channel", params.channel);
    if (params?.search) searchParams.set("search", params.search);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());
    const qs = searchParams.toString();
    return this.request<ConversationListResponse>(`/api/dashboard/conversations${qs ? `?${qs}` : ""}`);
  }

  async getConversation(id: string): Promise<ConversationListItem> {
    return this.request<ConversationListItem>(`/api/dashboard/conversations/${id}`);
  }

  async getCompliance(): Promise<ComplianceOverviewResponse> {
    return this.request<ComplianceOverviewResponse>("/api/dashboard/compliance");
  }

  async getContracts(params?: {
    lead_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<ContractListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.lead_id) searchParams.set("lead_id", params.lead_id);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());
    const qs = searchParams.toString();
    return this.request<ContractListResponse>(`/api/contracts${qs ? `?${qs}` : ""}`);
  }

  async getContract(contractId: string): Promise<ContractSummary> {
    return this.request<ContractSummary>(`/api/contracts/${contractId}`);
  }

  async createContract(leadId: string): Promise<ContractSummary> {
    return this.request<ContractSummary>("/api/contracts", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId }),
    });
  }

  async simulateSignContract(contractId: string): Promise<ContractSummary> {
    return this.request<ContractSummary>(`/api/contracts/${contractId}/simulate-sign`, {
      method: "POST",
    });
  }

  async downloadContractPdf(contractId: string, filename?: string): Promise<void> {
    const apiKey = this.getApiKey();
    const headers: Record<string, string> = {};
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    const url = `${this.baseUrl.replace(/\/$/, "")}/api/contracts/${contractId}/pdf`;
    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new Error(`Erreur lors du téléchargement du PDF (${response.status})`);
    }
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename || `contrat_specimen_${contractId.slice(0, 8)}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  }

  async startConversation(payload?: {
    first_name?: string;
    last_name?: string;
    email?: string;
    phone?: string;
  }): Promise<{ conversation_id: string; lead_id: string }> {
    return this.request<{ conversation_id: string; lead_id: string }>("/api/conversations", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  }

  async sendChatMessage(
    conversationId: string,
    text: string
  ): Promise<{ reply: string; state: string; required_action: string | null }> {
    return this.request<{ reply: string; state: string; required_action: string | null }>(
      `/api/conversations/${conversationId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ text }),
      }
    );
  }

  async previewImportLeads(csvText: string): Promise<ImportPreviewResponse> {
    return this.request<ImportPreviewResponse>("/api/leads/import/preview", {
      method: "POST",
      body: JSON.stringify({ csv_text: csvText }),
    });
  }

  async importLeads(csvText: string): Promise<ImportReportResponse> {
    return this.request<ImportReportResponse>("/api/leads/import", {
      method: "POST",
      body: JSON.stringify({ csv_text: csvText }),
    });
  }
}


export const apiClient = new ApiClient();

