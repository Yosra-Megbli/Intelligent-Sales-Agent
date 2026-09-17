import React from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { KpiGrid } from "@/components/overview/KpiGrid";
import { ConversionFunnel } from "@/components/overview/ConversionFunnel";
import { RecentActivityList } from "@/components/overview/RecentActivityList";
import { Button } from "@/components/ui/Button";
import { RefreshCw, AlertTriangle, ShieldCheck, Download } from "lucide-react";
import { toast } from "sonner";

export const OverviewPage: React.FC = () => {
  const { t } = useTranslation();

  const {
    data: overview,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiClient.getOverview(),
    staleTime: 30000,
    retry: 1,
  });

  const {
    data: stats,
    isLoading: isStatsLoading,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: () => apiClient.getStats(),
    staleTime: 30000,
    retry: 1,
  });

  const {
    data: activities,
    isLoading: isActivitiesLoading,
    refetch: refetchActivities,
  } = useQuery({
    queryKey: ["activities"],
    queryFn: () => apiClient.getActivities(15),
    staleTime: 15000,
    retry: 1,
  });

  const handleRefresh = () => {
    refetchOverview();
    refetchStats();
    refetchActivities();
    toast.success(t("common.refresh"));
  };

  const handleExportReport = () => {
    if (!overview && !stats) {
      toast.error(t("common.error") || "Données indisponibles pour l'export.");
      return;
    }

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = now.toLocaleTimeString();

    // Helper functions for CSV formatting
    const sanitize = (val: string | number | undefined | null) => {
      if (val === undefined || val === null) return '""';
      const s = String(val).replace(/"/g, '""');
      // OWASP CSV formula injection guard
      return /^[=+\-@\t\r]/.test(s) ? `"'${s}"` : `"${s}"`;
    };

    const lines: string[] = [
      `"RAPPORT DE SUPERVISION DES PERFORMANCES - SOPHIE AI (ECOFIX BELGIQUE)";""`,
      `"Date de génération";"${dateStr} ${timeStr}"`,
      `"Plateforme";"Production Render Live"`,
      `""`,
      `"=== INDICATEURS CLÉS DE PERFORMANCE (KPI) ===";""`,
      `"Indicateur";"Valeur"`,
      `"Contacts Engagés";${sanitize(overview?.contacted ?? stats?.total_leads ?? 0)}`,
      `"Conversations Actives";${sanitize(overview?.active_conversations ?? 0)}`,
      `"Prospects Qualifiés";${sanitize(overview?.qualified ?? 0)}`,
      `"Contrats Signés";${sanitize(overview?.signed_contracts ?? 0)}`,
      `"Taux de Transformation";${sanitize(`${(overview?.conversion_rate ?? 0).toFixed(1)} %`)}`,
      `"Coût d'Acquisition / Vente (CAC)";${sanitize(`${(overview?.cost_per_sale ?? 0).toFixed(2)} €`)}`,
      `"Chiffre d'Affaires Annuel Estimé (ARR)";${sanitize(`${(overview?.estimated_ca ?? 0).toLocaleString("fr-BE", { minimumFractionDigits: 2 })} €/an`)}`,
      `"Coût Moyen par Conversation";${sanitize(`${(overview?.cost_per_conversation ?? 0.02).toFixed(2)} €`)}`,
      `""`,
      `"=== ENTONNOIR DE CONVERSION COMMERCIALE ===";""`,
      `"Étape";"Volume"`,
      `"01 - Nouveaux Contacts";${sanitize(overview?.total_leads ?? stats?.total_leads ?? 0)}`,
      `"02 - Engagés par Sophie";${sanitize(overview?.contacted ?? 0)}`,
      `"03 - Qualifiés (Flexy & Motion)";${sanitize(overview?.qualified ?? 0)}`,
      `"04 - Contrats Signés";${sanitize(overview?.signed_contracts ?? 0)}`,
      `""`,
    ];

    if (stats?.by_status && Object.keys(stats.by_status).length > 0) {
      lines.push(`"=== RÉPARTITION DES STATUTS CRM ===";""`);
      lines.push(`"Statut";"Nombre de Prospects"`);
      for (const [st, count] of Object.entries(stats.by_status)) {
        lines.push(`${sanitize(st)};${sanitize(count)}`);
      }
      lines.push(`""`);
    }

    if (activities?.items && activities.items.length > 0) {
      lines.push(`"=== FLUX D'ACTIVITÉ RÉCENT ===";""`);
      lines.push(`"Date & Heure";"Prospect";"Type d'activité";"Détails"`);
      for (const act of activities.items) {
        lines.push([
          sanitize(act.created_at ? new Date(act.created_at).toLocaleString() : ""),
          sanitize(act.lead_name || "Prospect"),
          sanitize(act.type || ""),
          sanitize(act.details || ""),
        ].join(";"));
      }
      lines.push(`""`);
    }

    lines.push(`"=== CONFORMITÉ & MENTIONS LÉGALES ===";""`);
    lines.push(`"Cadre réglementaire";"Marché de l'énergie belge (CWaPE Wallonie, VREG Flandre, Brugel non desservi)"`);
    lines.push(`"Législation";"AI Act européen • Droit de rétractation 14 jours • RGPD Privacy by Design"`);
    lines.push(`"Mention";"SPÉCIMEN / DÉMO - DONNÉES FICTIVES DE PROSPECTS"`);

    const csvContent = lines.join("\r\n");
    // UTF-8 BOM '\uFEFF' ensures Excel on Windows displays accents without mojibake
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `rapport-performance-sophie-${dateStr}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    toast.success(t("toast.exportedCsv") || "Rapport de performance exporté avec succès (CSV)");
  };

  const isLoading = isOverviewLoading || isStatsLoading;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("overview.title")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("overview.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            className="text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            <span>{t("common.refresh")}</span>
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleExportReport}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 mr-1" />
            <span>{t("common.export") || "Exporter"}</span>
          </Button>
        </div>
      </div>

      {/* Error Banner if API call failed */}
      {overviewError && (
        <div className="p-4 rounded-[0.75rem] border border-[var(--danger-border)] bg-[var(--danger-soft)] flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-[var(--danger-red)] shrink-0" />
            <div>
              <h4 className="text-xs font-semibold text-[var(--danger-red)]">
                {t("common.error")}
              </h4>
              <p className="text-[11px] text-[var(--ink)] opacity-90 mt-0.5">
                {(overviewError as Error).message || "Serveur Render en cours de réveil ou clé API non acceptée."}
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefresh}
            className="text-xs shrink-0"
          >
            {t("common.retry")}
          </Button>
        </div>
      )}

      {/* 7 KPI Cards Grid */}
      <KpiGrid overview={overview} stats={stats} isLoading={isLoading} />

      {/* Conversion Funnel */}
      <ConversionFunnel overview={overview} stats={stats} isLoading={isLoading} />

      {/* Live Recent Activity Feed */}
      <RecentActivityList
        activities={activities?.items}
        isLoading={isActivitiesLoading}
      />

      {/* Compliance / Belgian Energy Regulatory Footer Callout */}
      <div className="p-4 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface)] flex items-center justify-between gap-4 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] flex items-center justify-center text-[var(--color-teal-text)] shrink-0">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-semibold text-[var(--ink)] block">
              Garantie Conformité Marché Belge & RGPD
            </span>
            <span className="text-[11px] text-[var(--ink-muted)] block mt-0.5">
              Fluvius (Flandre) • ORES / RESA (Wallonie) • Aucun frais de résiliation résidentiel • Délai de rétractation 14j
            </span>
          </div>
        </div>

        <span className="text-[10px] font-mono font-medium text-[var(--ink-subtle)] border border-[var(--border)] px-2 py-1 rounded bg-[var(--surface-hover)]">
          SPÉCIMEN / DÉMO
        </span>
      </div>
    </div>
  );
};
