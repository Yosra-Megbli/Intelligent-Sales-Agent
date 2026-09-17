import React, { useState, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  flexRender,
  SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { apiClient } from "@/api/client";
import { LeadSummary, LeadStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { LeadDrawer } from "@/components/leads/LeadDrawer";
import { AddLeadModal } from "@/components/leads/AddLeadModal";
import { CsvUploadModal } from "@/components/leads/CsvUploadModal";
import { ExportModal } from "@/components/ui/ExportModal";
import { exportLeadsToCsv, exportLeadsToExcel } from "@/utils/exportEngine";
import {
  Search,
  Download,
  UploadCloud,
  Copy,
  UserCheck,
  RotateCcw,
  AlertCircle,
  Check,
  ShieldAlert,
  ArrowUpDown,
  Filter,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";

export const LeadsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [langFilter, setLangFilter] = useState<string>("ALL");
  const [regionFilter, setRegionFilter] = useState<string>("ALL");
  const [grdFilter, setGrdFilter] = useState<string>("ALL");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [selectedLead, setSelectedLead] = useState<LeadSummary | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  const {
    data: leadsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["leads", statusFilter, searchTerm],
    queryFn: () =>
      apiClient.getLeads({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        search: searchTerm.trim() || undefined,
        limit: 200,
      }),
  });

  // Helper to determine GRD from region / provider
  const resolveGrd = (lead: LeadSummary): string => {
    if (lead.provider) return lead.provider;
    const r = (lead.region || "").toLowerCase();
    if (r.includes("fland") || r.includes("vl") || r.includes("antw") || r.includes("gent")) return "Fluvius";
    if (r.includes("wallon") || r.includes("wa") || r.includes("liège") || r.includes("namur")) return "ORES";
    return "Fluvius";
  };

  // Helper to determine language chip
  const resolveLang = (lead: LeadSummary): string => {
    if (lead.language) return lead.language.toUpperCase();
    const r = (lead.region || "").toLowerCase();
    if (r.includes("fland") || r.includes("vl")) return "NL";
    if (r.includes("wallon") || r.includes("wa")) return "FR";
    return "FR";
  };

  // Helper to determine region code
  const resolveRegion = (lead: LeadSummary): string => {
    const r = (lead.region || "").toLowerCase();
    if (r.includes("fland") || r.includes("vl")) return "VL";
    if (r.includes("wallon") || r.includes("wa")) return "WA";
    return lead.region || "BE";
  };

  // Filtered dataset
  const filteredData = useMemo(() => {
    if (!leadsData?.items) return [];
    return leadsData.items.filter((lead) => {
      if (langFilter !== "ALL" && resolveLang(lead) !== langFilter) return false;
      if (regionFilter !== "ALL" && resolveRegion(lead) !== regionFilter) return false;
      if (grdFilter !== "ALL" && resolveGrd(lead) !== grdFilter) return false;
      return true;
    });
  }, [leadsData?.items, langFilter, regionFilter, grdFilter]);

  const copyEan = (ean: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(ean);
    toast.success(t("leads.copyEanToast") || "Code EAN copié dans le presse-papier");
  };

  const handleOpenExport = () => {
    if (!filteredData.length) {
      toast.error(t("leads.noDataExport") || "Aucun prospect à exporter.");
      return;
    }
    setIsExportModalOpen(true);
  };

  // Define Columns
  const columns = useMemo<ColumnDef<LeadSummary>[]>(
    () => [
      {
        accessorKey: "name",
        header: ({ column }) => (
          <button
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="flex items-center gap-1 font-semibold hover:text-[var(--ink)] cursor-pointer"
          >
            <span>{t("leads.table.name")}</span>
            <ArrowUpDown className="w-3 h-3 text-[var(--ink-subtle)]" />
          </button>
        ),
        cell: ({ row }) => {
          const lead = row.original;
          const isOpt = lead.status === "OPT_OUT";
          return (
            <div className="font-medium text-[var(--ink)] flex items-center gap-1.5">
              {isOpt ? (
                <span className="text-pink-600 dark:text-pink-400 font-mono text-[11px] line-through">
                  {t("compliance.gdprPurged")}
                </span>
              ) : (
                <span>{[lead.first_name, lead.last_name].filter(Boolean).join(" ") || "Prospect sans nom"}</span>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: "status",
        header: t("leads.table.status"),
        cell: ({ row }) => <Badge variant={row.original.status as LeadStatus} />,
      },
      {
        id: "language",
        header: t("leads.table.language"),
        cell: ({ row }) => {
          const lang = resolveLang(row.original);
          return (
            <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink-muted)]">
              {lang}
            </span>
          );
        },
      },
      {
        id: "region",
        header: t("leads.table.region"),
        cell: ({ row }) => {
          const reg = resolveRegion(row.original);
          return (
            <span className="font-mono text-[11px] font-semibold text-[var(--ink)]">
              {reg}
            </span>
          );
        },
      },
      {
        id: "grd",
        header: t("leads.table.grd"),
        cell: ({ row }) => (
          <span className="text-xs text-[var(--ink-muted)] font-medium">
            {resolveGrd(row.original)}
          </span>
        ),
      },
      {
        accessorKey: "current_supplier",
        header: t("leads.table.supplier"),
        cell: ({ row }) => (
          <span className="text-xs text-[var(--ink-muted)]">
            {row.original.current_supplier || "—"}
          </span>
        ),
      },
      {
        accessorKey: "ean",
        header: t("leads.table.ean"),
        cell: ({ row }) => {
          const isOpt = row.original.status === "OPT_OUT";
          if (isOpt) return <span className="text-[var(--ink-subtle)] font-mono">—</span>;
          const rawEan = row.original.ean || (row.original.notes?.includes("5414") ? "5414" + "000".repeat(4) : null);
          if (!rawEan) return <span className="text-[var(--ink-subtle)] font-mono">—</span>;
          const displayEan = `${rawEan.slice(0, 4)} •••• ${rawEan.slice(-4)}`;
          return (
            <div className="flex items-center gap-1.5 font-mono text-[11px] text-[var(--ink)]">
              <span>{displayEan}</span>
              <button
                onClick={(e) => copyEan(rawEan, e)}
                title="Copier le code EAN"
                className="p-1 rounded hover:bg-[var(--border)]/40 text-[var(--ink-subtle)] hover:text-[var(--ink)] transition-smooth cursor-pointer"
              >
                <Copy className="w-3 h-3" />
              </button>
            </div>
          );
        },
      },
      {
        accessorKey: "date",
        header: t("leads.table.date"),
        cell: ({ row }) => {
          const date = row.original.last_contact_date || row.original.created_at;
          return (
            <span className="font-mono text-[11px] text-[var(--ink-subtle)]">
              {new Date(date).toLocaleDateString("fr-BE")}
            </span>
          );
        },
      },
    ],
    [t]
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const { rows } = table.getRowModel();

  // TanStack Virtualizer
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 48,
    overscan: 10,
  });

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("leads.title")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("leads.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsCsvModalOpen(true)}
            className="text-xs font-semibold text-[var(--color-teal)] hover:text-[var(--color-teal-hover)]"
          >
            <UploadCloud className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.importCsv") || "Importer CSV"}</span>
          </Button>
          <Button variant="secondary" size="sm" onClick={handleOpenExport} className="text-xs">
            <Download className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.exportCsv") || "Exporter"}</span>
          </Button>
          <Button size="sm" onClick={() => setIsAddModalOpen(true)} className="text-xs">
            <UserPlus className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.addModal.button") || "Ajouter un prospect"}</span>
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-[var(--surface)] border border-[var(--border)] p-3 rounded-[0.75rem] shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search bar */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)]" />
            <input
              type="text"
              placeholder={t("leads.searchPlaceholder")}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)] transition-smooth"
            />
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-[var(--ink-muted)] self-end md:self-auto">
            <span>{t("leads.resultsCount", { count: filteredData.length })}</span>
          </div>
        </div>

        {/* Facet Filters Bar */}
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-[var(--border)]">
          {/* Status Facet */}
          <div className="flex items-center gap-1 overflow-x-auto py-1">
            <span className="text-[10px] font-semibold uppercase text-[var(--ink-subtle)] mr-1">
              Statut:
            </span>
            {[
              { label: t("common.all"), value: "ALL" },
              { label: t("status.NEW"), value: "NEW" },
              { label: t("status.CONTACTED"), value: "CONTACTED" },
              { label: t("status.QUALIFIED_FLEXY"), value: "QUALIFIED_FLEXY" },
              { label: t("status.QUALIFIED_MOTION"), value: "QUALIFIED_MOTION" },
              { label: t("status.FIXED_SEEKER"), value: "FIXED_SEEKER" },
              { label: t("status.OPT_OUT"), value: "OPT_OUT" },
            ].map((s) => (
              <button
                key={s.value}
                onClick={() => setStatusFilter(s.value)}
                className={`px-2 py-0.5 rounded-[0.35rem] text-[11px] font-medium whitespace-nowrap transition-smooth cursor-pointer ${
                  statusFilter === s.value
                    ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-semibold shadow-xs"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden sm:block" />

          {/* Region Facet */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-semibold uppercase text-[var(--ink-subtle)] mr-1">
              Région:
            </span>
            {[
              { label: "Toutes", value: "ALL" },
              { label: "Flandre (VL)", value: "VL" },
              { label: "Wallonie (WA)", value: "WA" },
            ].map((r) => (
              <button
                key={r.value}
                onClick={() => setRegionFilter(r.value)}
                className={`px-2 py-0.5 rounded-[0.35rem] text-[11px] font-medium transition-smooth cursor-pointer ${
                  regionFilter === r.value
                    ? "bg-[var(--color-navy)] text-[var(--color-teal)] font-semibold shadow-xs"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden sm:block" />

          {/* GRD Facet */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-semibold uppercase text-[var(--ink-subtle)] mr-1">
              GRD:
            </span>
            {[
              { label: "Tous", value: "ALL" },
              { label: "Fluvius", value: "Fluvius" },
              { label: "ORES", value: "ORES" },
              { label: "RESA", value: "RESA" },
            ].map((g) => (
              <button
                key={g.value}
                onClick={() => setGrdFilter(g.value)}
                className={`px-2 py-0.5 rounded-[0.35rem] text-[11px] font-medium transition-smooth cursor-pointer ${
                  grdFilter === g.value
                    ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-semibold shadow-xs"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Leads Table Container with Virtualization */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] overflow-hidden shadow-xs">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-4 py-2 border-b border-[var(--border)]/50">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="p-12 text-center space-y-3">
            <AlertCircle className="w-8 h-8 text-[var(--color-danger)] mx-auto" />
            <p className="text-xs text-[var(--ink-muted)]">{t("common.error")}</p>
            <Button variant="secondary" size="sm" onClick={() => refetch()}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              <span>{t("common.retry")}</span>
            </Button>
          </div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <UserCheck className="w-8 h-8 text-[var(--ink-subtle)] mx-auto" />
            <p className="text-xs text-[var(--ink-muted)]">Aucun prospect ne correspond aux critères sélectionnés.</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSearchTerm("");
                setStatusFilter("ALL");
                setLangFilter("ALL");
                setRegionFilter("ALL");
                setGrdFilter("ALL");
              }}
            >
              <span>Réinitialiser les filtres</span>
            </Button>
          </div>
        ) : (
          <div
            ref={tableContainerRef}
            className="overflow-auto max-h-[640px] relative"
          >
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[var(--surface-hover)] border-b-2 border-[var(--border)] text-[var(--ink)] uppercase tracking-wider text-[11px] font-bold sticky top-0 z-10 shadow-xs">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} className="px-4 py-3 font-bold whitespace-nowrap text-[var(--ink)]">
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody
                className="divide-y divide-[var(--border)] relative"
                style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const row = rows[virtualRow.index];
                  const isOptOut = row.original.status === "OPT_OUT";

                  return (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedLead(row.original)}
                      className={`hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer absolute w-full flex items-center ${
                        isOptOut ? "bg-pink-50/20 dark:bg-pink-950/10 line-through opacity-70" : ""
                      }`}
                      style={{
                        top: 0,
                        transform: `translateY(${virtualRow.start}px)`,
                        height: `${virtualRow.size}px`,
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-2 flex-1 truncate whitespace-nowrap">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 360° Lead Drawer */}
      <LeadDrawer
        lead={selectedLead}
        isOpen={Boolean(selectedLead)}
        onClose={() => setSelectedLead(null)}
      />

      <AddLeadModal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} />
      <CsvUploadModal
        isOpen={isCsvModalOpen}
        onClose={() => setIsCsvModalOpen(false)}
        onSuccess={() => {
          refetch();
        }}
      />
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        title="Exporter les prospects CRM"
        subtitle="Téléchargez la liste filtrée au format Excel stylisé ou CSV optimisé pour tableur."
        itemCount={filteredData.length}
        itemLabel="prospects"
        onExportExcel={() => {
          exportLeadsToExcel(filteredData);
          toast.success("Tableur Excel stylisé téléchargé !");
        }}
        onExportCsv={() => {
          exportLeadsToCsv(filteredData);
          toast.success("Fichier CSV optimisé téléchargé !");
        }}
      />
    </div>
  );
};
