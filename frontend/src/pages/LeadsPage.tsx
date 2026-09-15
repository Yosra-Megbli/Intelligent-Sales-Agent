import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Search, UserCheck, ShieldAlert, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";
import { LeadStatus } from "@/api/types";

export const LeadsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const {
    data: leadsData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["leads", statusFilter, searchTerm],
    queryFn: () =>
      apiClient.getLeads({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        search: searchTerm.trim() || undefined,
        limit: 50,
      }),
  });

  const handleImportCsvStub = () => {
    toast.info(t("toast.phase2Title"), {
      description: "Import CSV dédoublonné : " + t("toast.phase2Desc"),
    });
  };

  const statuses: { label: string; value: string }[] = [
    { label: "Tous", value: "ALL" },
    { label: t("status.NEW"), value: "NEW" },
    { label: t("status.CONTACTED"), value: "CONTACTED" },
    { label: t("status.QUALIFIED_FLEXY"), value: "QUALIFIED_FLEXY" },
    { label: t("status.QUALIFIED_MOTION"), value: "QUALIFIED_MOTION" },
    { label: t("status.FIXED_SEEKER"), value: "FIXED_SEEKER" },
    { label: t("status.OPT_OUT"), value: "OPT_OUT" },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.leads")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Gestion du pipe commercial et historique des contacts traités par Sophie.
          </p>
        </div>

        <Button variant="primary" size="sm" onClick={handleImportCsvStub} className="text-xs">
          <FileSpreadsheet className="w-3.5 h-3.5 mr-1" />
          <span>{t("overview.quickActions.importCsv")}</span>
        </Button>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[var(--surface)] border border-[var(--border)] p-3 rounded-[0.75rem] shadow-xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)]" />
          <input
            type="text"
            placeholder="Filtrer par nom, téléphone, EAN..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)]"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {statuses.map((s) => (
            <button
              key={s.value}
              onClick={() => setStatusFilter(s.value)}
              className={`px-2.5 py-1 rounded-[0.35rem] text-[11px] font-medium whitespace-nowrap transition-smooth cursor-pointer ${
                statusFilter === s.value
                  ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-semibold shadow-xs"
                  : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Leads Table */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--surface-hover)] border-b border-[var(--border)] text-[var(--ink-muted)] uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3 font-semibold">Prospect</th>
                <th className="px-4 py-3 font-semibold">Contact</th>
                <th className="px-4 py-3 font-semibold">Région / Gestionnaire</th>
                <th className="px-4 py-3 font-semibold">Statut</th>
                <th className="px-4 py-3 font-semibold">Score</th>
                <th className="px-4 py-3 font-semibold text-right">Dernier Contact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-28" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-5 w-20" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-8" /></td>
                    <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-16 ml-auto" /></td>
                  </tr>
                ))
              ) : leadsData?.items && leadsData.items.length > 0 ? (
                leadsData.items.map((lead) => {
                  const isOptOut = lead.status === "OPT_OUT";

                  return (
                    <tr
                      key={lead.id}
                      className={`hover:bg-[var(--surface-hover)] transition-smooth ${
                        isOptOut ? "bg-pink-50/20 dark:bg-pink-950/10 line-through opacity-70" : ""
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-[var(--ink)]">
                        {isOptOut ? (
                          <span className="font-mono text-pink-600 dark:text-pink-400">
                            {t("compliance.gdprPurged")}
                          </span>
                        ) : (
                          [lead.first_name, lead.last_name].filter(Boolean).join(" ") || "Prospect sans nom"
                        )}
                      </td>
                      <td className="px-4 py-3 text-[var(--ink-muted)] font-mono text-[11px]">
                        {isOptOut ? (
                          "—"
                        ) : (
                          lead.phone || lead.email || "—"
                        )}
                      </td>
                      <td className="px-4 py-3 text-[var(--ink-muted)]">
                        {lead.region ? `${lead.region} (${lead.provider || "Fluvius/ORES"})` : "Belgique"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={lead.status as LeadStatus} />
                      </td>
                      <td className="px-4 py-3 tabular-nums font-mono font-medium text-[var(--ink)]">
                        {lead.qualification_score ? `${lead.qualification_score}/100` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-[var(--ink-subtle)] font-mono text-[11px]">
                        {lead.last_contact_date
                          ? new Date(lead.last_contact_date).toLocaleDateString("fr-BE")
                          : new Date(lead.created_at).toLocaleDateString("fr-BE")}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-xs text-[var(--ink-muted)]">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <UserCheck className="w-8 h-8 text-[var(--ink-subtle)]" />
                      <span>Aucun prospect ne correspond aux critères sélectionnés.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
