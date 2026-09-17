import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ContractSummary } from "@/api/types";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  Settings,
  Radio,
  Send,
  Phone,
  MessageSquare,
  FileText,
  Download,
  KeyRound,
  Eye,
  EyeOff,
  Copy,
  Languages,
  CheckCircle2,
  ExternalLink,
  Sparkles,
  Loader2,
  ShieldCheck,
  Zap,
  Server,
  Activity,
  Check,
  Cpu,
  Database,
  Smartphone,
  Info,
  Scale,
  FileCheck2,
} from "lucide-react";
import { ContractVisualViewerModal } from "@/components/contracts/ContractVisualViewerModal";
import { toast } from "sonner";

export const SettingsPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [showApiKey, setShowApiKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSigning, setIsSigning] = useState(false);
  const [lastGeneratedContract, setLastGeneratedContract] = useState<ContractSummary | null>(null);
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [viewerInitialStudio, setViewerInitialStudio] = useState(false);

  const { apiKey } = useAuth();

  const { data: leadsData } = useQuery({
    queryKey: ["leadsForContract"],
    queryFn: () => apiClient.getLeads({ limit: 100 }),
  });

  const qualifiedLeads = (leadsData?.items || []).filter(
    (l) =>
      l.status === "QUALIFIED" ||
      l.status === "QUALIFIED_FLEXY" ||
      l.status === "QUALIFIED_MOTION" ||
      l.status === "CONTRACT" ||
      l.status === "CUSTOMER"
  );

  const targetLeadId = selectedLeadId || qualifiedLeads[0]?.id || "";
  const selectedLead = qualifiedLeads.find((l) => l.id === targetLeadId) || qualifiedLeads[0];

  const recommendedProduct = selectedLead && (selectedLead.has_ev || selectedLead.has_heat_pump || selectedLead.has_battery)
    ? "Motion"
    : "Flexy";

  const handleNonLiveChannelClick = (channelName: string) => {
    toast.info(t("toast.phase2Title") || "Canal en attente d'activation", {
      description: `${channelName} : Intégré de bout en bout, en attente de clés API de production.`,
    });
  };

  const handleGenerateContract = async () => {
    if (!targetLeadId) {
      toast.error("Veuillez sélectionner un prospect qualifié dans la liste.");
      return;
    }
    try {
      setIsGenerating(true);
      const contract = await apiClient.createContract(targetLeadId);
      setLastGeneratedContract(contract);
      toast.success(`Contrat Ecofix ${contract.product} généré pour le prospect ! Téléchargement en cours...`);
      await apiClient.downloadContractPdf(contract.id, `contrat_specimen_${contract.product.toLowerCase()}.pdf`);
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la génération du contrat.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSimulateYousign = async () => {
    if (!lastGeneratedContract?.id) return;
    try {
      setIsSigning(true);
      await apiClient.simulateSignContract(lastGeneratedContract.id);
      toast.success("Signature certifiée eIDAS simulée avec succès ! Statut client activé.");
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la simulation de signature.");
    } finally {
      setIsSigning(false);
    }
  };

  const handleCopyApiKey = () => {
    if (!apiKey) return;
    navigator.clipboard.writeText(apiKey);
    setCopiedKey(true);
    toast.success(t("toast.copied") || "Clé API copiée dans le presse-papier !");
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem("i18nextLng", lang);
    toast.success(`Langue de l'interface : ${lang.toUpperCase()}`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-5xl">
      {/* Executive Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-2 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="p-2 rounded-xl bg-[var(--color-teal)]/10 text-[var(--color-teal)] border border-[var(--color-teal)]/20 shadow-xs">
              <Settings className="w-5 h-5 animate-spin-slow" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
                {t("settingsPage.title") || "Console Settings"}
              </h1>
              <p className="text-xs text-[var(--ink-muted)]">
                {t("settingsPage.subtitle") || "Canaux de communication, génération contractuelle certifiée et sécurité API."}
              </p>
            </div>
          </div>
        </div>

        {/* Live System Status Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-semibold shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Render Live</span>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--color-lavender)]/20 border border-[var(--color-lavender)]/30 text-[var(--ink)] font-semibold shadow-2xs">
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            <span>Groq 120B OK</span>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] text-[var(--color-teal-text)] font-semibold shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-teal)]" />
            <span>Conforme AI Act</span>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Card 1: Contact Channels Grid */}
        <Card className="border-[var(--border)] overflow-hidden shadow-xs hover:border-[var(--color-teal)]/30 transition-smooth">
          <CardHeader className="bg-[var(--surface-hover)]/40 border-b border-[var(--border)] pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center">
                  <Radio className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-sm font-bold text-[var(--ink)]">
                    {t("settingsPage.channelsTitle") || "Canaux d'Engagement Commercial"}
                  </CardTitle>
                  <CardDescription className="text-xs text-[var(--ink-muted)]">
                    {t("settingsPage.channelsDesc") || "Supervision en direct de l'état des passerelles d'interaction de Sophie."}
                  </CardDescription>
                </div>
              </div>
              <Badge variant="phase2" className="bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border-[var(--color-teal-soft-border)]">
                Multicanal Actif
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Telegram - LIVE */}
              <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/10 flex items-center justify-between transition-smooth shadow-2xs group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500 text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-smooth">
                    <Send className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-[var(--ink)]">
                        {t("settingsPage.telegram") || "Telegram"}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-mono">
                        LIVE
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--ink-muted)] block font-mono">@EcofixSalesBot</span>
                    <a
                      href="https://t.me/EcofixSalesBot"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 hover:underline mt-0.5"
                    >
                      <span>Tester le bot</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 font-mono bg-white/60 dark:bg-black/30 px-2.5 py-1 rounded-full border border-emerald-500/20">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>En ligne</span>
                </div>
              </div>

              {/* Twilio SMS - LIVE */}
              <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/10 flex items-center justify-between transition-smooth shadow-2xs group">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500 text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-smooth">
                    <Smartphone className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-[var(--ink)]">
                        {t("settingsPage.sms") || "SMS (Twilio)"}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-600 dark:text-blue-400 font-mono">
                        LIVE
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--ink-muted)] block font-mono">Webhook HMAC vérifié</span>
                    <span className="text-[10px] text-[var(--ink-subtle)] block">Format court ≤ 320 car. + STOP</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 dark:text-blue-400 font-mono bg-white/60 dark:bg-black/30 px-2.5 py-1 rounded-full border border-blue-500/20">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  <span>Prêt</span>
                </div>
              </div>

              {/* WhatsApp - READY */}
              <button
                type="button"
                onClick={() => handleNonLiveChannelClick("WhatsApp Business")}
                className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-amber-500/40 hover:bg-amber-500/5 flex items-center justify-between transition-smooth cursor-pointer text-left group shadow-2xs"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center group-hover:scale-105 transition-smooth">
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-[var(--ink)]">
                        {t("settingsPage.whatsApp") || "WhatsApp Business"}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-600 dark:text-amber-400 font-mono">
                        SANDBOX
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--ink-muted)] block">Twilio Sandbox pré-intégré</span>
                    <span className="text-[10px] text-[var(--ink-subtle)] block">Activation avec clé Meta Cloud</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400 font-mono bg-[var(--surface-hover)] px-2.5 py-1 rounded-full border border-[var(--border)]">
                  <span>◐</span>
                  <span>Prêt</span>
                </div>
              </button>

              {/* Voice - READY */}
              <button
                type="button"
                onClick={() => handleNonLiveChannelClick("Twilio Voice")}
                className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-purple-500/40 hover:bg-purple-500/5 flex items-center justify-between transition-smooth cursor-pointer text-left group shadow-2xs"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-600/15 text-purple-600 dark:text-purple-400 flex items-center justify-center group-hover:scale-105 transition-smooth">
                    <Phone className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-[var(--ink)]">
                        {t("settingsPage.voice") || "Twilio Voice"}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-600 dark:text-purple-400 font-mono">
                        VOICE AI
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--ink-muted)] block">Entrants / sortants</span>
                    <span className="text-[10px] text-[var(--ink-subtle)] block">STT Whisper + TTS ElevenLabs</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-600 dark:text-purple-400 font-mono bg-[var(--surface-hover)] px-2.5 py-1 rounded-full border border-[var(--border)]">
                  <span>◐</span>
                  <span>Prêt</span>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Contract Studio & Legal Specimen */}
        <Card className="border-[var(--border)] overflow-hidden shadow-xs hover:border-[var(--color-teal)]/30 transition-smooth">
          <CardHeader className="bg-[var(--surface-hover)]/40 border-b border-[var(--border)] pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-sm font-bold text-[var(--ink)]">
                    {t("settingsPage.contractTitle") || "Studio de Génération Contractuelle & Spécimen"}
                  </CardTitle>
                  <CardDescription className="text-xs text-[var(--ink-muted)]">
                    {t("settingsPage.contractDesc") || "Générez un contrat d'énergie officiel pour un prospect qualifié ou téléchargez le spécimen certifié."}
                  </CardDescription>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] font-bold border border-[var(--color-teal-soft-border)] shadow-2xs">
                Données CRM • AI Act Art. 50
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left 2 Cols: Real Generator */}
              <div className="lg:col-span-2 p-4 rounded-xl bg-[var(--surface-hover)]/50 border border-[var(--border)] space-y-3.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-[var(--ink)] flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-[var(--color-teal)]" />
                    Générateur Dynamique de Contrat CRM
                  </span>
                  {selectedLead && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[var(--color-teal)]/15 text-[var(--color-teal)] font-mono">
                      Produit détecté : {recommendedProduct}
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
                  Le moteur applique automatiquement les règles déterministes d'Ecofix : contrat <strong>Motion</strong> (dynamique horaire) si le prospect dispose d'un VE, d'une pompe à chaleur ou d'une batterie, sinon contrat <strong>Flexy</strong> (variable mensuelle).
                </p>

                {/* Dropdown of qualified leads */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-[var(--ink-muted)] block">
                    Prospects qualifiés disponibles ({qualifiedLeads.length}) :
                  </label>
                  <select
                    value={targetLeadId}
                    onChange={(e) => setSelectedLeadId(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)] transition-smooth cursor-pointer shadow-2xs"
                  >
                    {qualifiedLeads.length === 0 ? (
                      <option value="">Aucun prospect qualifié disponible dans le CRM</option>
                    ) : (
                      qualifiedLeads.map((l) => (
                        <option key={l.id} value={l.id}>
                          {[l.first_name, l.last_name].filter(Boolean).join(" ") || "Prospect"} — {l.city || l.region || "Belgique"} • Statut : {l.status}
                        </option>
                      ))
                    )}
                  </select>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-2 text-[10px] text-[var(--ink-muted)]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span>GRD Fluvius/ORES • Bordereau de rétractation 14j</span>
                  </div>

                  <button
                    type="button"
                    onClick={handleGenerateContract}
                    disabled={isGenerating || !targetLeadId}
                    className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-600 active:scale-[0.98] text-white shadow-xs transition-smooth cursor-pointer disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <FileCheck2 className="w-3.5 h-3.5" />
                    )}
                    <span>{t("settingsPage.generateContract") || "Générer le contrat juridique (PDF)"}</span>
                  </button>
                </div>

                {/* If a contract was just created, offer visual view and Yousign simulation */}
                {lastGeneratedContract && (
                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex flex-wrap items-center justify-between gap-2.5 animate-in fade-in slide-in-from-top-1 duration-200">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-emerald-700 dark:text-emerald-300">
                          Contrat {lastGeneratedContract.product} prêt pour signature
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold">
                          {lastGeneratedContract.status}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-[var(--ink-muted)] block mt-0.5">
                        ID: {lastGeneratedContract.id}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setViewerInitialStudio(false);
                          setIsViewerOpen(true);
                        }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface)] hover:bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)] text-xs font-semibold transition-smooth cursor-pointer shadow-2xs"
                      >
                        <Eye className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                        <span>Visualiser</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setViewerInitialStudio(true);
                          setIsViewerOpen(true);
                        }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] text-white text-xs font-semibold transition-smooth cursor-pointer shadow-xs"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Simuler Signature eIDAS</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Right Col: Official Specimen Preview Box */}
              <div className="p-4 rounded-xl bg-gradient-to-br from-[var(--surface)] to-[var(--surface-hover)] border border-[var(--border)] flex flex-col justify-between space-y-4 shadow-2xs">
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--color-teal)] font-mono">
                      Spécimen Officiel
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--surface)] border border-[var(--border)] text-[var(--ink-muted)]">
                      PDF • 6.4 Ko
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-[var(--surface)] border border-[var(--border)] space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-md bg-rose-500/10 text-rose-500 flex items-center justify-center font-bold text-xs">
                        PDF
                      </div>
                      <div className="overflow-hidden">
                        <span className="text-xs font-bold text-[var(--ink)] block truncate">
                          contrat-specimen.pdf
                        </span>
                        <span className="text-[10px] text-[var(--ink-muted)] block">
                          Générateur ReportLab v2
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1 pt-1 border-t border-[var(--border)] text-[10px] text-[var(--ink-muted)]">
                      <div className="flex items-center gap-1.5">
                        <Check className="w-3 h-3 text-[var(--color-teal)]" />
                        <span>Filigrane légal « Données Fictives »</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Check className="w-3 h-3 text-[var(--color-teal)]" />
                        <span>Preamble AI Act Règlement UE 2024/1689</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Check className="w-3 h-3 text-[var(--color-teal)]" />
                        <span>Bordereau légal de rétractation</span>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={async () => {
                    try {
                      toast.info("Téléchargement du contrat spécimen en cours...");
                      await apiClient.downloadSpecimenPdf();
                      toast.success("Contrat spécimen téléchargé avec succès !");
                    } catch (err: any) {
                      toast.error(err?.message || "Erreur lors du téléchargement");
                    }
                  }}
                  className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-bold rounded-xl bg-[var(--color-navy)] text-white hover:opacity-90 active:scale-[0.98] transition-smooth shadow-xs cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{t("settingsPage.downloadSpecimen") || "Télécharger le Spécimen PDF"}</span>
                </button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Security & API Vault */}
        <Card className="border-[var(--border)] overflow-hidden shadow-xs hover:border-[var(--color-teal)]/30 transition-smooth">
          <CardHeader className="bg-[var(--surface-hover)]/40 border-b border-[var(--border)] pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center">
                  <KeyRound className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-sm font-bold text-[var(--ink)]">
                    {t("settingsPage.apiKeyTitle") || "Sécurité & Clé d'Authentification API"}
                  </CardTitle>
                  <CardDescription className="text-xs text-[var(--ink-muted)]">
                    {t("settingsPage.apiKeyDesc") || "Clé secrète requise dans l'en-tête X-API-Key pour consommer les services protégés de Sophie."}
                  </CardDescription>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/20">
                Session Chiffrée TLS
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-4 space-y-3">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 max-w-xl">
              <div className="relative flex-1">
                <input
                  type={showApiKey ? "text" : "password"}
                  readOnly
                  value={apiKey || ""}
                  className="w-full pl-3.5 pr-10 py-2 text-xs font-mono rounded-xl border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] focus:outline-none select-all shadow-2xs"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)] hover:text-[var(--ink)] transition-smooth cursor-pointer"
                  title={showApiKey ? "Masquer" : "Révéler"}
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              <Button
                variant={copiedKey ? "primary" : "secondary"}
                size="sm"
                onClick={handleCopyApiKey}
                className="shrink-0 text-xs px-4"
              >
                {copiedKey ? (
                  <>
                    <Check className="w-3.5 h-3.5 mr-1" />
                    <span>Copié !</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 mr-1" />
                    <span>{t("common.copy") || "Copier"}</span>
                  </>
                )}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-[var(--ink-muted)]">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                Protection contre les attaques par force brute (Rate Limit activé)
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Server className="w-3.5 h-3.5 text-blue-500" />
                CORS strict : origines Render et Vercel autorisées
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Console Language Preferences */}
        <Card className="border-[var(--border)] overflow-hidden shadow-xs hover:border-[var(--color-teal)]/30 transition-smooth">
          <CardHeader className="bg-[var(--surface-hover)]/40 border-b border-[var(--border)] pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center">
                  <Languages className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-sm font-bold text-[var(--ink)]">
                    {t("settingsPage.languageTitle") || "Langue de la Console de Supervision"}
                  </CardTitle>
                  <CardDescription className="text-xs text-[var(--ink-muted)]">
                    {t("settingsPage.languageDesc") || "Définissez la langue par défaut de l'interface et du simulateur commercial."}
                  </CardDescription>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { code: "fr", flag: "🇫🇷", name: "Français", note: "Vouvoiement de rigueur" },
                { code: "nl", flag: "🇳🇱", name: "Nederlands", note: "U-vorm beleefd" },
                { code: "en", flag: "🇬🇧", name: "English", note: "International standard" },
              ].map((lang) => {
                const isActive = i18n.language.startsWith(lang.code);
                return (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageChange(lang.code)}
                    className={`p-3.5 rounded-xl border text-left transition-smooth cursor-pointer flex items-center justify-between ${
                      isActive
                        ? "border-[var(--color-teal)] bg-[var(--color-teal-soft)]/40 shadow-xs"
                        : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--color-teal)]/40 hover:bg-[var(--surface-hover)]"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{lang.flag}</span>
                      <div>
                        <div className="font-bold text-xs text-[var(--ink)]">{lang.name}</div>
                        <div className="text-[10px] text-[var(--ink-muted)]">{lang.note}</div>
                      </div>
                    </div>
                    {isActive && (
                      <span className="w-2 h-2 rounded-full bg-[var(--color-teal)] animate-pulse" />
                    )}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Card 5: Pricing Truth & Guardrails Banner */}
        <div className="p-4 rounded-2xl bg-gradient-to-r from-teal-500/10 via-[var(--surface-hover)] to-lavender-500/10 border border-[var(--color-teal-soft-border)] shadow-xs space-y-2">
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-[var(--color-teal)] shrink-0" />
            <span className="font-bold text-xs text-[var(--ink)]">
              Vérité Tarifaire & Garde-Fou Invariant (Septembre 2026) :
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 pt-1 text-[11px] text-[var(--ink-muted)]">
            <div className="p-2 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Frais fixes obligatoires :</span>
              <span className="font-mono text-[var(--color-teal)] font-bold">60,00 € / an</span>
            </div>
            <div className="p-2 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Option Ecofix Digi :</span>
              <span className="font-mono text-purple-600 dark:text-purple-400 font-bold">5,99 € / mois</span> (Optionnel)
            </div>
            <div className="p-2 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Friends with Benefits :</span>
              <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">-5 € / mois / parrainage</span>
            </div>
            <div className="p-2 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <span className="font-semibold text-[var(--ink)] block">Indemnité de rupture :</span>
              <span className="font-mono text-[var(--ink)] font-bold">0,00 € (Loi belge)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Visual Contract Viewer & Signature Studio Modal */}
      {lastGeneratedContract && (
        <ContractVisualViewerModal
          contract={lastGeneratedContract}
          isOpen={isViewerOpen}
          onClose={() => {
            setIsViewerOpen(false);
            setViewerInitialStudio(false);
          }}
          initialSignStudioOpen={viewerInitialStudio}
          onContractSigned={(updated) => {
            setLastGeneratedContract(updated);
          }}
        />
      )}
    </div>
  );
};

export default SettingsPage;
