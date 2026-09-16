import React from "react";
import { useTranslation } from "react-i18next";
import { ConversationListItem, MessageSummary } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import {
  X,
  MessageSquare,
  User,
  Bot,
  Clock,
  Send,
  Phone,
  Radio,
} from "lucide-react";

interface ConversationReplayDrawerProps {
  conversation: ConversationListItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ConversationReplayDrawer: React.FC<ConversationReplayDrawerProps> = ({
  conversation,
  isOpen,
  onClose,
}) => {
  const { t } = useTranslation();

  if (!isOpen || !conversation) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-[var(--surface)] border-l border-[var(--border)] shadow-2xl flex flex-col transition-smooth"
      >
        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] bg-[var(--surface-hover)] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-[var(--color-teal)]/10 text-[var(--color-teal)] flex items-center justify-center font-bold text-xs">
              <Radio className="w-4 h-4 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[var(--ink)]">
                  {conversation.lead_name || t("conversations.leadUnknown")}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--color-teal)]/10 text-[var(--color-teal)]">
                  {conversation.channel}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--border)] text-[var(--ink)]">
                  {conversation.current_state}
                </span>
              </div>
              <p className="text-[11px] text-[var(--ink-muted)]">
                ID: {conversation.id.slice(0, 8)} · Langue : {conversation.language.toUpperCase()}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages Body */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-[var(--bg-app)]/50">
          {(!conversation.messages || conversation.messages.length === 0) ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-xs text-[var(--ink-muted)] space-y-2">
              <MessageSquare className="w-8 h-8 opacity-40 text-[var(--ink-subtle)]" />
              <span>Aucun message dans cette conversation.</span>
            </div>
          ) : (
            conversation.messages.map((msg: MessageSummary, idx: number) => {
              const isAssistant = msg.role === "assistant";
              return (
                <div
                  key={idx}
                  className={`flex items-start gap-2.5 ${
                    isAssistant ? "justify-start" : "justify-end"
                  }`}
                >
                  {isAssistant && (
                    <div className="w-6 h-6 rounded-full bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                  )}

                  <div
                    className={`max-w-[80%] rounded-2xl p-3 text-xs leading-relaxed shadow-xs ${
                      isAssistant
                        ? "bg-[var(--surface)] border border-[var(--border)] text-[var(--ink)] rounded-tl-none"
                        : "bg-[var(--color-teal)] text-white rounded-tr-none"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    <div
                      className={`text-[10px] mt-1 text-right ${
                        isAssistant ? "text-[var(--ink-subtle)]" : "text-white/70"
                      }`}
                    >
                      {new Date(msg.timestamp || Date.now()).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </div>
                  </div>

                  {!isAssistant && (
                    <div className="w-6 h-6 rounded-full bg-[var(--color-navy)]/20 text-[var(--color-navy)] flex items-center justify-center shrink-0 mt-0.5">
                      <User className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer info (Read-only live notice) */}
        <div className="p-3 border-t border-[var(--border)] bg-[var(--surface)] text-[11px] text-[var(--ink-muted)] flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Radio className="w-3 h-3 text-[var(--color-teal)]" />
            <span>Vue directe en lecture seule (Live Replay)</span>
          </span>
          <span>{conversation.messages?.length || 0} messages</span>
        </div>
      </div>
    </>
  );
};
