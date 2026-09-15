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

  const handlePhase2Action = (featureName: string) => {
    toast.info(t("toast.phase2Title"), {
      description: `${featureName} : ${t("toast.phase2Desc")}`,
    });
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
            onClick={() => handlePhase2Action("Export de rapport")}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 mr-1" />
            <span>Exporter</span>
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
          <div className="w-8 h-8 rounded-full bg-[var(--brand-soft)] border border-[var(--brand-soft-border)] flex items-center justify-center text-[var(--brand-green)] shrink-0">
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
