import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { CampaignSummary, LeadSummary } from "@/api/types";
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
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  UploadCloud,
  ArrowRight,
  ArrowLeft,
  CheckSquare,
  Square,
  Search,
  Ban,
} from "lucide-react";
import { toast } from "sonner";

const inputClass =
  "w-full px-3 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-[var(--surface-hover)] text-[var(--ink-muted)] border-[var(--border)]",
  RUNNING: "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border-[var(--color-teal-soft-border)]",
  PAUSED: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800",
  COMPLETED: "bg-[var(--surface-hover)] text-[var(--ink)] border-[var(--border)]",
  CANCELLED: "bg-rose-100 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border-rose-300 dark:border-rose-800",
};

const CHANNEL_OPTIONS: { value: string; label: string; activated: boolean }[] = [
  { value: "TELEGRAM", label: "Telegram Bot (@EcofixSalesBot)", activated: true },
  { value: "WEB", label: "Web Chatbot Widget", activated: true },
  { value: "SMS", label: "Twilio SMS (FR/NL/EN)", activated: true },
  { value: "WHATSAPP", label: "WhatsApp Business API", activated: false },
  { value: "VOICE", label: "Twilio Voice Outbound AI", activated: false },
];

export const CampaignsPage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<CampaignSummary | null>(null);
  const [launchTarget, setLaunchTarget] = useState<CampaignSummary | null>(null);

  const { data: campaignsData, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiClient.getCampaigns(50, 0),
  });

  const campaigns = campaignsData?.items || [];
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["campaigns"] });

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

  const cancelMutation = useMutation({
    mutationFn: (id: string) => apiClient.cancelCampaign(id),
    onSuccess: () => {
      toast.success(t("campaignsPage.cancelSuccess") || "Campagne annulée avec succès");
      invalidate();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur lors de l'annulation"),
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("campaignsPage.title") || "Campagnes Outbound"}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("campaignsPage.subtitle") || "Pilotez vos campagnes d'engagement automatisées et conformes AI Act."}
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setIsWizardOpen(true)} className="text-xs">
          <Plus className="w-3.5 h-3.5 mr-1" />
          <span>{t("campaignsPage.newCampaign") || "Nouvelle Campagne (Assistant)"}</span>
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
            <h3 className="text-sm font-bold text-[var(--ink)]">{t("campaignsPage.empty") || "Aucune campagne active"}</h3>
            <p className="text-xs text-[var(--ink-muted)] max-w-sm mx-auto">
              Créez votre première campagne d'engagement avec l'assistant guidé en 3 étapes.
            </p>
            <Button variant="primary" size="sm" onClick={() => setIsWizardOpen(true)}>
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              <span>{t("campaignsPage.newCampaign") || "Lancer l'assistant de campagne"}</span>
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
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.channel") || "Canal"}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.totalLeads") || "Cible"}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.sent") || "Envoyés"}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.status") || "Statut"}</th>
                  <th className="px-4 py-3 font-semibold text-right">{t("campaignsPage.actions") || "Actions"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {campaigns.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                    onClick={() => setSelectedCampaign(c)}
                  >
                    <td className="px-4 py-3 font-semibold text-[var(--ink)]">
                      <div className="flex items-center gap-2">
                        <span>{c.name}</span>
                        {c.status === "CANCELLED" && (
                          <span className="text-[10px] text-rose-500 font-normal">
                            (Annulée)
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-[var(--ink-muted)]">{c.channel}</td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink)]">{c.total_leads}</td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink-muted)]">{c.sent}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${STATUS_STYLES[c.status] || STATUS_STYLES.DRAFT}`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        {c.status === "DRAFT" && (
                          <button
                            onClick={() => setLaunchTarget(c)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-[10px] font-semibold transition-smooth cursor-pointer"
                          >
                            <Play className="w-3 h-3" />
                            {t("campaignsPage.start") || "Démarrer"}
                          </button>
                        )}
                        {c.status === "RUNNING" && (
                          <button
                            onClick={() => pauseMutation.mutate(c.id)}
                            disabled={pauseMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500 text-white hover:opacity-90 text-[10px] font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                          >
                            <Pause className="w-3 h-3" />
                            {t("campaignsPage.pause") || "Pause"}
                          </button>
                        )}
                        {c.status === "PAUSED" && (
                          <button
                            onClick={() => resumeMutation.mutate(c.id)}
                            disabled={resumeMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-[10px] font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                          >
                            <Play className="w-3 h-3" />
                            {t("campaignsPage.resume") || "Reprendre"}
                          </button>
                        )}
                        {(c.status === "DRAFT" || c.status === "RUNNING" || c.status === "PAUSED") && (
                          <button
                            onClick={() => {
                              if (window.confirm(`Confirmez-vous l'annulation de la campagne "${c.name}" ?`)) {
                                cancelMutation.mutate(c.id);
                              }
                            }}
                            disabled={cancelMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-rose-50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800 hover:bg-rose-100 dark:hover:bg-rose-900/50 text-[10px] font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                            title="Annuler définitivement la campagne"
                          >
                            <Ban className="w-3 h-3" />
                            {t("campaignsPage.cancel") || "Annuler"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3-Step Campaign Creation Wizard */}
      {isWizardOpen && (
        <CampaignWizardModal
          onClose={() => setIsWizardOpen(false)}
          onSuccess={() => {
            setIsWizardOpen(false);
            invalidate();
          }}
        />
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

/* ── 3-STEP CAMPAIGN CREATION WIZARD ─────────────────────────────────────── */

interface CampaignWizardModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const CampaignWizardModal: React.FC<CampaignWizardModalProps> = ({ onClose, onSuccess }) => {
  const { t } = useTranslation();
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1: Info
  const [name, setName] = useState("");
  const [channel, setChannel] = useState("TELEGRAM");

  // Step 2: Targeting Method ('region' | 'checkboxes' | 'csv')
  const [targetMode, setTargetMode] = useState<"region" | "checkboxes" | "csv">("region");
  const [region, setRegion] = useState("");

  // Checkboxes targeting
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(new Set());
  const [leadSearchTerm, setLeadSearchTerm] = useState("");

  // CSV targeting
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvRowsCount, setCsvRowsCount] = useState<number>(0);
  const [csvPreviewError, setCsvPreviewError] = useState<string | null>(null);

  // Fetch leads for checkbox selection
  const { data: leadsData, isLoading: isLeadsLoading } = useQuery({
    queryKey: ["leadsForCampaignWizard"],
    queryFn: () => apiClient.getLeads({ limit: 100 }),
    enabled: targetMode === "checkboxes",
  });

  const availableLeads = leadsData?.items || [];
  const filteredLeads = availableLeads.filter((l) => {
    const fullName = [l.first_name, l.last_name].filter(Boolean).join(" ").toLowerCase();
    return (
      !leadSearchTerm.trim() ||
      fullName.includes(leadSearchTerm.toLowerCase()) ||
      (l.email && l.email.toLowerCase().includes(leadSearchTerm.toLowerCase())) ||
      (l.phone && l.phone.includes(leadSearchTerm))
    );
  });

  const toggleLead = (id: string) => {
    const next = new Set(selectedLeadIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedLeadIds(next);
  };

  const toggleSelectAllLeads = () => {
    if (selectedLeadIds.size === filteredLeads.length) {
      setSelectedLeadIds(new Set());
    } else {
      setSelectedLeadIds(new Set(filteredLeads.map((l) => l.id)));
    }
  };

  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCsvFile(file);
    setCsvPreviewError(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
      if (lines.length <= 1) {
        setCsvPreviewError("Le fichier CSV doit contenir un en-tête et au moins une ligne de prospect.");
        setCsvRowsCount(0);
        return;
      }
      setCsvRowsCount(lines.length - 1);
    };
    reader.readAsText(file);
  };

  const createMutation = useMutation({
    mutationFn: () => {
      const targetRules: Record<string, unknown> = {
        target_mode: targetMode,
      };
      if (targetMode === "region") {
        if (region) targetRules.region = region;
      } else if (targetMode === "checkboxes") {
        targetRules.selected_lead_ids = Array.from(selectedLeadIds);
        targetRules.leads_count = selectedLeadIds.size;
      } else if (targetMode === "csv") {
        targetRules.csv_filename = csvFile?.name || "import.csv";
        targetRules.csv_leads_count = csvRowsCount;
      }

      return apiClient.createCampaign({
        name,
        channel,
        target_rules: targetRules,
      });
    },
    onSuccess: () => {
      toast.success("Campagne créée avec succès ! Prête pour le lancement.");
      onSuccess();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur lors de la création"),
  });

  return (
    <>
      <div className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50" onClick={onClose} aria-hidden="true" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
          {/* Header */}
          <div className="p-4 border-b border-[var(--border)] bg-[var(--surface-hover)] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Megaphone className="w-4 h-4 text-[var(--color-teal)]" />
              <h2 className="text-sm font-bold text-[var(--ink)]">
                Assistant de Campagne Outbound — Étape {step}/3
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Stepper Indicator */}
          <div className="grid grid-cols-3 border-b border-[var(--border)] bg-[var(--surface)] text-center text-xs font-semibold">
            <div
              className={`py-2.5 border-b-2 transition-smooth ${
                step === 1
                  ? "border-[var(--color-teal)] text-[var(--color-teal)] bg-[var(--color-teal-soft)]/20"
                  : step > 1
                  ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
                  : "border-transparent text-[var(--ink-subtle)]"
              }`}
            >
              1. Paramètres & Canal
            </div>
            <div
              className={`py-2.5 border-b-2 transition-smooth ${
                step === 2
                  ? "border-[var(--color-teal)] text-[var(--color-teal)] bg-[var(--color-teal-soft)]/20"
                  : step > 2
                  ? "border-emerald-500 text-emerald-600 dark:text-emerald-400"
                  : "border-transparent text-[var(--ink-subtle)]"
              }`}
            >
              2. Sélection Prospects
            </div>
            <div
              className={`py-2.5 border-b-2 transition-smooth ${
                step === 3
                  ? "border-[var(--color-teal)] text-[var(--color-teal)] bg-[var(--color-teal-soft)]/20"
                  : "border-transparent text-[var(--ink-subtle)]"
              }`}
            >
              3. Aperçu & Validation
            </div>
          </div>

          {/* Body */}
          <div className="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
            {/* STEP 1: General Info & Channel */}
            {step === 1 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    Nom de la campagne *
                  </label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ex: Relance Flexy Printemps 2026 - Wallonie"
                    className={inputClass}
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    Canal d'engagement automatisé *
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {CHANNEL_OPTIONS.map((opt) => (
                      <label
                        key={opt.value}
                        title={!opt.activated ? "Canal non activé en production (clés d'accès requises)" : undefined}
                        className={`flex items-start gap-2.5 p-3 rounded-xl border cursor-pointer transition-smooth ${
                          !opt.activated
                            ? "opacity-50 cursor-not-allowed border-[var(--border)] bg-[var(--surface-hover)]/30"
                            : channel === opt.value
                            ? "border-[var(--color-teal)] bg-[var(--color-teal-soft)]/30 shadow-xs"
                            : "border-[var(--border)] hover:border-[var(--color-teal)]/40"
                        }`}
                      >
                        <input
                          type="radio"
                          name="channel"
                          value={opt.value}
                          checked={channel === opt.value}
                          disabled={!opt.activated}
                          onChange={() => setChannel(opt.value)}
                          className="mt-0.5 accent-[var(--color-teal)]"
                        />
                        <div>
                          <div className="font-semibold text-[var(--ink)]">{opt.label}</div>
                          <div className="text-[10px] text-[var(--ink-muted)] mt-0.5 font-mono">
                            {opt.activated ? "✓ Prêt pour diffusion" : "Clés requises (Désactivé)"}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* STEP 2: Target Selection */}
            {step === 2 && (
              <div className="space-y-4">
                <div className="flex items-center gap-1.5 p-1 bg-[var(--surface-hover)] rounded-xl border border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => setTargetMode("region")}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-smooth ${
                      targetMode === "region"
                        ? "bg-[var(--surface)] text-[var(--ink)] shadow-xs"
                        : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                    }`}
                  >
                    1. Règle Géographique
                  </button>
                  <button
                    type="button"
                    onClick={() => setTargetMode("checkboxes")}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-smooth ${
                      targetMode === "checkboxes"
                        ? "bg-[var(--surface)] text-[var(--ink)] shadow-xs"
                        : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                    }`}
                  >
                    2. Cases à cocher (CRM)
                  </button>
                  <button
                    type="button"
                    onClick={() => setTargetMode("csv")}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-smooth ${
                      targetMode === "csv"
                        ? "bg-[var(--surface)] text-[var(--ink)] shadow-xs"
                        : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                    }`}
                  >
                    3. Fichier CSV Dédié
                  </button>
                </div>

                {/* Sub-mode 1: Region */}
                {targetMode === "region" && (
                  <div className="space-y-3 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                    <h3 className="font-semibold text-[var(--ink)] text-xs">
                      Ciblage automatique par zone de distribution (GRD)
                    </h3>
                    <p className="text-[11px] text-[var(--ink-muted)]">
                      Sophie engagera automatiquement tous les prospects admissibles (nouveaux contacts, non désinscrits) situés dans la zone sélectionnée.
                    </p>
                    <div>
                      <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                        Zone géographique
                      </label>
                      <select value={region} onChange={(e) => setRegion(e.target.value)} className={inputClass}>
                        <option value="">Toute la Belgique éligible (Wallonie + Flandre)</option>
                        <option value="Wallonie">Wallonie uniquement (Régulateur CWaPE - ORES / RESA)</option>
                        <option value="Flandre">Flandre uniquement (Régulateur VREG - Fluvius)</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* Sub-mode 2: Checkboxes */}
                {targetMode === "checkboxes" && (
                  <div className="space-y-3 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold text-[var(--ink)] text-xs">
                          Sélection manuelle de prospects
                        </h3>
                        <p className="text-[11px] text-[var(--ink-muted)]">
                          {selectedLeadIds.size} prospect(s) sélectionné(s) sur {filteredLeads.length} visibles.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={toggleSelectAllLeads}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-[var(--border)] hover:bg-[var(--surface-hover)] text-[11px] font-semibold transition-smooth"
                      >
                        {selectedLeadIds.size === filteredLeads.length ? (
                          <>
                            <CheckSquare className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                            <span>Tout désélectionner</span>
                          </>
                        ) : (
                          <>
                            <Square className="w-3.5 h-3.5 text-[var(--ink-muted)]" />
                            <span>Tout sélectionner</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-[var(--ink-subtle)]" />
                      <input
                        value={leadSearchTerm}
                        onChange={(e) => setLeadSearchTerm(e.target.value)}
                        placeholder="Filtrer par nom, email, téléphone..."
                        className={`${inputClass} pl-8`}
                      />
                    </div>

                    <div className="max-h-56 overflow-y-auto border border-[var(--border)] rounded-lg divide-y divide-[var(--border)]">
                      {isLeadsLoading ? (
                        <div className="p-4 text-center text-xs text-[var(--ink-muted)]">
                          Chargement des prospects...
                        </div>
                      ) : filteredLeads.length === 0 ? (
                        <div className="p-4 text-center text-xs text-[var(--ink-muted)]">
                          Aucun prospect trouvé.
                        </div>
                      ) : (
                        filteredLeads.map((lead) => {
                          const isChecked = selectedLeadIds.has(lead.id);
                          return (
                            <div
                              key={lead.id}
                              onClick={() => toggleLead(lead.id)}
                              className={`flex items-center justify-between p-2.5 hover:bg-[var(--surface-hover)] cursor-pointer transition-smooth ${
                                isChecked ? "bg-[var(--color-teal-soft)]/20" : ""
                              }`}
                            >
                              <div className="flex items-center gap-2.5">
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {}}
                                  className="accent-[var(--color-teal)] rounded"
                                />
                                <div>
                                  <div className="font-semibold text-[var(--ink)]">
                                    {[lead.first_name, lead.last_name].filter(Boolean).join(" ") || "Prospect sans nom"}
                                  </div>
                                  <div className="text-[10px] text-[var(--ink-muted)] font-mono">
                                    {lead.phone || lead.email || "Sans coordonnées"}
                                  </div>
                                </div>
                              </div>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink-muted)]">
                                {lead.region || "Belgique"}
                              </span>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}

                {/* Sub-mode 3: CSV Dedicated */}
                {targetMode === "csv" && (
                  <div className="space-y-3 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                    <h3 className="font-semibold text-[var(--ink)] text-xs">
                      Téléversement d'un fichier CSV dédié pour cette campagne
                    </h3>
                    <p className="text-[11px] text-[var(--ink-muted)]">
                      Importez un fichier avec colonnes <code className="font-mono text-[var(--color-teal)]">name;email;phone;region</code>.
                    </p>

                    <label className="border-2 border-dashed border-[var(--border)] hover:border-[var(--color-teal)] rounded-xl p-6 text-center cursor-pointer flex flex-col items-center justify-center gap-2 transition-smooth">
                      <UploadCloud className="w-8 h-8 text-[var(--color-teal)]" />
                      <span className="text-xs font-semibold text-[var(--ink)]">
                        {csvFile ? csvFile.name : "Cliquez ou déposez votre fichier CSV ici"}
                      </span>
                      <span className="text-[10px] text-[var(--ink-muted)]">
                        Format CSV délimité par virgule ou point-virgule (UTF-8)
                      </span>
                      <input type="file" accept=".csv" onChange={handleCsvFileChange} className="hidden" />
                    </label>

                    {csvPreviewError && (
                      <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-600 text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{csvPreviewError}</span>
                      </div>
                    )}

                    {csvRowsCount > 0 && (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-xs flex items-center gap-2 font-medium">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span>Fichier validé : {csvRowsCount} prospects prêts à être rattachés à cette campagne.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* STEP 3: Preview & Launch Confirmation */}
            {step === 3 && (
              <div className="space-y-4">
                <div className="p-4 rounded-xl border border-[var(--color-teal-soft-border)] bg-[var(--surface-hover)]/30 space-y-3">
                  <h3 className="font-bold text-[var(--ink)] text-xs flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-[var(--color-teal)]" />
                    <span>Récapitulatif de la campagne</span>
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div>
                      <span className="text-[var(--ink-muted)] block">Nom :</span>
                      <strong className="text-[var(--ink)] font-semibold">{name}</strong>
                    </div>
                    <div>
                      <span className="text-[var(--ink-muted)] block">Canal :</span>
                      <strong className="text-[var(--ink)] font-semibold font-mono">{channel}</strong>
                    </div>
                    <div>
                      <span className="text-[var(--ink-muted)] block">Mode de ciblage :</span>
                      <strong className="text-[var(--ink)] font-semibold">
                        {targetMode === "region" && (region ? `Région : ${region}` : "Toute la Belgique")}
                        {targetMode === "checkboxes" && `${selectedLeadIds.size} prospect(s) coché(s)`}
                        {targetMode === "csv" && `${csvRowsCount} prospect(s) importé(s) par CSV`}
                      </strong>
                    </div>
                    <div>
                      <span className="text-[var(--ink-muted)] block">Conformité :</span>
                      <strong className="text-emerald-600 dark:text-emerald-400 font-semibold">
                        AI Act & RGPD Validé
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1.5">
                  <div className="text-[10px] font-bold text-[var(--ink-muted)] uppercase tracking-wider">
                    Mention de transparence obligatoire (AI Act)
                  </div>
                  <p className="text-[11px] text-[var(--ink-muted)] italic leading-relaxed">
                    "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment."
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Footer Navigation */}
          <div className="p-4 border-t border-[var(--border)] bg-[var(--surface-hover)] flex items-center justify-between">
            {step > 1 ? (
              <Button variant="outline" size="sm" onClick={() => setStep((s) => (s - 1) as any)} className="text-xs">
                <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                <span>Précédent</span>
              </Button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={onClose} className="text-xs">
                Annuler
              </Button>
              {step < 3 ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    if (step === 1 && !name.trim()) {
                      toast.error("Veuillez saisir un nom de campagne.");
                      return;
                    }
                    if (step === 2 && targetMode === "checkboxes" && selectedLeadIds.size === 0) {
                      toast.error("Veuillez sélectionner au moins un prospect.");
                      return;
                    }
                    if (step === 2 && targetMode === "csv" && csvRowsCount === 0) {
                      toast.error("Veuillez charger un fichier CSV valide.");
                      return;
                    }
                    setStep((s) => (s + 1) as any);
                  }}
                  className="text-xs"
                >
                  <span>Suivant</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={createMutation.isPending}
                  onClick={() => createMutation.mutate()}
                  className="text-xs"
                >
                  {createMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  <span>Créer la campagne</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

/* ── LAUNCH CONFIRM MODAL ─────────────────────────────────────────────────── */

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
      toast.success(t("campaignsPage.startConfirm.success") || "Campagne lancée avec succès !");
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
            <span>{t("campaignsPage.startConfirm.title") || "Confirmation de lancement"}</span>
          </div>
          {isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <>
              <p className="text-xs text-[var(--ink)] leading-relaxed">
                {t("campaignsPage.startConfirm.body", { count: preview?.matched_leads ?? 0 }) ||
                  `Lancer cette campagne va contacter immédiatement ${preview?.matched_leads ?? 0} prospect(s) admissible(s).`}
              </p>
              <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1">
                <span className="text-[10px] font-semibold text-[var(--ink-muted)] uppercase">
                  {t("campaignsPage.startConfirm.disclosurePreview") || "Aperçu de la mention Sophie"}
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
              {t("common.close") || "Fermer"}
            </button>
            <button
              type="button"
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending || isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
            >
              {startMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>{t("campaignsPage.startConfirm.confirm") || "Confirmer le lancement"}</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

/* ── CAMPAIGN DETAIL MODAL ───────────────────────────────────────────────── */

const CampaignDetailModal: React.FC<{ campaign: CampaignSummary; onClose: () => void }> = ({ campaign, onClose }) => {
  const { t } = useTranslation();

  const { data: analytics, isLoading } = useQuery({
    queryKey: ["campaignAnalytics", campaign.id],
    queryFn: () => apiClient.getCampaignAnalytics(campaign.id),
  });

  const stats: { key: keyof NonNullable<typeof analytics>; label: string }[] = [
    { key: "total", label: t("campaignsPage.detail.total") || "Total" },
    { key: "pending", label: t("campaignsPage.detail.pending") || "En attente" },
    { key: "contacted", label: t("campaignsPage.detail.contacted") || "Contactés" },
    { key: "replied", label: t("campaignsPage.detail.replied") || "Réponses" },
    { key: "qualified", label: t("campaignsPage.detail.qualified") || "Qualifiés" },
    { key: "rejected", label: t("campaignsPage.detail.rejected") || "Refusés" },
    { key: "handoff", label: t("campaignsPage.detail.handoff") || "Relais Humain" },
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
                  {t("campaignsPage.detail.responseRate") || "Taux de réponse"}:{" "}
                  <strong className="text-[var(--ink)]">{analytics.response_rate.toFixed(1)}%</strong>
                </span>
                <span>
                  {t("campaignsPage.detail.qualificationRate") || "Taux de qualification"}:{" "}
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
