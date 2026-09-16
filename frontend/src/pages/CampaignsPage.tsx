import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { CampaignSummary } from "@/api/types";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  Megaphone,
  Plus,
  Play,
  Pause,
  X,
  Loader2,
  Send,
  Users,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

const inputClass =
  "w-full px-3 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-[var(--surface-hover)] text-[var(--ink-muted)] border-[var(--border)]",
  RUNNING: "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border-[var(--color-teal-soft-border)]",
  PAUSED: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800",
  COMPLETED: "bg-[var(--surface-hover)] text-[var(--ink)] border-[var(--border)]",
};

// Honest stubs: built end-to-end but not activated in this deployment (no
// Twilio credentials) - see AGENTS.md. Matches
// application/campaign_service.py's _ACTIVATED_CAMPAIGN_CHANNELS exactly.
const CHANNEL_OPTIONS: { value: string; activated: boolean }[] = [
  { value: "TELEGRAM", activated: true },
  { value: "WEB", activated: true },
  { value: "SMS", activated: true },
  { value: "WHATSAPP", activated: false },
  { value: "VOICE", activated: false },
];

export const CampaignsPage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState("TELEGRAM");
  const [region, setRegion] = useState("");
  const [selectedCampaign, setSelectedCampaign] = useState<CampaignSummary | null>(null);
  const [launchTarget, setLaunchTarget] = useState<CampaignSummary | null>(null);

  const { data: campaignsData, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiClient.getCampaigns(50, 0),
  });

  const campaigns = campaignsData?.items || [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["campaigns"] });

  const createMutation = useMutation({
    mutationFn: () =>
      apiClient.createCampaign({
        name,
        channel,
        target_rules: region ? { region } : undefined,
      }),
    onSuccess: () => {
      toast.success(t("campaignsPage.createModal.success") || "Campagne créée avec succès");
      invalidate();
      setIsCreateOpen(false);
      setName("");
      setChannel("TELEGRAM");
      setRegion("");
    },
    onError: (err: any) => toast.error(err?.message || t("campaignsPage.createModal.error")),
  });

  const pauseMutation = useMutation({
    mutationFn: (id: string) => apiClient.pauseCampaign(id),
    onSuccess: () => {
      toast.success(t("campaignsPage.pauseSuccess") || "Campagne mise en pause");
      invalidate();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur"),
  });

  const resumeMutation = useMutation({
    mutationFn: (id: string) => apiClient.resumeCampaign(id),
    onSuccess: () => {
      toast.success(t("campaignsPage.resumeSuccess") || "Campagne relancée");
      invalidate();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur"),
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate();
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("campaignsPage.title")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">{t("campaignsPage.subtitle")}</p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)} className="text-xs">
          <Plus className="w-3.5 h-3.5 mr-1" />
          <span>{t("campaignsPage.newCampaign")}</span>
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-5 space-y-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-24" />
            </Card>
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-14 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-[var(--surface-hover)] border border-[var(--border)] flex items-center justify-center mx-auto text-[var(--ink-subtle)]">
              <Megaphone className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-[var(--ink)]">{t("campaignsPage.empty")}</h3>
            <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              <span>{t("campaignsPage.newCampaign")}</span>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--surface-hover)] border-b border-[var(--border)] text-[var(--ink-muted)] uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Campagne</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.channel")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.totalLeads")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.sent")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.status")}</th>
                  <th className="px-4 py-3 font-semibold text-right">{t("campaignsPage.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {campaigns.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                    onClick={() => setSelectedCampaign(c)}
                  >
                    <td className="px-4 py-3 font-semibold text-[var(--ink)]">{c.name}</td>
                    <td className="px-4 py-3 font-mono text-[11px] text-[var(--ink-muted)]">{c.channel}</td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink)]">{c.total_leads}</td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink-muted)]">{c.sent}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${STATUS_STYLES[c.status]}`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {c.status === "DRAFT" && (
                        <button
                          onClick={() => setLaunchTarget(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-[10px] font-semibold transition-smooth cursor-pointer"
                        >
                          <Play className="w-3 h-3" />
                          {t("campaignsPage.start")}
                        </button>
                      )}
                      {c.status === "RUNNING" && (
                        <button
                          onClick={() => pauseMutation.mutate(c.id)}
                          disabled={pauseMutation.isPending}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500 text-white hover:opacity-90 text-[10px] font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                        >
                          <Pause className="w-3 h-3" />
                          {t("campaignsPage.pause")}
                        </button>
                      )}
                      {c.status === "PAUSED" && (
                        <button
                          onClick={() => resumeMutation.mutate(c.id)}
                          disabled={resumeMutation.isPending}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-[10px] font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                        >
                          <Play className="w-3 h-3" />
                          {t("campaignsPage.resume")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create campaign modal */}
      {isCreateOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40"
            onClick={() => !createMutation.isPending && setIsCreateOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--surface-hover)]">
                <h2 className="text-sm font-bold text-[var(--ink)]">{t("campaignsPage.createModal.title")}</h2>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                  type="button"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <form onSubmit={handleCreateSubmit} className="p-4 space-y-3">
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("campaignsPage.createModal.name")}
                  </label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} autoFocus required />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("campaignsPage.createModal.channel")}
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {CHANNEL_OPTIONS.map((opt) => (
                      <label
                        key={opt.value}
                        title={!opt.activated ? t("campaignsPage.channelNotActivated") || "" : undefined}
                        className={`flex items-center gap-2 px-3 py-2 rounded-[0.5rem] border text-xs cursor-pointer transition-smooth ${
                          !opt.activated
                            ? "opacity-40 cursor-not-allowed border-[var(--border)]"
                            : channel === opt.value
                            ? "border-[var(--color-teal)] bg-[var(--color-teal-soft)]/30"
                            : "border-[var(--border)] hover:border-[var(--color-teal)]/50"
                        }`}
                      >
                        <input
                          type="radio"
                          name="channel"
                          value={opt.value}
                          checked={channel === opt.value}
                          disabled={!opt.activated}
                          onChange={() => setChannel(opt.value)}
                          className="accent-[var(--color-teal)]"
                        />
                        {opt.value}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("campaignsPage.createModal.region")}
                  </label>
                  <select value={region} onChange={(e) => setRegion(e.target.value)} className={inputClass}>
                    <option value="">{t("campaignsPage.createModal.anyRegion")}</option>
                    <option value="Wallonie">Wallonie</option>
                    <option value="Flandre">Flandre</option>
                  </select>
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsCreateOpen(false)}
                    className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                  >
                    {t("common.close")}
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || !name.trim()}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                  >
                    {createMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    <span>{t("campaignsPage.createModal.submit")}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}

      {launchTarget && (
        <LaunchConfirmModal campaign={launchTarget} onClose={() => setLaunchTarget(null)} onLaunched={invalidate} />
      )}

      {selectedCampaign && (
        <CampaignDetailModal campaign={selectedCampaign} onClose={() => setSelectedCampaign(null)} />
      )}
    </div>
  );
};

const LaunchConfirmModal: React.FC<{
  campaign: CampaignSummary;
  onClose: () => void;
  onLaunched: () => void;
}> = ({ campaign, onClose, onLaunched }) => {
  const { t } = useTranslation();

  const { data: preview, isLoading } = useQuery({
    queryKey: ["campaignPreview", campaign.id],
    queryFn: () => apiClient.previewCampaign(campaign.id),
  });

  const startMutation = useMutation({
    mutationFn: () => apiClient.startCampaign(campaign.id),
    onSuccess: () => {
      toast.success(t("campaignsPage.startConfirm.success") || "Campagne lancée");
      onLaunched();
      onClose();
    },
    onError: (err: any) => toast.error(err?.message || t("campaignsPage.startConfirm.error")),
  });

  return (
    <>
      <div className="fixed inset-0 bg-black/50 backdrop-blur-xs z-[60]" onClick={onClose} aria-hidden="true" />
      <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
        <div className="w-full max-w-sm bg-[var(--surface)] border border-[var(--color-teal-soft-border)] rounded-2xl shadow-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-[var(--ink)] font-bold text-sm">
            <ShieldCheck className="w-4 h-4 text-[var(--color-teal)]" />
            <span>{t("campaignsPage.startConfirm.title")}</span>
          </div>
          {isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <>
              <p className="text-xs text-[var(--ink)] leading-relaxed">
                {t("campaignsPage.startConfirm.body", { count: preview?.matched_leads ?? 0 })}
              </p>
              <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1">
                <span className="text-[10px] font-semibold text-[var(--ink-muted)] uppercase">
                  {t("campaignsPage.startConfirm.disclosurePreview")}
                </span>
                <p className="text-[11px] text-[var(--ink-muted)] italic">{preview?.disclosure_preview}</p>
              </div>
            </>
          )}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={startMutation.isPending}
              className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer disabled:opacity-50"
            >
              {t("common.close")}
            </button>
            <button
              type="button"
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending || isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
            >
              {startMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>{t("campaignsPage.startConfirm.confirm")}</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

const CampaignDetailModal: React.FC<{ campaign: CampaignSummary; onClose: () => void }> = ({ campaign, onClose }) => {
  const { t } = useTranslation();

  const { data: analytics, isLoading } = useQuery({
    queryKey: ["campaignAnalytics", campaign.id],
    queryFn: () => apiClient.getCampaignAnalytics(campaign.id),
  });

  const stats: { key: keyof NonNullable<typeof analytics>; label: string }[] = [
    { key: "total", label: t("campaignsPage.detail.total") },
    { key: "pending", label: t("campaignsPage.detail.pending") },
    { key: "contacted", label: t("campaignsPage.detail.contacted") },
    { key: "replied", label: t("campaignsPage.detail.replied") },
    { key: "qualified", label: t("campaignsPage.detail.qualified") },
    { key: "rejected", label: t("campaignsPage.detail.rejected") },
    { key: "handoff", label: t("campaignsPage.detail.handoff") },
  ];

  return (
    <>
      <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40" onClick={onClose} aria-hidden="true" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="w-full max-w-lg bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--surface-hover)]">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-[var(--color-teal)]" />
              <h2 className="text-sm font-bold text-[var(--ink)]">{campaign.name}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
              type="button"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
            {isLoading ? (
              <div className="grid grid-cols-3 gap-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {stats.map((s) => (
                  <div
                    key={String(s.key)}
                    className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] text-center"
                  >
                    <div className="text-lg font-bold text-[var(--ink)] tabular-nums font-mono">
                      {analytics ? (analytics[s.key] as number) : "—"}
                    </div>
                    <div className="text-[10px] text-[var(--ink-muted)]">{s.label}</div>
                  </div>
                ))}
              </div>
            )}
            {analytics && (
              <div className="flex gap-4 text-xs text-[var(--ink-muted)] pt-2 border-t border-[var(--border)]">
                <span>
                  {t("campaignsPage.detail.responseRate")}:{" "}
                  <strong className="text-[var(--ink)]">{analytics.response_rate.toFixed(1)}%</strong>
                </span>
                <span>
                  {t("campaignsPage.detail.qualificationRate")}:{" "}
                  <strong className="text-[var(--ink)]">{analytics.qualification_rate.toFixed(1)}%</strong>
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default CampaignsPage;
