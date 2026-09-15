import {
  ActivityFeedListResponse,
  CampaignListResponse,
  HandoffListResponse,
  LeadDetailResponse,
  LeadListResponse,
  OverviewResponse,
  StatsSummaryResponse,
} from "./types";
import { toast } from "sonner";

export const DEFAULT_API_BASE = "https://intelligent-sales-agent.onrender.com";

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || (import.meta.env.VITE_API_URL as string) || DEFAULT_API_BASE;
  }

  private getApiKey(): string | null {
    return localStorage.getItem("sophie_api_key");
  }

  private async request<T>(
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
        let detail = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const body = await response.json();
          if (body.detail) detail = body.detail;
        } catch {
          // ignore non-json error responses
        }
        throw new Error(detail);
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
}

export const apiClient = new ApiClient();
