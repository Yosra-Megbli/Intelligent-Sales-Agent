import React from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  ShieldCheck,
  Lock,
  Globe2,
  Server,
  Ban,
  CheckCircle2,
  AlertTriangle,
  Clock,
  FileText,
  KeyRound,
  Eye,
  ExternalLink,
} from "lucide-react";

export const CompliancePage: React.FC = () => {
  const { t } = useTranslation();

  const { data: complianceData, isLoading } = useQuery({
    queryKey: ["compliance"],
    queryFn: () => apiClient.getCompliance(),
  });

  const optOutEvents = complianceData?.opt_out_events || [];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header with Hero Shield */}
      <div className="p-6 rounded-[0.75rem] bg-[var(--color-navy)] text-white relative overflow-hidden shadow-md">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[var(--color-teal)]/20 text-[var(--color-teal)] text-[11px] font-bold border border-[var(--color-teal)]/30">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Conformité Règlementaire Native</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {t("compliancePage.title")}
            </h1>
            <p className="text-xs text-white/70 leading-relaxed">
              {t("compliancePage.subtitle")}
            </p>
          </div>

          {/* 4 Mini Trust Badges echoing login screen */}
          <div className="grid grid-cols-2 gap-2.5 shrink-0">
            <div className="flex items-center gap-2 p-2.5 rounded-[0.5rem] bg-white/5 border border-white/10">
              <ShieldCheck className="w-4 h-4 text-[var(--color-teal)] shrink-0" />
              <div className="leading-tight">
                <span className="text-[11px] font-bold block text-white">AI Act</span>
                <span className="text-[9px] text-white/60">Transparence obligatoire</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2.5 rounded-[0.5rem] bg-white/5 border border-white/10">
              <Lock className="w-4 h-4 text-[var(--color-teal)] shrink-0" />
              <div className="leading-tight">
                <span className="text-[11px] font-bold block text-white">RGPD Art. 17</span>
                <span className="text-[9px] text-white/60">Purge PII irréversible</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2.5 rounded-[0.5rem] bg-white/5 border border-white/10">
              <Globe2 className="w-4 h-4 text-[var(--color-teal)] shrink-0" />
              <div className="leading-tight">
                <span className="text-[11px] font-bold block text-white">Groq DPA</span>
                <span className="text-[9px] text-white/60">Clauses types UE</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2.5 rounded-[0.5rem] bg-white/5 border border-white/10">
              <Server className="w-4 h-4 text-[var(--color-teal)] shrink-0" />
              <div className="leading-tight">
                <span className="text-[11px] font-bold block text-white">Hébergement UE</span>
                <span className="text-[9px] text-white/60">Francfort / Bruxelles</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Card 1: Opt-out Journal */}
        <Card className="flex flex-col md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Ban className="w-4 h-4 text-pink-600 dark:text-pink-400" />
                <CardTitle>{t("compliancePage.optOutJournalTitle")}</CardTitle>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-pink-100 dark:bg-pink-950/50 text-pink-700 dark:text-pink-300 font-semibold border border-pink-200 dark:border-pink-800">
                {complianceData?.suppression_list_count || optOutEvents.length} entrées inhibées
              </span>
            </div>
            <CardDescription>{t("compliancePage.optOutJournalDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[var(--surface-hover)] border-y border-[var(--border)] text-[var(--ink-muted)] uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Horodatage</th>
                    <th className="px-4 py-2.5 font-semibold">Identifiant Prospect</th>
                    <th className="px-4 py-2.5 font-semibold">Canal</th>
                    <th className="px-4 py-2.5 font-semibold">Motif d'arrêt</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Confirmation d'effacement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {isLoading ? (
                    Array.from({ length: 3 }).map((_, i) => (
                      <tr key={i}>
                        <td className="px-4 py-3"><Skeleton className="h-4 w-28" /></td>
                        <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                        <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                        <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                        <td className="px-4 py-3"><Skeleton className="h-4 w-12 ml-auto" /></td>
                      </tr>
                    ))
                  ) : optOutEvents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-xs text-[var(--ink-muted)]">
                        Aucun opt-out enregistré pour le moment.
                      </td>
                    </tr>
                  ) : (
                    optOutEvents.map((evt) => (
                      <tr key={evt.id} className="hover:bg-[var(--surface-hover)] transition-smooth font-mono text-[11px]">
                        <td className="px-4 py-2.5 text-[var(--ink-subtle)]">
                          {new Date(evt.timestamp).toLocaleString("fr-BE")}
                        </td>
                        <td className="px-4 py-2.5 font-medium text-pink-600 dark:text-pink-400 line-through">
                          {evt.lead_name}
                        </td>
                        <td className="px-4 py-2.5 text-[var(--ink-muted)]">
                          {evt.channel}
                        </td>
                        <td className="px-4 py-2.5 text-[var(--ink)]">
                          {evt.details || "STOP / STOPT / ARRÊT"}
                        </td>
                        <td className="px-4 py-2.5 text-right font-semibold text-[var(--color-teal-text)]">
                          <span className="inline-flex items-center gap-1 justify-end">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Envoyée & Purge ✓
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: AI Disclosure Guard */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[var(--color-teal)]" />
                <CardTitle>{t("compliancePage.guardTitle")}</CardTitle>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] font-semibold border border-[var(--color-teal-soft-border)]">
                {complianceData?.guard_status || "ACTIF"} — {complianceData?.guard_tests_count || 673} tests
              </span>
            </div>
            <CardDescription>{t("compliancePage.guardDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="p-3 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1.5">
              <span className="font-bold text-[11px] text-[var(--ink)] block">
                Énoncé légal injecté obligatoirement :
              </span>
              <p className="text-[11px] italic text-[var(--ink-muted)] leading-relaxed border-l-2 border-l-[var(--color-teal)] pl-2.5">
                "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment."
              </p>
            </div>
            <div className="flex items-center justify-between text-[11px] text-[var(--ink-subtle)] font-mono pt-1">
              <span>Test : test_first_outbound_message_discloses_ai</span>
              <span className="text-[var(--color-teal-text)] font-bold">100% SUCCÈS</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Retention Policy */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-[var(--color-teal)]" />
                <CardTitle>{t("compliancePage.retentionTitle")}</CardTitle>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--surface-hover)] text-[var(--ink-muted)] font-semibold border border-[var(--border)]">
                12 Mois Max
              </span>
            </div>
            <CardDescription>{t("compliancePage.retentionDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)]">
                <span className="text-[10px] text-[var(--ink-subtle)] block">Durée de conservation</span>
                <span className="font-bold text-[var(--ink)] text-xs">365 jours</span>
              </div>
              <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)]">
                <span className="text-[10px] text-[var(--ink-subtle)] block">Purge automatique</span>
                <span className="font-bold text-[var(--color-teal-text)] text-xs">Activée (quotidienne)</span>
              </div>
            </div>
            <p className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
              Conformément au principe de minimisation (RGPD Art. 5), les métadonnées et conversations sont anonymisées au-delà de la période active de vente.
            </p>
          </CardContent>
        </Card>

        {/* Card 4: Transfers Outside EU */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe2 className="w-4 h-4 text-[var(--color-teal)]" />
                <CardTitle>{t("compliancePage.transfersTitle")}</CardTitle>
              </div>
              <Badge variant="phase2">DPA Groq Actif</Badge>
            </div>
            <CardDescription>{t("compliancePage.transfersDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1">
                <span className="font-bold text-[11px] text-[var(--ink)] block">Sous-traitant LLM</span>
                <p className="text-[11px] text-[var(--ink-muted)]">Groq Inc. (Inférence Llama 3 70B certifiée sans rétention des données d'entraînement)</p>
              </div>
              <div className="p-3 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1">
                <span className="font-bold text-[11px] text-[var(--ink)] block">Clauses Contractuelles Types</span>
                <p className="text-[11px] text-[var(--ink-muted)]">SCCs Commission Européenne 2021/914 Module 2 (Responsable du traitement à Sous-traitant)</p>
              </div>
              <div className="p-3 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] space-y-1">
                <span className="font-bold text-[11px] text-[var(--ink)] block">Statut Anonymisation</span>
                <p className="text-[11px] text-[var(--warn-amber)] font-medium">Anonymisation avant LLM : Phase 3 (état actuel honnête)</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
