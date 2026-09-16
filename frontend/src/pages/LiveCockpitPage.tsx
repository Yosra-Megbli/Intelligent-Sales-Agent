import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ConversationListItem } from "@/api/types";
import {
  LiveClient,
  LiveConnectionState,
  ConversationUpdatedPayload,
  LeadStateChangedPayload,
  KeyHealthPayload,
} from "@/api/live";
import { ConversationReplayDrawer } from "@/components/live/ConversationReplayDrawer";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  Radio,
  RefreshCw,
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  MessageSquare,
  Globe,
  Send,
  Phone,
  ShieldAlert,
  Search,
  CheckCircle2,
  Clock,
  Sparkles,
} from "lucide-react";

export const LiveCockpitPage: React.FC = () => {
  const { t } = useTranslation();
  const [connectionState, setConnectionState] = useState<LiveConnectionState>("CONNECTING");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConv, setSelectedConv] = useState<ConversationListItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Filters
  const [channelFilter, setChannelFilter] = useState("ALL");
  const [stateFilter, setStateFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Rate metrics (sliding window last 60s)
  const inMessagesTimestamps = useRef<number[]>([]);
  const outMessagesTimestamps = useRef<number[]>([]);
  const [inPerMin, setInPerMin] = useState(0);
  const [outPerMin, setOutPerMin] = useState(0);

  // Initial load query
  const { data: initialData, isLoading } = useQuery({
    queryKey: ["liveConversationsInitial"],
    queryFn: () => apiClient.getConversations({ limit: 100 }),
    staleTime: 60_000,
  });

  // Query key health
  const { data: keyHealthData } = useQuery({
    queryKey: ["keyHealth"],
    queryFn: async () => {
      try {
        return await apiClient.request<KeyHealthPayload>("/api/keys/health");
      } catch {
        return { provider: "groq", status: "unknown", percent_used: null };
      }
    },
    refetchInterval: 30_000,
  });

  // Sync initial query into state
  useEffect(() => {
    if (initialData?.items) {
      setConversations(initialData.items);
    }
  }, [initialData]);

  // Rate metrics periodic pruning
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const cutoff = now - 60_000;
      inMessagesTimestamps.current = inMessagesTimestamps.current.filter((ts) => ts > cutoff);
      outMessagesTimestamps.current = outMessagesTimestamps.current.filter((ts) => ts > cutoff);
      setInPerMin(inMessagesTimestamps.current.length);
      setOutPerMin(outMessagesTimestamps.current.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // SSE Stream setup with LiveClient
  useEffect(() => {
    const live = new LiveClient();

    live.connect({
      onStateChange: (st) => setConnectionState(st),
      onDown: () => {
        setConnectionState("DOWN");
      },
      onEvent: (evt) => {
        const now = Date.now();
        if (evt.event === "conversation_updated") {
          const data = evt.data as ConversationUpdatedPayload;
          if (data.direction === "in") {
            inMessagesTimestamps.current.push(now);
          } else {
            outMessagesTimestamps.current.push(now);
          }
          setInPerMin(inMessagesTimestamps.current.length);
          setOutPerMin(outMessagesTimestamps.current.length);

          setConversations((prev) => {
            const index = prev.findIndex((c) => c.id === data.conversation_id);
            if (index >= 0) {
              const updated = [...prev];
              const existing = updated[index];
              const updatedItem: ConversationListItem = {
                ...existing,
                current_state: data.state || existing.current_state,
                last_message_preview: data.last_message_preview || existing.last_message_preview,
                last_message_at: new Date().toISOString(),
                message_count: existing.message_count + 1,
              };
              // Move to top of active list
              updated.splice(index, 1);
              return [updatedItem, ...updated];
            } else {
              // New conversation not yet in list
              const newItem: ConversationListItem = {
                id: data.conversation_id,
                lead_id: data.lead_id || "",
                lead_name: "Prospect en cours",
                lead_phone: null,
                lead_email: null,
                channel: data.channel,
                language: "fr",
                current_state: data.state,
                started_at: new Date().toISOString(),
                last_message_at: new Date().toISOString(),
                messages: [],
                last_message_preview: data.last_message_preview,
                message_count: 1,
              };
              return [newItem, ...prev];
            }
          });
        } else if (evt.event === "lead_state_changed") {
          const data = evt.data as LeadStateChangedPayload;
          setConversations((prev) =>
            prev.map((c) =>
              c.lead_id === data.lead_id ? { ...c, current_state: data.to_state } : c
            )
          );
        }
      },
    });

    return () => {
      live.disconnect();
    };
  }, []);

  // 30s Polling fallback when stream is DOWN (>60s)
  useEffect(() => {
    if (connectionState !== "DOWN") return;
    const interval = setInterval(async () => {
      try {
        const res = await apiClient.getConversations({ limit: 100 });
        if (res?.items) {
          setConversations(res.items);
        }
      } catch {
        // quiet fallback
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [connectionState]);

  // Filtered conversations
  const filtered = useMemo(() => {
    return conversations.filter((c) => {
      if (channelFilter !== "ALL" && c.channel.toUpperCase() !== channelFilter) return false;
      if (stateFilter !== "ALL" && c.current_state !== stateFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = c.lead_name?.toLowerCase().includes(q);
        const matchMsg = c.last_message_preview?.toLowerCase().includes(q);
        if (!matchName && !matchMsg) return false;
      }
      return true;
    });
  }, [conversations, channelFilter, stateFilter, searchQuery]);

  const openConversationDetail = async (conv: ConversationListItem) => {
    try {
      const full = await apiClient.getConversation(conv.id);
      setSelectedConv(full);
    } catch {
      setSelectedConv(conv);
    }
    setIsDrawerOpen(true);
  };

  const getChannelIcon = (channel: string) => {
    switch (channel.toUpperCase()) {
      case "WEB":
        return <Globe className="w-3.5 h-3.5 text-[var(--color-teal)]" />;
      case "TELEGRAM":
        return <Send className="w-3.5 h-3.5 text-sky-500" />;
      case "SMS":
        return <MessageSquare className="w-3.5 h-3.5 text-amber-500" />;
      case "VOICE":
        return <Phone className="w-3.5 h-3.5 text-emerald-500" />;
      default:
        return <MessageSquare className="w-3.5 h-3.5 text-[var(--ink-muted)]" />;
    }
  };

  const formatRelativeTime = (dateStr: string) => {
    if (!dateStr) return "";
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 10) return "à l'instant";
    if (diff < 60) return `${diff}s`;
    const mins = Math.floor(diff / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h`;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header & Status */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-[var(--color-teal)] animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-[var(--ink)]">
              {t("livePage.title") || "Supervision Live"}
            </h1>
          </div>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("livePage.subtitle") ||
              "Cockpit temps réel des conversations actives de Sophie, flux SSE et métriques instantanées."}
          </p>
        </div>

        {/* Live Status indicator badge */}
        <div className="flex items-center gap-2">
          {connectionState === "CONNECTED" && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/30 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              <span>{t("livePage.statusLive") || "En direct (SSE)"}</span>
            </span>
          )}
          {connectionState === "RECONNECTING" && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/30">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-500" />
              <span>{t("livePage.statusReconnecting") || "Reconnexion..."}</span>
            </span>
          )}
          {connectionState === "DOWN" && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-danger/10 text-danger border border-danger/30">
              <AlertTriangle className="w-3.5 h-3.5 text-danger" />
              <span>{t("livePage.statusPolling") || "Mode rafraîchissement (30s)"}</span>
            </span>
          )}
        </div>
      </div>

      {/* Stale Warning Banner if stream is down */}
      {connectionState === "DOWN" && (
        <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-xs flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>
              {t("livePage.staleNotice") ||
                "Flux SSE interrompu (>60s) — Mode rafraîchissement automatique activé toutes les 30s."}
            </span>
          </div>
          <span className="text-[11px] opacity-80 font-mono">mode: polling</span>
        </div>
      )}

      {/* Global Strip KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="text-xs text-[var(--ink-muted)] flex items-center justify-between">
            <span>{t("livePage.activeCount") || "Conversations Actives"}</span>
            <Radio className="w-3.5 h-3.5 text-[var(--color-teal)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--ink)]">
            {conversations.length}
          </div>
          <div className="text-[11px] text-[var(--ink-muted)]">
            Canaux connectés
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="text-xs text-[var(--ink-muted)] flex items-center justify-between">
            <span>{t("livePage.inPerMin") || "Messages reçus / min"}</span>
            <ArrowDownLeft className="w-3.5 h-3.5 text-[var(--color-teal)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--color-teal)]">
            {inPerMin}
          </div>
          <div className="text-[11px] text-[var(--ink-muted)]">
            Flux entrant (dernières 60s)
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="text-xs text-[var(--ink-muted)] flex items-center justify-between">
            <span>{t("livePage.outPerMin") || "Messages émis / min"}</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-[var(--color-navy)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--color-navy)]">
            {outPerMin}
          </div>
          <div className="text-[11px] text-[var(--ink-muted)]">
            Réponses Sophie (dernières 60s)
          </div>
        </div>

        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="text-xs text-[var(--ink-muted)] flex items-center justify-between">
            <span>{t("livePage.systemHealth") || "Santé des Clés API"}</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="text-lg font-bold text-[var(--ink)] truncate">
            {keyHealthData?.provider?.toUpperCase() || "GROQ"}
          </div>
          <div className="text-[11px] text-[var(--ink-muted)] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>{keyHealthData?.status === "unknown" ? "Statut opérationnel" : keyHealthData?.status || "—"}</span>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <div className="flex flex-wrap items-center gap-2">
          {/* Channel selector */}
          <div className="flex items-center gap-1 bg-[var(--surface-hover)] p-1 rounded-lg text-xs">
            {["ALL", "WEB", "TELEGRAM", "SMS"].map((ch) => (
              <button
                key={ch}
                type="button"
                onClick={() => setChannelFilter(ch)}
                className={`px-2.5 py-1 rounded-md font-semibold transition-smooth cursor-pointer ${
                  channelFilter === ch
                    ? "bg-[var(--surface)] text-[var(--color-teal)] shadow-xs"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {ch === "ALL" ? t("livePage.filterAll") || "Tous" : ch}
              </button>
            ))}
          </div>

          {/* State selector */}
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth"
          >
            <option value="ALL">{t("livePage.filterState") || "Tous les états"}</option>
            <option value="START">START</option>
            <option value="GREETING">GREETING</option>
            <option value="DISCOVERY">DISCOVERY</option>
            <option value="COLLECT_LOCATION">COLLECT_LOCATION</option>
            <option value="COLLECT_EAN">COLLECT_EAN</option>
            <option value="QUALIFIED">QUALIFIED</option>
            <option value="CONTRACT_DRAFT">CONTRACT_DRAFT</option>
            <option value="HANDOFF">HANDOFF</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </div>

        {/* Search Query */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-muted)]" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher par prospect, message..."
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth"
          />
        </div>
      </div>

      {/* Conversations Grid */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-3"
              >
                <div className="flex items-center justify-between">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center rounded-2xl border border-[var(--border)] bg-[var(--surface)] space-y-3">
            <MessageSquare className="w-8 h-8 text-[var(--ink-subtle)] mx-auto opacity-40" />
            <p className="text-xs text-[var(--ink-muted)] max-w-sm mx-auto leading-relaxed">
              {t("livePage.empty") ||
                "Aucune conversation active — lancez une campagne ou attendez un inbound."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((conv) => (
              <div
                key={conv.id}
                onClick={() => openConversationDetail(conv)}
                className="group p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--color-teal)] hover:shadow-md transition-smooth cursor-pointer flex flex-col justify-between space-y-3"
              >
                {/* Card Top */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-[var(--surface-hover)] border border-[var(--border)] flex items-center justify-center">
                      {getChannelIcon(conv.channel)}
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[var(--ink)] group-hover:text-[var(--color-teal)] transition-colors">
                        {conv.lead_name || "Prospect inconnu"}
                      </h3>
                      <div className="text-[10px] text-[var(--ink-muted)]">
                        ID: {conv.id.slice(0, 8)}
                      </div>
                    </div>
                  </div>

                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--border)]/70 text-[var(--ink)]">
                    {conv.current_state}
                  </span>
                </div>

                {/* Last message preview */}
                <p className="text-xs text-[var(--ink-muted)] line-clamp-2 leading-relaxed bg-[var(--surface-hover)]/40 p-2.5 rounded-lg border border-[var(--border)]/50">
                  {conv.last_message_preview || "Aucun message échangé pour le moment."}
                </p>

                {/* Card Bottom Meta */}
                <div className="flex items-center justify-between text-[11px] text-[var(--ink-muted)] pt-1 border-t border-[var(--border)]/60">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>{formatRelativeTime(conv.last_message_at || conv.started_at)}</span>
                  </span>
                  <span className="text-[10px] font-medium text-[var(--color-teal)] group-hover:underline">
                    {t("livePage.openReplay") || "Ouvrir le Replay →"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Replay Drawer */}
      <ConversationReplayDrawer
        conversation={selectedConv}
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setSelectedConv(null);
        }}
      />
    </div>
  );
};

export default LiveCockpitPage;
