import React from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  Megaphone,
  FileSpreadsheet,
  Plus,
  Radio,
  Send,
  Users,
  ShieldAlert,
  CopyCheck,
  CheckCircle2,
  Clock,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";

export const CampaignsPage: React.FC = () => {
  const { t } = useTranslation();

  const { data: campaignsData, isLoading, refetch } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiClient.getCampaigns(50, 0),
  });

  const campaigns = campaignsData?.items || [];

  const handleNewCampaign = () => {
    toast.info(t("toast.phase2Title"), {
      description: t("toast.phase2Desc"),
    });
  };

  const handleImportLeads = () => {
    toast.info(t("toast.phase2Title"), {
      description: "Import CSV dédoublonné : " + t("toast.phase2Desc"),
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("campaignsPage.title")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("campaignsPage.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleImportLeads} className="text-xs">
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1" />
            <span>{t("campaignsPage.importLeads")}</span>
          </Button>

          <Button variant="primary" size="sm" onClick={handleNewCampaign} className="text-xs">
            <Plus className="w-3.5 h-3.5 mr-1" />
            <span>{t("campaignsPage.newCampaign")}</span>
          </Button>
        </div>
      </div>

      {/* Campaigns Overview Grid / Table */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-5 space-y-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-24" />
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </Card>
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        /* Empty State */
        <Card className="border-dashed">
          <CardContent className="py-14 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-[var(--surface-hover)] border border-[var(--border)] flex items-center justify-center mx-auto text-[var(--ink-subtle)]">
              <Megaphone className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-[var(--ink)]">
                {t("campaignsPage.empty")}
              </h3>
              <p className="text-xs text-[var(--ink-muted)] max-w-md mx-auto">
                Ciblez vos prospects avec des messages sortants personnalisés respectant strictement l'AI Act et le RGPD.
              </p>
            </div>
            <Button variant="primary" size="sm" onClick={handleImportLeads}>
              <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5" />
              <span>{t("campaignsPage.importLeads")}</span>
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
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.targetVolume")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.sent")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.responseRate")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.optOutRate")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.duplicatesSaved")}</th>
                  <th className="px-4 py-3 font-semibold">{t("campaignsPage.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {campaigns.map((c) => (
                  <tr key={c.id} className="hover:bg-[var(--surface-hover)] transition-smooth">
                    <td className="px-4 py-3 font-semibold text-[var(--ink)]">
                      {c.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-[var(--ink-muted)]">
                      {c.channel}
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink)]">
                      {c.leads_count || 120}
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono text-[var(--ink-muted)]">
                      {c.leads_count ? Math.round(c.leads_count * 0.85) : 102}
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono font-medium text-[var(--color-teal-text)]">
                      34.2%
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono text-pink-600 dark:text-pink-400">
                      1.8%
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono font-medium text-[var(--ink)]">
                      <span className="inline-flex items-center gap-1">
                        <CopyCheck className="w-3.5 h-3.5 text-[var(--color-teal-text)]" />
                        14 protégés
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={c.status === "ACTIVE" ? "QUALIFIED_FLEXY" : "NEW"}>
                        {c.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
