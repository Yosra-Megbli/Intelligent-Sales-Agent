/**
 * EventSource SSE wrapper with auto-reconnect, token renewal,
 * reconnection state exposure, and 60s downtime fallback notification.
 */

import { apiClient, DEFAULT_API_BASE } from "./client";

export type LiveConnectionState = "CONNECTING" | "CONNECTED" | "RECONNECTING" | "DOWN";

export interface ConversationUpdatedPayload {
  lead_id: string | null;
  conversation_id: string;
  channel: string;
  state: string;
  last_message_preview: string;
  direction: "in" | "out";
}

export interface LeadStateChangedPayload {
  lead_id: string | null;
  from_state: string;
  to_state: string;
}

export interface CampaignProgressPayload {
  campaign_id: string;
  sent: number;
  responded: number;
  qualified: number;
  opted_out: number;
}

export interface KeyHealthPayload {
  provider: string;
  status: string;
  percent_used: number | null;
}

export interface LiveEvent<T = any> {
  event: string;
  data: T;
  receivedAt: Date;
}

export interface LiveClientCallbacks {
  onEvent?: (event: LiveEvent) => void;
  onStateChange?: (state: LiveConnectionState) => void;
  onDown?: () => void;
}

export class LiveClient {
  private eventSource: EventSource | null = null;
  private state: LiveConnectionState = "CONNECTING";
  private baseUrl: string;
  private callbacks: LiveClientCallbacks = {};
  private downTimer: ReturnType<typeof setTimeout> | null = null;
  private tokenExpiryTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isDestroyed = false;

  constructor(baseUrl?: string) {
    this.baseUrl =
      baseUrl ||
      (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL
        ? String(import.meta.env.VITE_API_URL).trim()
        : DEFAULT_API_BASE);
  }

  async connect(callbacks: LiveClientCallbacks): Promise<void> {
    this.callbacks = callbacks;
    this.isDestroyed = false;
    await this.initiateStream();
  }

  private async fetchToken(): Promise<string> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const apiKey = apiClient.getApiKey();
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}/api/live/token`, {
      method: "POST",
      headers,
    });
    if (!response.ok) {
      throw new Error(`Token fetch failed: ${response.status}`);
    }
    const data = await response.json();
    return data.token;
  }

  private setState(newState: LiveConnectionState) {
    if (this.state === newState) return;
    this.state = newState;
    this.callbacks.onStateChange?.(newState);
  }

  private async initiateStream(): Promise<void> {
    if (this.isDestroyed) return;
    this.setState(this.reconnectAttempts > 0 ? "RECONNECTING" : "CONNECTING");

    try {
      const token = await this.fetchToken();
      if (this.isDestroyed) return;

      if (this.eventSource) {
        this.eventSource.close();
      }

      const streamUrl = `${this.baseUrl.replace(/\/$/, "")}/api/live/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(streamUrl);
      this.eventSource = es;

      es.onopen = () => {
        if (this.isDestroyed) {
          es.close();
          return;
        }
        this.reconnectAttempts = 0;
        this.setState("CONNECTED");
        if (this.downTimer) {
          clearTimeout(this.downTimer);
          this.downTimer = null;
        }

        // Token expires in 5 minutes (300s) -> refresh connection at 4.5 minutes (270s)
        if (this.tokenExpiryTimer) clearTimeout(this.tokenExpiryTimer);
        this.tokenExpiryTimer = setTimeout(() => {
          if (!this.isDestroyed && this.state === "CONNECTED") {
            this.initiateStream();
          }
        }, 270_000);
      };

      const handleIncoming = (eventType: string, e: MessageEvent) => {
        try {
          const parsed = JSON.parse(e.data);
          this.callbacks.onEvent?.({
            event: eventType,
            data: parsed,
            receivedAt: new Date(),
          });
        } catch {
          // Heartbeats or raw text
        }
      };

      es.addEventListener("conversation_updated", (e) => handleIncoming("conversation_updated", e));
      es.addEventListener("lead_state_changed", (e) => handleIncoming("lead_state_changed", e));
      es.addEventListener("campaign_progress", (e) => handleIncoming("campaign_progress", e));
      es.addEventListener("key_health", (e) => handleIncoming("key_health", e));
      es.onmessage = (e) => handleIncoming("message", e);

      es.onerror = () => {
        if (this.isDestroyed) return;
        this.setState("RECONNECTING");

        // Start down timer if not already running (triggers onDown after 60s of disconnect)
        if (!this.downTimer) {
          this.downTimer = setTimeout(() => {
            if (this.state === "RECONNECTING") {
              this.setState("DOWN");
              this.callbacks.onDown?.();
            }
          }, 60_000);
        }

        // Incremental backoff before recreating stream
        this.reconnectAttempts++;
        const backoff = Math.min(10_000, 1000 * Math.pow(1.5, this.reconnectAttempts));
        setTimeout(() => {
          if (!this.isDestroyed && this.state !== "CONNECTED") {
            this.initiateStream();
          }
        }, backoff);
      };
    } catch (err) {
      if (this.isDestroyed) return;
      this.setState("RECONNECTING");
      if (!this.downTimer) {
        this.downTimer = setTimeout(() => {
          this.setState("DOWN");
          this.callbacks.onDown?.();
        }, 60_000);
      }
      setTimeout(() => {
        if (!this.isDestroyed) this.initiateStream();
      }, 5000);
    }
  }

  disconnect(): void {
    this.isDestroyed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.downTimer) {
      clearTimeout(this.downTimer);
      this.downTimer = null;
    }
    if (this.tokenExpiryTimer) {
      clearTimeout(this.tokenExpiryTimer);
      this.tokenExpiryTimer = null;
    }
  }
}
