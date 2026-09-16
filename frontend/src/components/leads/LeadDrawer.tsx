import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { LeadSummary, LeadStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  X,
  Check,
  Minus,
  Copy,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Battery,
  Sun,
  Flame,
  Activity as ActivityIcon,
  Calendar,
  Sparkles,
  FileText,
  Download,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

interface LeadDrawerProps {
  lead: LeadSummary | null;
  isOpen: boolean;
  onClose: () => void;
}

export const LeadDrawer: React.FC<LeadDrawerProps> = ({ lead, isOpen, onClose }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isGeneratingContract, setIsGeneratingContract] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [isSimulatingSign, setIsSimulatingSign] = useState(false);

  const { data: detailData, isLoading: isDetailLoading } = useQuery({
    queryKey: ["leadDetail", lead?.id],
    queryFn: () => (lead?.id ? apiClient.getLeadDetail(lead.id) : null),
    enabled: Boolean(lead?.id && isOpen),
  });

  const { data: contractsData } = useQuery({
    queryKey: ["leadContracts", lead?.id],
    queryFn: () => (lead?.id ? apiClient.getContracts({ lead_id: lead.id, limit: 1 }) : null),
    enabled: Boolean(lead?.id && isOpen),
  });

  const latestContract = contractsData?.items?.[0] || null;

  const handleDownloadPdf = async (contractId: string) => {
    try {
      setIsDownloadingPdf(true);
      await apiClient.downloadContractPdf(contractId, `contrat_specimen_${lead?.last_name || "lead"}.pdf`);
      toast.success(t("leads.drawer.contract.downloadSuccess") || "Contrat PDF SPÉCIMEN téléchargé");
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors du téléchargement du PDF");
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const handleGenerateContract = async () => {
    if (!lead?.id) return;
    try {
      setIsGeneratingContract(true);
      const contract = await apiClient.createContract(lead.id);
      toast.success(t("leads.drawer.contract.createSuccess") || `Contrat ${contract.product} généré avec succès !`);
      queryClient.invalidateQueries({ queryKey: ["leadContracts", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leadDetail", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      await apiClient.downloadContractPdf(contract.id, `contrat_specimen_${lead.last_name || "lead"}.pdf`);
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la génération du contrat");
    } finally {
      setIsGeneratingContract(false);
    }
  };

  const handleSimulateSign = async (contractId: string) => {
    try {
      setIsSimulatingSign(true);
      await apiClient.simulateSignContract(contractId);
      toast.success(t("leads.drawer.contract.signSuccess") || "Signature Yousign simulée avec succès ! Statut client activé.");
      queryClient.invalidateQueries({ queryKey: ["leadContracts", lead?.id] });
      queryClient.invalidateQueries({ queryKey: ["leadDetail", lead?.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la simulation de signature");
    } finally {
      setIsSimulatingSign(false);
    }
  };

  if (!lead) return null;

  const isOptOut = lead.status === "OPT_OUT" || Boolean(lead.opt_out_at);

  const copyEan = (ean: string) => {
    navigator.clipboard.writeText(ean);
    toast.success(t("leads.copyEanToast") || "Code EAN copié");
  };

  // Derive GRD based on region rule: Flanders=Fluvius, Wallonia=ORES/RESA
  const getGrd = () => {
    if (lead.provider) return lead.provider;
    const r = (lead.region || "").toLowerCase();
    if (r.includes("fland") || r.includes("vl") || r.includes("antw") || r.includes("gent")) return "Fluvius";
    if (r.includes("wallon") || r.includes("wa") || r.includes("liège") || r.includes("namur")) return "ORES";
    return "Fluvius / ORES";
  };

  // 9-field qualification checklist
  const checklistItems = [
    {
      id: "customerType",
      label: t("leads.drawer.fields.customerType"),
      value: isOptOut ? "—" : lead.customer_type || "Particulier",
      isComplete: Boolean(lead.customer_type) && !isOptOut,
    },
    {
      id: "location",
      label: t("leads.drawer.fields.location"),
      value: isOptOut ? "—" : [lead.region, lead.city].filter(Boolean).join(", ") || lead.address || null,
      isComplete: Boolean(lead.region || lead.city || lead.address) && !isOptOut,
    },
    {
      id: "supplier",
      label: t("leads.drawer.fields.supplier"),
      value: isOptOut ? "—" : lead.current_supplier || null,
      isComplete: Boolean(lead.current_supplier) && !isOptOut,
    },
    {
      id: "fullName",
      label: t("leads.drawer.fields.fullName"),
      value: isOptOut ? "—" : [lead.first_name, lead.last_name].filter(Boolean).join(" ") || null,
      isComplete: Boolean(lead.first_name || lead.last_name) && !isOptOut,
    },
    {
      id: "email",
      label: t("leads.drawer.fields.email"),
      value: isOptOut ? "—" : lead.email || null,
      isComplete: Boolean(lead.email) && !isOptOut,
    },
    {
      id: "phone",
      label: t("leads.drawer.fields.phone"),
      value: isOptOut ? "—" : lead.phone || null,
      isComplete: Boolean(lead.phone) && !isOptOut,
    },
    {
      id: "dob",
      label: t("leads.drawer.fields.dob"),
      value: isOptOut ? "—" : lead.date_of_birth || null,
      isComplete: Boolean(lead.date_of_birth) && !isOptOut,
    },
    {
      id: "ean",
      label: t("leads.drawer.fields.ean"),
      value: isOptOut ? "—" : lead.ean || (lead.notes?.includes("5414") ? "5414" + "000".repeat(4) : null),
      isComplete: Boolean(lead.ean || lead.notes?.includes("5414")) && !isOptOut,
    },
    {
      id: "changeConfirmation",
      label: t("leads.drawer.fields.changeConfirmation"),
      value: isOptOut ? "—" : lead.change_intent !== false ? "Accord explicite confirmé" : null,
      isComplete: Boolean(lead.change_intent !== false && lead.status !== "NEW") && !isOptOut,
    },
  ];

  const completedCount = checklistItems.filter((item) => item.isComplete).length;

  // Product fit chips detection
  const notesLower = (lead.notes || "").toLowerCase();
  const hasEv = notesLower.includes("ev") || notesLower.includes("électrique") || notesLower.includes("tesla") || lead.status === "QUALIFIED_MOTION";
  const hasHeatPump = notesLower.includes("pompe") || notesLower.includes("chaleur") || notesLower.includes("pac");
  const hasSolar = notesLower.includes("solaire") || notesLower.includes("panneau") || notesLower.includes("photovolta");
  const hasBattery = notesLower.includes("batterie") || notesLower.includes("stockage");

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/40 backdrop-blur-xs z-40 transition-opacity duration-250 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        className={`fixed top-0 right-0 bottom-0 w-full max-w-xl bg-[var(--surface)] border-l border-[var(--border)] shadow-2xl z-50 flex flex-col transform transition-transform duration-250 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label={t("leads.drawer.title")}
      >
        {/* Header */}
        <div className="p-5 border-b border-[var(--border)] flex items-start justify-between gap-4 bg-[var(--surface-hover)]">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-[var(--ink)] tracking-tight">
                {isOptOut ? (
                  <span className="text-pink-600 dark:text-pink-400 line-through">
                    {t("compliance.gdprPurged")}
                  </span>
                ) : (
                  [lead.first_name, lead.last_name].filter(Boolean).join(" ") || "Prospect sans nom"
                )}
              </h2>
              <Badge variant={lead.status as LeadStatus} />
              <span className="inline-flex items-center text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink-muted)] uppercase">
                {lead.language || "FR"}
              </span>
              {isOptOut && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-pink-100 dark:bg-pink-950/60 text-pink-700 dark:text-pink-300 border border-pink-300 dark:border-pink-800">
                  <ShieldAlert className="w-3 h-3" />
                  RGPD Art. 17
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-[var(--ink-muted)]">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3 text-[var(--ink-subtle)]" />
                Créé le {new Date(lead.created_at).toLocaleDateString("fr-BE")}
              </span>
              <span>•</span>
              <span>GRD: <strong className="text-[var(--ink)]">{getGrd()}</strong></span>
              {lead.campaign_name && (
                <>
                  <span>•</span>
                  <span>Campagne: {lead.campaign_name}</span>
                </>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
            aria-label={t("common.close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs">
          {/* RGPD Purged banner if opted out */}
          {isOptOut && (
            <div className="p-3.5 rounded-[0.75rem] bg-pink-50 dark:bg-pink-950/30 border border-pink-200 dark:border-pink-900/60 text-pink-900 dark:text-pink-200 space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-xs">
                <ShieldCheck className="w-4 h-4 text-pink-600 dark:text-pink-400" />
                <span>{t("leads.drawer.purgedNotice", {
                  date: lead.opt_out_at ? new Date(lead.opt_out_at).toLocaleString("fr-BE") : "Récemment",
                })}</span>
              </div>
              <p className="text-[11px] text-pink-800/80 dark:text-pink-300/80 leading-relaxed">
                Toutes les données PII (nom, téléphone, email) ont été immédiatement détruites lors de la réception du mot-clé STOP. Seule une clé d'inhibition technique anonymisée est conservée.
              </p>
            </div>
          )}

          {/* 9-Field Qualification Checklist */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-[var(--ink)] tracking-tight uppercase">
                {t("leads.drawer.qualificationTitle")}
              </h3>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-semibold">
                {completedCount}/9 {t("status.QUALIFIED").toLowerCase()}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2">
              {checklistItems.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center justify-between p-2.5 rounded-[0.5rem] border transition-smooth ${
                    item.isComplete
                      ? "bg-[var(--color-teal-soft)]/40 border-[var(--color-teal-soft-border)]"
                      : "bg-[var(--surface-hover)] border-dashed border-[var(--border)]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                        item.isComplete
                          ? "bg-[var(--color-teal)] text-white"
                          : "bg-[var(--border)] text-[var(--ink-subtle)]"
                      }`}
                    >
                      {item.isComplete ? <Check className="w-3 h-3 stroke-[2.5]" /> : <Minus className="w-3 h-3" />}
                    </div>
                    <span className="text-xs font-medium text-[var(--ink)]">
                      {item.label}
                    </span>
                  </div>

                  <div className="text-right">
                    {item.value ? (
                      <span className="font-mono text-[11px] text-[var(--ink-muted)]">
                        {item.value}
                      </span>
                    ) : (
                      <span className="text-[11px] text-[var(--ink-subtle)] italic">
                        Non renseigné
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Contract Card */}
          {!isOptOut && (
            <div className="p-3.5 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[var(--color-teal)]" />
                  <h3 className="text-xs font-bold text-[var(--ink)] tracking-tight uppercase">
                    {t("leads.drawer.contract.title") || "Contrat & Signature"}
                  </h3>
                </div>
                {latestContract && (
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                      latestContract.status === "SIGNED"
                        ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border-[var(--color-teal-soft-border)]"
                        : latestContract.status === "SENT"
                        ? "bg-sky-100 dark:bg-sky-950/60 text-sky-800 dark:text-sky-300 border-sky-300"
                        : latestContract.status === "WITHDRAWN"
                        ? "bg-pink-100 dark:bg-pink-950/60 text-pink-700 dark:text-pink-300 border-pink-300"
                        : "bg-[var(--surface)] text-[var(--ink-muted)] border-[var(--border)]"
                    }`}
                  >
                    {latestContract.status === "SIGNED" && <CheckCircle2 className="w-3 h-3 text-[var(--color-teal)]" />}
                    <span>{latestContract.status}</span>
                  </span>
                )}
              </div>

              {latestContract ? (
                <div className="space-y-2.5">
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-[var(--ink-muted)] block text-[10px]">Offre</span>
                      <span className="font-bold text-[var(--ink)]">Ecofix {latestContract.product}</span>
                    </div>
                    <div>
                      <span className="text-[var(--ink-muted)] block text-[10px]">Frais fixes (obligatoire)</span>
                      <span className="font-mono text-[var(--ink)]">60,00 € / an</span>
                    </div>
                    <div>
                      <span className="text-[var(--ink-muted)] block text-[10px]">Ecofix Digi (optionnel)</span>
                      <span className="font-mono text-[var(--ink)]">5,99 € / mois</span>
                    </div>
                    {latestContract.signed_at && (
                      <div>
                        <span className="text-[var(--ink-muted)] block text-[10px]">Signé le</span>
                        <span className="font-mono text-[var(--ink)]">
                          {new Date(latestContract.signed_at).toLocaleDateString("fr-BE")}
                        </span>
                      </div>
                    )}
                    {latestContract.yousign_signature_request_id && (
                      <div>
                        <span className="text-[var(--ink-muted)] block text-[10px]">Yousign Sandbox</span>
                        <span className="font-mono text-[10px] text-[var(--ink-subtle)] truncate block">
                          {latestContract.yousign_signature_request_id.slice(0, 14)}...
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--border)]">
                    <button
                      type="button"
                      onClick={() => handleDownloadPdf(latestContract.id)}
                      disabled={isDownloadingPdf}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                    >
                      {isDownloadingPdf ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      <span>Télécharger PDF Spécimen</span>
                    </button>

                    {latestContract.status !== "SIGNED" && latestContract.status !== "WITHDRAWN" && (
                      <button
                        type="button"
                        onClick={() => handleSimulateSign(latestContract.id)}
                        disabled={isSimulatingSign}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] hover:bg-[var(--color-teal-soft)]/80 text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                      >
                        {isSimulatingSign ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                        )}
                        <span>Simuler Signature (Sandbox)</span>
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
                    Aucun contrat actif pour ce prospect. Générez le contrat SPÉCIMEN avec les données CRM réelles et la transparence AI Act.
                  </p>
                  <button
                    type="button"
                    onClick={handleGenerateContract}
                    disabled={isGeneratingContract}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                  >
                    {isGeneratingContract ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5" />
                    )}
                    <span>Générer le contrat SPÉCIMEN</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Product Fit & Energy Profile */}
          <div className="space-y-3 pt-2">
            <h3 className="text-xs font-bold text-[var(--ink)] tracking-tight uppercase">
              {t("leads.drawer.profileTitle")}
            </h3>

            <div className="grid grid-cols-2 gap-2.5">
              <div className={`p-3 rounded-[0.75rem] border ${hasEv ? "bg-[var(--color-motion-soft)] border-[var(--color-motion-border)]" : "bg-[var(--surface-hover)] border-[var(--border)]"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Zap className={`w-3.5 h-3.5 ${hasEv ? "text-[var(--color-motion)]" : "text-[var(--ink-subtle)]"}`} />
                  <span className="font-semibold text-[11px] text-[var(--ink)]">{t("leads.drawer.productFit.ev")}</span>
                </div>
                <p className="text-[10px] text-[var(--ink-muted)] leading-normal">
                  {hasEv ? t("leads.drawer.productFit.evPitch") : "Pas de VE déclaré"}
                </p>
              </div>

              <div className={`p-3 rounded-[0.75rem] border ${hasHeatPump ? "bg-[var(--color-teal-soft)] border-[var(--color-teal-soft-border)]" : "bg-[var(--surface-hover)] border-[var(--border)]"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Flame className={`w-3.5 h-3.5 ${hasHeatPump ? "text-[var(--color-teal-text)]" : "text-[var(--ink-subtle)]"}`} />
                  <span className="font-semibold text-[11px] text-[var(--ink)]">{t("leads.drawer.productFit.heatPump")}</span>
                </div>
                <p className="text-[10px] text-[var(--ink-muted)] leading-normal">
                  {hasHeatPump ? t("leads.drawer.productFit.heatPumpPitch") : "Chauffage classique"}
                </p>
              </div>

              <div className={`p-3 rounded-[0.75rem] border ${hasSolar ? "bg-amber-500/10 border-amber-500/30" : "bg-[var(--surface-hover)] border-[var(--border)]"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Sun className={`w-3.5 h-3.5 ${hasSolar ? "text-amber-500" : "text-[var(--ink-subtle)]"}`} />
                  <span className="font-semibold text-[11px] text-[var(--ink)]">{t("leads.drawer.productFit.solar")}</span>
                </div>
                <p className="text-[10px] text-[var(--ink-muted)] leading-normal">
                  {hasSolar ? t("leads.drawer.productFit.solarPitch") : "Sans panneaux solaires"}
                </p>
              </div>

              <div className={`p-3 rounded-[0.75rem] border ${hasBattery ? "bg-purple-500/10 border-purple-500/30" : "bg-[var(--surface-hover)] border-[var(--border)]"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Battery className={`w-3.5 h-3.5 ${hasBattery ? "text-purple-500" : "text-[var(--ink-subtle)]"}`} />
                  <span className="font-semibold text-[11px] text-[var(--ink)]">{t("leads.drawer.productFit.battery")}</span>
                </div>
                <p className="text-[10px] text-[var(--ink-muted)] leading-normal">
                  {hasBattery ? t("leads.drawer.productFit.batteryPitch") : "Sans batterie"}
                </p>
              </div>
            </div>
          </div>

          {/* Activity Feed for this lead */}
          <div className="space-y-3 pt-2">
            <h3 className="text-xs font-bold text-[var(--ink)] tracking-tight uppercase flex items-center gap-2">
              <ActivityIcon className="w-3.5 h-3.5 text-[var(--color-teal)]" />
              <span>{t("leads.drawer.activityTitle")}</span>
            </h3>

            {isDetailLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : detailData?.activities && detailData.activities.length > 0 ? (
              <div className="space-y-2 border-l-2 border-[var(--border)] ml-2 pl-3">
                {detailData.activities.map((act) => (
                  <div key={act.id} className="relative text-xs space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[var(--ink)]">
                        {act.type}
                      </span>
                      <span className="text-[10px] text-[var(--ink-subtle)] font-mono">
                        {new Date(act.created_at).toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    {act.details && (
                      <p className="text-[11px] text-[var(--ink-muted)]">{act.details}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--ink-muted)] italic">
                Aucune activité récente enregistrée pour ce prospect.
              </p>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
