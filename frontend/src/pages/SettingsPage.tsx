import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
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
} from "lucide-react";
import { toast } from "sonner";

export const SettingsPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [showApiKey, setShowApiKey] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSigning, setIsSigning] = useState(false);
  const [lastGeneratedContract, setLastGeneratedContract] = useState<{ id: string; product: string } | null>(null);

  const storedApiKey = localStorage.getItem("sophie_api_key") || "sk-live-ecofix-demo-key-2026";
  const maskedApiKey = storedApiKey.slice(0, 7) + "••••••••••••••••" + storedApiKey.slice(-4);

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

  const handleNonLiveChannelClick = (channelName: string) => {
    toast.info(t("toast.phase2Title"), {
      description: `${channelName} : ${t("toast.phase2Desc")}`,
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
      setLastGeneratedContract({ id: contract.id, product: contract.product });
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
      toast.success("Signature Yousign Sandbox simulée avec succès ! Statut client activé.");
    } catch (err: any) {
      toast.error(err?.message || "Erreur lors de la simulation de signature.");
    } finally {
      setIsSigning(false);
    }
  };

  const handleCopyApiKey = () => {
    navigator.clipboard.writeText(storedApiKey);
    toast.success(t("toast.copied"));
  };

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem("i18nextLng", lang);
    toast.success(`Langue changée : ${lang.toUpperCase()}`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-4xl">
      {/* Header */}
      <div className="pb-1">
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
          {t("settingsPage.title")}
        </h1>
        <p className="text-xs text-[var(--ink-muted)] mt-1">
          {t("settingsPage.subtitle")}
        </p>
      </div>

      <div className="space-y-5">
        {/* Card 1: Channels status (Honest channels) */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-[var(--color-teal-text)]" />
                <CardTitle>{t("settingsPage.channelsTitle")}</CardTitle>
              </div>
              <Badge variant="phase2">Multicanal</Badge>
            </div>
            <CardDescription>{t("settingsPage.channelsDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Telegram - LIVE */}
              <div className="p-3.5 rounded-[0.75rem] border border-[var(--color-teal-soft-border)] bg-[var(--color-teal-soft)]/40 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-[var(--color-teal)] text-white flex items-center justify-center">
                    <Send className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-xs text-[var(--ink)] block">
                      {t("settingsPage.telegram")}
                    </span>
                    <span className="text-[10px] text-[var(--ink-muted)]">Bot @EcofixSalesBot</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-teal-text)] font-mono">
                  <span className="w-2 h-2 rounded-full bg-[var(--color-teal)] animate-pulse" />
                  <span>{t("settingsPage.telegramStatus")}</span>
                </div>
              </div>

              {/* WhatsApp - READY */}
              <button
                type="button"
                onClick={() => handleNonLiveChannelClick("WhatsApp Business")}
                className="p-3.5 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] hover:border-amber-500/50 flex items-center justify-between transition-smooth cursor-pointer text-left group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-emerald-600/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-xs text-[var(--ink)] block group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-smooth">
                      {t("settingsPage.whatsApp")}
                    </span>
                    <span className="text-[10px] text-[var(--ink-muted)]">Twilio Sandbox prêt</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400 font-mono">
                  <span className="text-sm">◐</span>
                  <span>{t("settingsPage.whatsAppStatus")}</span>
                </div>
              </button>

              {/* Voice - READY */}
              <button
                type="button"
                onClick={() => handleNonLiveChannelClick("Twilio Voice")}
                className="p-3.5 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] hover:border-amber-500/50 flex items-center justify-between transition-smooth cursor-pointer text-left group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-blue-600/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                    <Phone className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-xs text-[var(--ink)] block group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-smooth">
                      {t("settingsPage.voice")}
                    </span>
                    <span className="text-[10px] text-[var(--ink-muted)]">Appels entrants / sortants</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400 font-mono">
                  <span className="text-sm">◐</span>
                  <span>{t("settingsPage.voiceStatus")}</span>
                </div>
              </button>

              {/* SMS - PLANNED */}
              <button
                type="button"
                onClick={() => handleNonLiveChannelClick("SMS Twilio")}
                className="p-3.5 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] hover:border-[var(--ink-subtle)] flex items-center justify-between transition-smooth cursor-pointer text-left group opacity-75"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-[var(--border)] text-[var(--ink-subtle)] flex items-center justify-center">
                    <Radio className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold text-xs text-[var(--ink)] block">
                      {t("settingsPage.sms")}
                    </span>
                    <span className="text-[10px] text-[var(--ink-muted)]">Relance SMS</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--ink-subtle)] font-mono">
                  <span className="text-sm">○</span>
                  <span>{t("settingsPage.smsStatus")}</span>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Contract Section (Real Generator with Qualified Leads Dropdown) */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[var(--color-teal-text)]" />
                <CardTitle>{t("settingsPage.contractTitle")}</CardTitle>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] font-semibold border border-[var(--color-teal-soft-border)]">
                Données CRM Réelles • AI Act Preamble
              </span>
            </div>
            <CardDescription>{t("settingsPage.contractDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] text-xs text-[var(--ink-muted)] space-y-1.5">
              <span className="font-bold text-[var(--ink)] block">
                Génération de Contrat d'Énergie Réel (SPÉCIMEN) :
              </span>
              <p className="leading-relaxed text-[11px]">
                Sélectionnez un prospect qualifié par Sophie. Le moteur extrait ses données CRM (nom, adresse, EAN 18 chiffres, GRD Fluvius/ORES), applique la règle de produit (Motion si VE/pompe/batterie sinon Flexy), injecte la mention AI Act verbatim et produit le PDF juridique avec bordereau de rétractation de 14 jours.
              </p>
            </div>

            {/* Dropdown of qualified leads */}
            <div className="space-y-2 pt-1">
              <label className="text-xs font-semibold text-[var(--ink)] block">
                Sélectionner un prospect qualifié :
              </label>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <select
                  value={targetLeadId}
                  onChange={(e) => setSelectedLeadId(e.target.value)}
                  className="flex-1 px-3 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)] cursor-pointer"
                >
                  {qualifiedLeads.length === 0 ? (
                    <option value="">Aucun prospect qualifié disponible</option>
                  ) : (
                    qualifiedLeads.map((l) => (
                      <option key={l.id} value={l.id}>
                        {[l.first_name, l.last_name].filter(Boolean).join(" ") || "Prospect"} — {l.city || l.region || "Belgique"} ({l.status})
                      </option>
                    ))
                  )}
                </select>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleGenerateContract}
                  disabled={isGenerating || !targetLeadId}
                  className="cursor-pointer shrink-0"
                >
                  {isGenerating ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 mr-1" />
                  )}
                  <span>{t("settingsPage.generateContract")}</span>
                </Button>
              </div>
            </div>

            {/* If a contract was just created, offer instant Yousign simulation */}
            {lastGeneratedContract && (
              <div className="p-3 rounded-[0.5rem] bg-[var(--color-teal-soft)]/50 border border-[var(--color-teal-soft-border)] flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs">
                  <span className="font-bold text-[var(--color-teal-text)] block">
                    Contrat {lastGeneratedContract.product} prêt pour signature
                  </span>
                  <span className="text-[11px] text-[var(--ink-muted)]">
                    ID: {lastGeneratedContract.id}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSimulateYousign}
                  disabled={isSigning}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {isSigning ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  <span>Simuler Signature (Yousign Sandbox)</span>
                </button>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[var(--border)]">
              <a
                href="/contrat-specimen.pdf"
                download="contrat-specimen-ecofix.pdf"
                className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold rounded-[0.5rem] bg-lavender text-lavender-ink hover:bg-lavender-hover transition-smooth shadow-xs gap-1.5 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{t("settingsPage.downloadSpecimen")}</span>
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Card 3: API Key Display */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>{t("settingsPage.apiKeyTitle")}</CardTitle>
            </div>
            <CardDescription>{t("settingsPage.apiKeyDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 max-w-md">
              <div className="relative flex-1">
                <input
                  type={showApiKey ? "text" : "password"}
                  readOnly
                  value={storedApiKey}
                  className="w-full pl-3 pr-9 py-1.5 text-xs font-mono rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] focus:outline-none select-all"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)] hover:text-[var(--ink)] cursor-pointer"
                  title={showApiKey ? "Masquer" : "Révéler"}
                >
                  {showApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>

              <Button variant="secondary" size="sm" onClick={handleCopyApiKey} className="shrink-0">
                <Copy className="w-3.5 h-3.5 mr-1" />
                <span>{t("common.copy")}</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Default Language Selector */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Languages className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>{t("settingsPage.languageTitle")}</CardTitle>
            </div>
            <CardDescription>{t("settingsPage.languageDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {[
                { code: "fr", label: "Français (FR)" },
                { code: "nl", label: "Nederlands (NL - u-vorm)" },
                { code: "en", label: "English (EN)" },
              ].map((lang) => {
                const isActive = i18n.language.startsWith(lang.code);
                return (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageChange(lang.code)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-[0.5rem] border transition-smooth cursor-pointer ${
                      isActive
                        ? "bg-[var(--color-navy)] text-[var(--color-teal)] border-white/10 shadow-xs"
                        : "bg-[var(--surface-hover)] border-[var(--border)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                    }`}
                  >
                    {lang.label}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
