import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ConversationListItem, MessageSummary } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  MessageSquare,
  Search,
  ShieldCheck,
  Phone,
  Send,
  Sparkles,
  Clock,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Ban,
  User,
  Bot,
  RotateCcw,
  Check,
  Copy,
} from "lucide-react";
import { toast } from "sonner";

export const ConversationsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);

  const {
    data: convData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["conversations", stateFilter, searchTerm],
    queryFn: () =>
      apiClient.getConversations({
        state: stateFilter === "ALL" ? undefined : stateFilter,
        search: searchTerm.trim() || undefined,
        limit: 100,
      }),
  });

  const conversations = convData?.items || [];

  // Auto-select first conversation if none selected
  const activeConversation = useMemo(() => {
    if (!conversations.length) return null;
    if (selectedConvId) {
      const found = conversations.find((c) => c.id === selectedConvId);
      if (found) return found;
    }
    return conversations[0];
  }, [conversations, selectedConvId]);

  // Available states for filtering
  const states = [
    { label: t("common.all"), value: "ALL" },
    { label: "START", value: "START" },
    { label: "GREETING", value: "GREETING" },
    { label: "INTENT", value: "INTENT_CONFIRMATION" },
    { label: "COLLECT", value: "COLLECT_CONTACT" },
    { label: "QUALIFIED", value: "QUALIFIED" },
    { label: "FIXED_SEEKER", value: "FIXED_SEEKER" },
    { label: "OPT_OUT", value: "OPT_OUT" },
  ];

  // Helper to detect if a message is an AI disclosure message
  const isDisclosureMessage = (msg: MessageSummary): boolean => {
    const content = (msg.content || "").toLowerCase();
    return (
      msg.role === "assistant" &&
      (content.includes("virtuelle") ||
        content.includes("intelligence artificielle") ||
        content.includes("virtuele assistent") ||
        content.includes("virtual assistant") ||
        content.includes("conseiller humain") ||
        content.includes("ai-transparantie"))
    );
  };

  // Helper to highlight extracted entities inside user message
  const renderMessageContent = (msg: MessageSummary) => {
    if (msg.role === "assistant" || msg.role === "system") {
      return <span>{msg.content}</span>;
    }


    // Match patterns: Belgian EAN (5414...), Emails, Phones (+32 or 04...), Belgian postal codes / cities
    const eanRegex = /\b5414\d{14}\b/g;
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
    const phoneRegex = /(?:\+32|0)[1-9](?:[ ./-]?\d{2}){3,4}/g;

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    const text = msg.content;

    // Combined search
    const matches: { index: number; text: string; label: string }[] = [];
    let match;

    while ((match = eanRegex.exec(text)) !== null) {
      matches.push({ index: match.index, text: match[0], label: "EAN 5414..." });
    }
    while ((match = emailRegex.exec(text)) !== null) {
      matches.push({ index: match.index, text: match[0], label: "Email" });
    }
    while ((match = phoneRegex.exec(text)) !== null) {
      matches.push({ index: match.index, text: match[0], label: "Téléphone BE" });
    }

    matches.sort((a, b) => a.index - b.index);

    if (matches.length === 0) {
      return <span>{msg.content}</span>;
    }

    matches.forEach((m, i) => {
      if (m.index > lastIndex) {
        parts.push(text.slice(lastIndex, m.index));
      }
      parts.push(
        <span
          key={i}
          title={`${t("conversations.collectedEntity")}: ${m.label}`}
          className="underline decoration-[var(--color-teal)] decoration-2 underline-offset-4 font-semibold text-[var(--color-teal-text)] cursor-help bg-[var(--color-teal-soft)]/50 px-1 py-0.5 rounded"
        >
          {m.text}
        </span>
      );
      lastIndex = m.index + m.text.length;
    });

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return <>{parts}</>;
  };

  // State machine progression steps for timeline
  const pipelineSteps = [
    { key: "START", label: "START", desc: "Initialisation du contact" },
    { key: "GREETING", label: "GREETING", desc: "Divulgation IA légale + Accueil" },
    { key: "INTENT_CONFIRMATION", label: "INTENT_CONFIRMATION", desc: "Validation volonté de changer" },
    { key: "COLLECT_CUSTOMER_TYPE", label: "COLLECT_TYPE", desc: "Particulier vs Professionnel" },
    { key: "COLLECT_LOCATION", label: "COLLECT_LOCATION", desc: "Région & GRD (Fluvius / ORES)" },
    { key: "COLLECT_SUPPLIER", label: "COLLECT_SUPPLIER", desc: "Fournisseur actuel" },
    { key: "COLLECT_CONTACT", label: "COLLECT_CONTACT", desc: "Nom, Email, Téléphone" },
    { key: "COLLECT_EAN", label: "COLLECT_EAN", desc: "Code compteur 5414..." },
    { key: "DATA_VALIDATION", label: "DATA_VALIDATION", desc: "Vérification des règles métier" },
    { key: "QUALIFIED", label: "QUALIFIED", desc: "Lead prêt pour contrat" },
  ];

  // Helper to determine step index
  const getCurrentStepIndex = (currentState: string): number => {
    const idx = pipelineSteps.findIndex((s) => s.key === currentState);
    if (idx !== -1) return idx;
    if (currentState.includes("COLLECT")) return 5;
    if (currentState === "HANDOFF" || currentState === "CONTRACT" || currentState === "CUSTOMER") return 9;
    return 1;
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("conversations.title")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-0.5">
            {t("conversations.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)]">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>AI Act Compliance Guard Active</span>
          </span>
        </div>
      </div>

      {/* Main Replay Layout: 2 Columns (List + Replay & Timeline) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[720px]">
        {/* Left Column: Conversation List (4 cols) */}
        <div className="lg:col-span-4 bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] flex flex-col overflow-hidden shadow-xs">
          {/* List Search & Filter */}
          <div className="p-3 border-b border-[var(--border)] space-y-2 bg-[var(--surface-hover)]">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)]" />
              <input
                type="text"
                placeholder={t("conversations.searchPlaceholder")}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)]"
              />
            </div>

            <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[10px]">
              {states.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStateFilter(s.value)}
                  className={`px-2 py-0.5 rounded-[0.35rem] whitespace-nowrap font-medium transition-smooth cursor-pointer ${
                    stateFilter === s.value
                      ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-semibold"
                      : "bg-[var(--surface)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* List Items */}
          <div className="flex-1 overflow-y-auto divide-y divide-[var(--border)]">
            {isLoading ? (
              <div className="p-3 space-y-3">
                {Array.from({ length: 7 }).map((_, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="flex justify-between">
                      <Skeleton className="h-3.5 w-28" />
                      <Skeleton className="h-3 w-12" />
                    </div>
                    <Skeleton className="h-3 w-44" />
                  </div>
                ))}
              </div>
            ) : conversations.length === 0 ? (
              <div className="p-8 text-center text-xs text-[var(--ink-muted)] space-y-2">
                <MessageSquare className="w-6 h-6 text-[var(--ink-subtle)] mx-auto" />
                <p>{t("conversations.emptyList")}</p>
              </div>
            ) : (
              conversations.map((conv) => {
                const isSelected = activeConversation?.id === conv.id;
                const isOptOut = conv.current_state === "OPT_OUT";

                return (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedConvId(conv.id)}
                    className={`p-3 transition-smooth cursor-pointer ${
                      isSelected
                        ? "bg-[var(--color-teal-soft)]/60 border-l-3 border-l-[var(--color-teal)]"
                        : "hover:bg-[var(--surface-hover)]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className={`text-xs font-bold truncate ${isSelected ? "text-[var(--color-teal-text)]" : "text-[var(--ink)]"}`}>
                        {isOptOut ? (
                          <span className="text-pink-600 dark:text-pink-400 font-mono text-[11px] line-through">
                            {t("compliance.gdprPurged")}
                          </span>
                        ) : (
                          conv.lead_name || "Prospect sans nom"
                        )}
                      </span>

                      <span className="font-mono text-[10px] text-[var(--ink-subtle)] shrink-0">
                        {new Date(conv.last_message_at).toLocaleTimeString("fr-BE", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] text-[var(--ink-muted)] truncate max-w-[190px]">
                        {conv.last_message_preview || "Conversation démarrée..."}
                      </p>

                      <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)] shrink-0 font-medium">
                        {conv.channel}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: WhatsApp-style Replay + State Timeline (8 cols) */}
        <div className="lg:col-span-8 bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] flex flex-col md:flex-row overflow-hidden shadow-xs">
          {/* Chat Bubbles Area */}
          <div className="flex-1 flex flex-col border-r border-[var(--border)]">
            {/* Conversation Header */}
            {activeConversation ? (
              <div className="p-3.5 border-b border-[var(--border)] flex items-center justify-between bg-[var(--surface-hover)]">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-[var(--color-navy)] text-[var(--color-teal)] flex items-center justify-center font-bold text-xs">
                    {activeConversation.lead_name?.charAt(0) || "P"}
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-[var(--ink)] tracking-tight">
                      {activeConversation.lead_name}
                    </h3>
                    <div className="flex items-center gap-2 text-[10px] text-[var(--ink-muted)]">
                      <span>Canal: <strong className="text-[var(--ink)]">{activeConversation.channel}</strong></span>
                      <span>•</span>
                      <span>Langue: <strong className="text-[var(--ink)]">{activeConversation.language.toUpperCase()}</strong></span>
                      <span>•</span>
                      <span>{activeConversation.message_count} messages</span>
                    </div>
                  </div>
                </div>

                <Badge variant={activeConversation.current_state as any} />
              </div>
            ) : (
              <div className="p-4 border-b border-[var(--border)] text-xs text-[var(--ink-muted)]">
                {t("conversations.noSelection")}
              </div>
            )}

            {/* Chat Replay Messages Body */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-[var(--color-bg)]/60">
              {activeConversation ? (
                <>
                  {activeConversation.messages.map((msg, idx) => {
                    const isAssistant = msg.role === "assistant" || msg.role === "system";
                    const isFirstBotDisclosure = isAssistant && idx === 0 && isDisclosureMessage(msg);

                    return (
                      <div
                        key={msg.id || idx}
                        className={`flex flex-col ${isAssistant ? "items-start" : "items-end"}`}
                      >
                        {/* DISCLOSURE BUBBLE SHOWCASE */}
                        {isFirstBotDisclosure ? (
                          <div className="max-w-[85%] rounded-[0.75rem] p-3.5 text-xs leading-relaxed bg-[var(--surface)] text-[var(--ink)] shadow-md border-l-4 border-l-[var(--color-teal)] border-y border-r border-[var(--border)] space-y-2">
                            <div className="flex items-center gap-1.5 text-[11px] font-bold text-[var(--color-teal-text)] bg-[var(--color-teal-soft)] px-2 py-0.5 rounded-full w-fit">
                              <ShieldCheck className="w-3.5 h-3.5" />
                              <span>{t("conversations.disclosureBadge")}</span>
                            </div>
                            <p className="text-xs font-medium text-[var(--ink)]">
                              {msg.content}
                            </p>
                            <div className="text-[10px] text-[var(--ink-subtle)] font-mono text-right">
                              {new Date(msg.timestamp).toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" })}
                            </div>
                          </div>
                        ) : (
                          <div
                            className={`max-w-[80%] rounded-[0.75rem] px-3.5 py-2.5 text-xs leading-relaxed shadow-xs ${
                              isAssistant
                                ? "bg-[var(--color-navy)] text-white/90 border border-white/5 rounded-tl-xs"
                                : "bg-[var(--surface)] text-[var(--ink)] border border-[var(--border)] rounded-tr-xs"
                            }`}
                          >
                            <div className="space-y-1">
                              <div>{renderMessageContent(msg)}</div>
                              <div
                                className={`text-[10px] font-mono text-right ${
                                  isAssistant ? "text-white/50" : "text-[var(--ink-subtle)]"
                                }`}
                              >
                                {new Date(msg.timestamp).toLocaleTimeString("fr-BE", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* Special System Chips in the Replay Flow */}
                  {activeConversation.current_state === "OPT_OUT" && (
                    <div className="flex justify-center py-2">
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-3 py-1 rounded-full bg-pink-100 dark:bg-pink-950/60 text-pink-700 dark:text-pink-300 border border-pink-300 dark:border-pink-800 shadow-xs">
                        <Ban className="w-3.5 h-3.5" />
                        <span>{t("conversations.chips.optOut")}</span>
                      </span>
                    </div>
                  )}

                  {activeConversation.current_state === "FIXED_SEEKER" && (
                    <div className="flex justify-center py-2">
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-3 py-1 rounded-full bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shadow-xs">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>{t("conversations.chips.fixedSeeker")}</span>
                      </span>
                    </div>
                  )}

                  {activeConversation.current_state === "ERROR_RECOVERY" && (
                    <div className="flex justify-center py-2">
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-3 py-1 rounded-full bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shadow-xs">
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>{t("conversations.chips.errorRecovery")}</span>
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-[var(--ink-muted)]">
                  {t("conversations.noSelection")}
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar: State Machine Timeline */}
          <div className="w-full md:w-64 bg-[var(--surface-hover)] p-4 flex flex-col justify-between overflow-y-auto">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-[var(--ink)] flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                  <span>{t("conversations.stateTimeline")}</span>
                </h4>
              </div>

              {activeConversation && (
                <div className="relative border-l-2 border-[var(--border)] ml-2 pl-3 space-y-3 text-xs">
                  {pipelineSteps.map((step, idx) => {
                    const currentIdx = getCurrentStepIndex(activeConversation.current_state);
                    const isPassed = idx < currentIdx;
                    const isCurrent = idx === currentIdx;

                    return (
                      <div key={step.key} className="relative">
                        {/* Dot indicator */}
                        <div
                          className={`absolute -left-[19px] top-1 w-3 h-3 rounded-full border-2 transition-smooth ${
                            isCurrent
                              ? "bg-[var(--color-teal)] border-white ring-4 ring-[var(--color-teal)]/20 animate-pulse"
                              : isPassed
                              ? "bg-[var(--color-teal)] border-white"
                              : "bg-[var(--surface)] border-[var(--border)]"
                          }`}
                        />

                        <div className="space-y-0.5">
                          <span
                            className={`font-mono text-[10px] font-bold block ${
                              isCurrent
                                ? "text-[var(--color-teal-text)]"
                                : isPassed
                                ? "text-[var(--ink)]"
                                : "text-[var(--ink-subtle)]"
                            }`}
                          >
                            {step.label}
                          </span>
                          <p className="text-[10px] text-[var(--ink-muted)] leading-tight">
                            {step.desc}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Invariant Footer */}
            <div className="pt-4 border-t border-[var(--border)] mt-4">
              <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface)] border border-[var(--border)] text-[10px] text-[var(--ink-muted)] leading-normal space-y-1">
                <span className="font-bold text-[var(--ink)] block">
                  Invariant d'architecture
                </span>
                <p>
                  Sophie ne décide jamais d'un état : la Machine à États finis gouverne le flux en toute indépendance du LLM.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
