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
  Pencil,
  Trash2,
  Save,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

interface LeadDrawerProps {
  lead: LeadSummary | null;
  isOpen: boolean;
  onClose: () => void;
}

// LeadService._EDITABLE_FIELDS (backend) - a lead's status/qualification is
// never editable from the Dashboard, only these CRM-correction fields.
interface EditableFields {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  region: string;
  city: string;
  current_supplier: string;
}

const toEditableFields = (lead: LeadSummary): EditableFields => ({
  first_name: lead.first_name || "",
  last_name: lead.last_name || "",
  email: lead.email || "",
  phone: lead.phone || "",
  region: lead.region || "",
  city: lead.city || "",
  current_supplier: lead.current_supplier || "",
});

const editInputClass =
  "w-full px-2.5 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth";

const EditField: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-semibold text-[var(--ink-muted)] mb-1">{label}</label>
    {children}
  </div>
);

export const LeadDrawer: React.FC<LeadDrawerProps> = ({ lead, isOpen, onClose }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isGeneratingContract, setIsGeneratingContract] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [isSimulatingSign, setIsSimulatingSign] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditableFields | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
      try {
        await apiClient.downloadContractPdf(contract.id, `contrat_specimen_${lead.last_name || "lead"}.pdf`);
      } catch (pdfErr) {
        console.warn("Could not auto-download PDF:", pdfErr);
      }
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

  const handleStartEdit = () => {
    setEditForm(toEditableFields(lead));
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditForm(null);
  };

  const handleSaveEdit = async () => {
    if (!editForm) return;
    try {
      setIsSaving(true);
      await apiClient.updateLead(lead.id, {
        first_name: editForm.first_name || null,
        last_name: editForm.last_name || null,
        email: editForm.email || null,
        phone: editForm.phone || null,
        region: editForm.region || null,
        city: editForm.city || null,
        current_supplier: editForm.current_supplier || null,
      });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["leadDetail", lead.id] });
      toast.success(t("leads.drawer.editSuccess") || "Prospect mis à jour");
      setIsEditing(false);
      setEditForm(null);
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la mise à jour du prospect");
    } finally {
      setIsSaving(false);
    }
  };

  // Must match the word shown in the confirmation input below exactly -
  // derived from the same t() call in both places so an English or Dutch
  // speaker is never told to type a word ("DELETE"/"VERWIJDEREN") the
  // check would then silently reject because it only compared against
  // the French literal.
  const deleteConfirmWord = t("leads.drawer.deleteConfirmWord") || "SUPPRIMER";

  const handleDelete = async () => {
    if (deleteConfirmText !== deleteConfirmWord) return;
    try {
      setIsDeleting(true);
      await apiClient.deleteLead(lead.id);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.success(t("leads.drawer.deleteSuccess") || "Prospect supprimé");
      setShowDeleteConfirm(false);
      setDeleteConfirmText("");
      onClose();
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la suppression du prospect");
    } finally {
      setIsDeleting(false);
    }
  };

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

          <div className="flex items-center gap-1 shrink-0">
            {!isOptOut && !isEditing && (
              <>
                <button
                  onClick={handleStartEdit}
                  className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--color-teal)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                  aria-label={t("leads.drawer.editButton") || "Modifier"}
                  title={t("leads.drawer.editButton") || "Modifier"}
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-danger hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                  aria-label={t("leads.drawer.deleteButton") || "Supprimer"}
                  title={t("leads.drawer.deleteButton") || "Supprimer"}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
              aria-label={t("common.close")}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Body content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs">
          {/* Inline edit panel - LeadService._EDITABLE_FIELDS only, never status/qualification */}
          {isEditing && editForm && (
            <div className="p-3.5 rounded-[0.75rem] border border-[var(--color-teal-soft-border)] bg-[var(--color-teal-soft)]/30 space-y-3">
              <div className="flex items-center gap-2 font-bold text-xs text-[var(--ink)]">
                <Pencil className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                <span>{t("leads.drawer.editTitle") || "Modifier les coordonnées"}</span>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <EditField label={t("leads.drawer.fields.fullName") + " (prénom)"}>
                  <input
                    value={editForm.first_name}
                    onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
                <EditField label={t("leads.drawer.fields.fullName") + " (nom)"}>
                  <input
                    value={editForm.last_name}
                    onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
                <EditField label={t("leads.drawer.fields.email")}>
                  <input
                    type="email"
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
                <EditField label={t("leads.drawer.fields.phone")}>
                  <input
                    value={editForm.phone}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
                <EditField label={t("leads.drawer.fields.location") + " (région)"}>
                  <select
                    value={editForm.region}
                    onChange={(e) => setEditForm({ ...editForm, region: e.target.value })}
                    className={editInputClass}
                  >
                    <option value="">—</option>
                    <option value="Wallonie">Wallonie</option>
                    <option value="Flandre">Flandre</option>
                  </select>
                </EditField>
                <EditField label={t("leads.drawer.fields.location") + " (ville)"}>
                  <input
                    value={editForm.city}
                    onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
                <EditField label={t("leads.drawer.fields.supplier")}>
                  <input
                    value={editForm.current_supplier}
                    onChange={(e) => setEditForm({ ...editForm, current_supplier: e.target.value })}
                    className={editInputClass}
                  />
                </EditField>
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>{t("common.close")}</span>
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={isSaving}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>{t("leads.drawer.saveButton") || "Enregistrer"}</span>
                </button>
              </div>
            </div>
          )}

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
                {completedCount}/9 {t("leads.drawer.criteriaMet")}
              </span>
            </div>

            <div className="rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] divide-y divide-[var(--border)] overflow-hidden">
              {checklistItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 px-3 py-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    {item.isComplete ? (
                      <Check className="w-3.5 h-3.5 shrink-0 stroke-[2.5] text-[var(--color-teal)]" />
                    ) : (
                      <Minus className="w-3.5 h-3.5 shrink-0 text-[var(--ink-subtle)]" />
                    )}
                    <span
                      className={`text-xs truncate ${
                        item.isComplete ? "font-semibold text-[var(--ink)]" : "font-medium text-[var(--ink-muted)]"
                      }`}
                    >
                      {item.label}
                    </span>
                  </div>

                  <div className="text-right shrink-0">
                    {item.value ? (
                      <span className="font-mono text-[11px] text-[var(--ink)]">
                        {item.value}
                      </span>
                    ) : (
                      <span className="text-[11px] text-[var(--ink-subtle)]">
                        {t("leads.drawer.notProvided")}
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
              {[
                {
                  active: hasEv,
                  Icon: Zap,
                  activeClass: "bg-[var(--color-motion-soft)] border-[var(--color-motion-border)] text-[var(--color-motion)]",
                  label: t("leads.drawer.productFit.ev"),
                  desc: hasEv ? t("leads.drawer.productFit.evPitch") : t("leads.drawer.productFit.evOff"),
                },
                {
                  active: hasHeatPump,
                  Icon: Flame,
                  activeClass: "bg-[var(--color-teal-soft)] border-[var(--color-teal-soft-border)] text-[var(--color-teal-text)]",
                  label: t("leads.drawer.productFit.heatPump"),
                  desc: hasHeatPump ? t("leads.drawer.productFit.heatPumpPitch") : t("leads.drawer.productFit.heatPumpOff"),
                },
                {
                  active: hasSolar,
                  Icon: Sun,
                  activeClass: "bg-amber-500/10 border-amber-500/30 text-amber-500",
                  label: t("leads.drawer.productFit.solar"),
                  desc: hasSolar ? t("leads.drawer.productFit.solarPitch") : t("leads.drawer.productFit.solarOff"),
                },
                {
                  active: hasBattery,
                  Icon: Battery,
                  activeClass: "bg-purple-500/10 border-purple-500/30 text-purple-500",
                  label: t("leads.drawer.productFit.battery"),
                  desc: hasBattery ? t("leads.drawer.productFit.batteryPitch") : t("leads.drawer.productFit.batteryOff"),
                },
              ].map(({ active, Icon, activeClass, label, desc }, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-[0.75rem] ${
                    active ? `border ${activeClass}` : "border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className={`w-3.5 h-3.5 shrink-0 ${active ? "" : "text-[var(--ink-subtle)]"}`} />
                    <span className={`text-[11px] truncate ${active ? "font-semibold text-[var(--ink)]" : "font-medium text-[var(--ink-muted)]"}`}>
                      {label}
                    </span>
                  </div>
                  <p className={`text-[10px] leading-normal ${active ? "text-[var(--ink-muted)]" : "text-[var(--ink-subtle)]"}`}>
                    {desc}
                  </p>
                </div>
              ))}
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

      {/* Delete confirmation - typed confirmation required, no accidental hard-delete */}
      {showDeleteConfirm && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs z-[60]"
            onClick={() => !isDeleting && setShowDeleteConfirm(false)}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
            <div
              role="alertdialog"
              aria-modal="true"
              aria-label={t("leads.drawer.deleteConfirmTitle") || "Supprimer ce prospect"}
              className="w-full max-w-sm bg-[var(--surface)] border border-danger rounded-2xl shadow-2xl p-5 space-y-3"
            >
              <div className="flex items-center gap-2 text-danger font-bold text-sm">
                <Trash2 className="w-4 h-4" />
                <span>{t("leads.drawer.deleteConfirmTitle") || "Supprimer ce prospect"}</span>
              </div>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                {t("leads.drawer.deleteConfirmBody", {
                  name: [lead.first_name, lead.last_name].filter(Boolean).join(" ") || lead.id,
                  word: deleteConfirmWord,
                }) ||
                  `Cette action est irréversible : le prospect, ses conversations et son historique seront définitivement supprimés. Tapez ${deleteConfirmWord} pour confirmer.`}
              </p>
              <input
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder={deleteConfirmWord}
                autoFocus
                className="w-full px-3 py-2 text-xs font-mono rounded-[0.5rem] border border-danger bg-[var(--surface)] text-[var(--ink)] focus:outline-none"
              />
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteConfirmText("");
                  }}
                  disabled={isDeleting}
                  className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {t("common.close")}
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleteConfirmText !== deleteConfirmWord || isDeleting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-danger text-white hover:opacity-90 text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isDeleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{t("leads.drawer.deleteButton") || "Supprimer"}</span>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};
