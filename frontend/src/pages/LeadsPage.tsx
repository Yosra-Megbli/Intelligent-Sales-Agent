import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
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
  Users,
  User,
  Phone,
  Mail,
  Globe,
  Send,
  Zap,
  Car,
  Flame,
  BatteryCharging,
  ChevronRight,
  X,
  Sparkles,
  Building2,
  CheckCircle2,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

export const LeadsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [langFilter, setLangFilter] = useState<string>("ALL");
  const [regionFilter, setRegionFilter] = useState<string>("ALL");
  const [grdFilter, setGrdFilter] = useState<string>("ALL");
  const [selectedLead, setSelectedLead] = useState<LeadSummary | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [sortField, setSortField] = useState<"name" | "date" | "status">("date");
  const [sortAsc, setSortAsc] = useState(false);

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

  const allLeads = leadsData?.items || [];

  // Pipeline Counters for KPI Cards
  const kpiCounts = useMemo(() => {
    return {
      total: allLeads.length,
      new: allLeads.filter((l) => l.status === "NEW").length,
      contacted: allLeads.filter((l) => l.status === "CONTACTED").length,
      qualified: allLeads.filter((l) => l.status === "QUALIFIED" || l.status === "QUALIFIED_FLEXY" || l.status === "QUALIFIED_MOTION").length,
      customers: allLeads.filter((l) => l.status === "CUSTOMER" || l.status === "CONTRACT").length,
      optOut: allLeads.filter((l) => l.status === "OPT_OUT").length,
    };
  }, [allLeads]);

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
    if (r.includes("fland") || r.includes("vl")) return "Flandre (VL)";
    if (r.includes("wallon") || r.includes("wa")) return "Wallonie (WA)";
    return lead.region || "Belgique";
  };

  // Filtered and Sorted dataset
  const filteredData = useMemo(() => {
    let result = allLeads.filter((lead) => {
      if (langFilter !== "ALL" && resolveLang(lead) !== langFilter) return false;
      if (regionFilter !== "ALL") {
        const reg = (lead.region || "").toLowerCase();
        if (regionFilter === "VL" && !reg.includes("fland") && !reg.includes("vl")) return false;
        if (regionFilter === "WA" && !reg.includes("wallon") && !reg.includes("wa")) return false;
      }
      if (grdFilter !== "ALL" && resolveGrd(lead) !== grdFilter) return false;
      return true;
    });

    result.sort((a, b) => {
      if (sortField === "name") {
        const nameA = [a.first_name, a.last_name].filter(Boolean).join(" ");
        const nameB = [b.first_name, b.last_name].filter(Boolean).join(" ");
        return sortAsc ? nameA.localeCompare(nameB) : nameB.localeCompare(nameA);
      }
      if (sortField === "status") {
        return sortAsc ? a.status.localeCompare(b.status) : b.status.localeCompare(a.status);
      }
      // date
      const dateA = new Date(a.last_contact_date || a.created_at).getTime();
      const dateB = new Date(b.last_contact_date || b.created_at).getTime();
      return sortAsc ? dateA - dateB : dateB - dateA;
    });

    return result;
  }, [allLeads, langFilter, regionFilter, grdFilter, sortField, sortAsc]);

  const copyEan = (ean: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(ean);
    toast.success("Code EAN 18 chiffres copié !");
  };

  const handleOpenExport = () => {
    if (!filteredData.length) {
      toast.error("Aucun prospect à exporter.");
      return;
    }
    setIsExportModalOpen(true);
  };

  const hasActiveFilters =
    searchTerm.trim().length > 0 ||
    statusFilter !== "ALL" ||
    langFilter !== "ALL" ||
    regionFilter !== "ALL" ||
    grdFilter !== "ALL";

  const clearAllFilters = () => {
    setSearchTerm("");
    setStatusFilter("ALL");
    setLangFilter("ALL");
    setRegionFilter("ALL");
    setGrdFilter("ALL");
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="p-2 rounded-xl bg-[var(--color-teal)]/10 text-[var(--color-teal)] border border-[var(--color-teal)]/20 shadow-xs">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
                {t("leads.title") || "Prospects & Qualification CRM"}
              </h1>
              <p className="text-xs text-[var(--ink-muted)]">
                {t("leads.subtitle") || "Tunnel d'acquisition commercial, qualification déterministe et registre de conformité RGPD."}
              </p>
            </div>
          </div>
        </div>

        {/* Global Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsCsvModalOpen(true)}
            className="text-xs font-semibold text-[var(--color-teal)] hover:text-[var(--color-teal-hover)] cursor-pointer"
          >
            <UploadCloud className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.importCsv") || "Importer CSV"}</span>
          </Button>

          <Button variant="secondary" size="sm" onClick={handleOpenExport} className="text-xs cursor-pointer">
            <Download className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.exportCsv") || "Exporter"}</span>
          </Button>

          <Button
            size="sm"
            onClick={() => setIsAddModalOpen(true)}
            className="text-xs font-bold bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-600 text-white shadow-xs cursor-pointer"
          >
            <UserPlus className="w-3.5 h-3.5 mr-1" />
            <span>{t("leads.addModal.button") || "Ajouter un prospect"}</span>
          </Button>
        </div>
      </div>

      {/* KPI Overview Cards (Pipeline Stages) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Card 1: Total */}
        <div
          onClick={() => setStatusFilter("ALL")}
          className={`p-3.5 rounded-2xl border transition-smooth cursor-pointer shadow-2xs hover:scale-[1.02] ${
            statusFilter === "ALL"
              ? "bg-[var(--surface-hover)] border-[var(--color-teal)] ring-1 ring-[var(--color-teal)]/30"
              : "bg-[var(--surface)] border-[var(--border)] hover:border-[var(--color-teal)]/40"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--ink-muted)]">Total Contacts</span>
            <div className="w-7 h-7 rounded-lg bg-[var(--surface-hover)] text-[var(--ink)] flex items-center justify-center">
              <Users className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[var(--ink)] font-mono tabular-nums mt-1">
            {kpiCounts.total}
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] font-medium">Base CRM active</span>
        </div>

        {/* Card 2: Contacted / In Dialogue */}
        <div
          onClick={() => setStatusFilter("CONTACTED")}
          className={`p-3.5 rounded-2xl border transition-smooth cursor-pointer shadow-2xs hover:scale-[1.02] ${
            statusFilter === "CONTACTED"
              ? "bg-blue-500/10 border-blue-500 ring-1 ring-blue-500/30"
              : "bg-[var(--surface)] border-[var(--border)] hover:border-blue-500/40"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--ink-muted)]">Engagés par Sophie</span>
            <div className="w-7 h-7 rounded-lg bg-blue-500/15 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <Clock className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 font-mono tabular-nums mt-1">
            {kpiCounts.contacted + kpiCounts.new}
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] font-medium">En cours de dialogue</span>
        </div>

        {/* Card 3: Qualified (Flexy / Motion) */}
        <div
          onClick={() => setStatusFilter("QUALIFIED_FLEXY")}
          className={`p-3.5 rounded-2xl border transition-smooth cursor-pointer shadow-2xs hover:scale-[1.02] ${
            statusFilter.includes("QUALIFIED")
              ? "bg-[var(--color-teal)]/10 border-[var(--color-teal)] ring-1 ring-[var(--color-teal)]/30"
              : "bg-[var(--surface)] border-[var(--border)] hover:border-[var(--color-teal)]/40"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--ink-muted)]">Qualifiés Offres</span>
            <div className="w-7 h-7 rounded-lg bg-[var(--color-teal)]/15 text-[var(--color-teal)] flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[var(--color-teal)] font-mono tabular-nums mt-1">
            {kpiCounts.qualified}
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] font-medium">Flexy & Motion prêts</span>
        </div>

        {/* Card 4: Customers / Signed */}
        <div
          onClick={() => setStatusFilter("CUSTOMER")}
          className={`p-3.5 rounded-2xl border transition-smooth cursor-pointer shadow-2xs hover:scale-[1.02] ${
            statusFilter === "CUSTOMER"
              ? "bg-emerald-500/10 border-emerald-500 ring-1 ring-emerald-500/30"
              : "bg-[var(--surface)] border-[var(--border)] hover:border-emerald-500/40"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--ink-muted)]">Clients Signés</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 font-mono tabular-nums mt-1">
            {kpiCounts.customers}
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] font-medium">Contrats certifiés</span>
        </div>

        {/* Card 5: GDPR Opt-Out */}
        <div
          onClick={() => setStatusFilter("OPT_OUT")}
          className={`p-3.5 rounded-2xl border transition-smooth cursor-pointer shadow-2xs hover:scale-[1.02] col-span-2 sm:col-span-1 ${
            statusFilter === "OPT_OUT"
              ? "bg-pink-500/10 border-pink-500 ring-1 ring-pink-500/30"
              : "bg-[var(--surface)] border-[var(--border)] hover:border-pink-500/40"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--ink-muted)]">Protégés RGPD</span>
            <div className="w-7 h-7 rounded-lg bg-pink-500/15 text-pink-600 dark:text-pink-400 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-pink-600 dark:text-pink-400 font-mono tabular-nums mt-1">
            {kpiCounts.optOut}
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] font-medium">Données purgées (STOP)</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-[var(--surface)] border border-[var(--border)] p-4 rounded-2xl shadow-xs space-y-3.5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search bar */}
          <div className="relative flex-1 max-w-lg">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)]" />
            <input
              type="text"
              placeholder="Rechercher par nom, email, téléphone, code EAN..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-9 py-2 text-xs rounded-xl border border-[var(--border)] bg-[var(--surface-hover)]/70 text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)] transition-smooth shadow-2xs"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)] hover:text-[var(--ink)] p-0.5 rounded-full hover:bg-[var(--border)] transition-smooth"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {hasActiveFilters && (
              <button
                onClick={clearAllFilters}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition-smooth cursor-pointer"
              >
                <X className="w-3 h-3" />
                <span>Réinitialiser filtres</span>
              </button>
            )}

            <div className="text-xs font-mono text-[var(--ink-muted)] bg-[var(--surface-hover)] px-3 py-1.5 rounded-lg border border-[var(--border)]">
              <strong>{filteredData.length}</strong> prospect(s) trouvé(s)
            </div>
          </div>
        </div>

        {/* Facet Filters Bar */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[var(--border)] text-xs">
          {/* Status Facet */}
          <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-subtle)] mr-1">
              Statut:
            </span>
            {[
              { label: "Tous", value: "ALL" },
              { label: "Nouveaux", value: "NEW" },
              { label: "Contactés", value: "CONTACTED" },
              { label: "Qualifié Flexy", value: "QUALIFIED_FLEXY" },
              { label: "Qualifié Motion", value: "QUALIFIED_MOTION" },
              { label: "Cherche Fixe", value: "FIXED_SEEKER" },
              { label: "Clients Signés", value: "CUSTOMER" },
              { label: "Opt-Out (RGPD)", value: "OPT_OUT" },
            ].map((s) => (
              <button
                key={s.value}
                onClick={() => setStatusFilter(s.value)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap transition-smooth cursor-pointer ${
                  statusFilter === s.value
                    ? "bg-[var(--color-teal)] text-white font-bold shadow-xs"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden lg:block" />

          {/* Region Facet */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-subtle)] mr-1">
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
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-smooth cursor-pointer ${
                  regionFilter === r.value
                    ? "bg-[var(--color-navy)] text-[var(--color-teal)] font-bold shadow-xs border border-white/10"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden lg:block" />

          {/* GRD Facet */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--ink-subtle)] mr-1">
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
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-smooth cursor-pointer ${
                  grdFilter === g.value
                    ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)] font-bold shadow-xs"
                    : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Leads Table Container */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-xs">
        {isLoading ? (
          <div className="p-6 space-y-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-4 py-2.5 border-b border-[var(--border)]/40">
                <div className="flex items-center gap-3">
                  <Skeleton className="h-9 w-9 rounded-full" />
                  <div className="space-y-1">
                    <Skeleton className="h-4 w-36" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
                <Skeleton className="h-6 w-24 rounded-full" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="p-14 text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
            <h3 className="text-sm font-bold text-[var(--ink)]">Erreur de chargement des prospects</h3>
            <p className="text-xs text-[var(--ink-muted)]">Impossible de synchroniser les données avec le serveur.</p>
            <Button variant="secondary" size="sm" onClick={() => refetch()} className="cursor-pointer">
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              <span>{t("common.retry") || "Réessayer"}</span>
            </Button>
          </div>
        ) : filteredData.length === 0 ? (
          <div className="p-16 text-center space-y-4">
            <div className="w-14 h-14 rounded-full bg-[var(--surface-hover)] border border-[var(--border)] flex items-center justify-center mx-auto text-[var(--ink-subtle)]">
              <UserCheck className="w-7 h-7" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--ink)]">Aucun prospect correspondant</h3>
              <p className="text-xs text-[var(--ink-muted)] mt-1 max-w-sm mx-auto">
                Modifiez vos termes de recherche ou réinitialisez les filtres pour afficher l'ensemble de votre base.
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={clearAllFilters} className="cursor-pointer">
              <span>Réinitialiser tous les filtres</span>
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[var(--surface-hover)]/70 border-b border-[var(--border)] text-[var(--ink-muted)] uppercase tracking-wider text-[10px] font-bold">
                <tr>
                  <th
                    className="px-4 py-3.5 font-bold cursor-pointer hover:text-[var(--ink)] transition-smooth"
                    onClick={() => {
                      if (sortField === "name") setSortAsc(!sortAsc);
                      else {
                        setSortField("name");
                        setSortAsc(true);
                      }
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <span>Prospect & Coordonnées</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3.5 font-bold cursor-pointer hover:text-[var(--ink)] transition-smooth"
                    onClick={() => {
                      if (sortField === "status") setSortAsc(!sortAsc);
                      else {
                        setSortField("status");
                        setSortAsc(true);
                      }
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <span>Statut Qualification</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="px-3 py-3.5 font-bold text-center">Langue</th>
                  <th className="px-4 py-3.5 font-bold">Région & GRD</th>
                  <th className="px-3 py-3.5 font-bold text-center">Équipements</th>
                  <th className="px-4 py-3.5 font-bold">Code EAN (18 chiffres)</th>
                  <th
                    className="px-4 py-3.5 font-bold cursor-pointer hover:text-[var(--ink)] transition-smooth"
                    onClick={() => {
                      if (sortField === "date") setSortAsc(!sortAsc);
                      else {
                        setSortField("date");
                        setSortAsc(false);
                      }
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <span>Dernier Contact</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="px-4 py-3.5 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] bg-[var(--surface)]">
                {filteredData.map((lead) => {
                  const isOptOut = lead.status === "OPT_OUT";
                  const fullName = [lead.first_name, lead.last_name].filter(Boolean).join(" ");
                  const isCustomer = lead.status === "CUSTOMER" || lead.status === "CONTRACT";

                  // Friendly display name
                  const displayName = isOptOut
                    ? "Prospect Purge RGPD"
                    : fullName
                    ? fullName
                    : lead.telegram_chat_id
                    ? `Prospect Telegram #${lead.telegram_chat_id.slice(0, 6)}`
                    : "Visiteur Simulateur Web";

                  // Initials
                  const initials = isOptOut
                    ? "XX"
                    : fullName
                    ? fullName
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()
                    : lead.telegram_chat_id
                    ? "TG"
                    : "SW";

                  // Subtitle info
                  const subtitle = isOptOut
                    ? "Données PII effacées (Droit à l'oubli)"
                    : lead.phone
                    ? lead.phone
                    : lead.email
                    ? lead.email
                    : lead.telegram_chat_id
                    ? "Canal Telegram Bot"
                    : "Canal Web Chat";

                  const lang = resolveLang(lead);
                  const region = resolveRegion(lead);
                  const grd = resolveGrd(lead);

                  // Equipment flags
                  const hasEquip = lead.has_ev || lead.has_heat_pump || lead.has_battery;

                  const rawEan = lead.ean || (lead.notes?.includes("5414") ? "5414" + "000".repeat(4) : null);
                  const displayEan = rawEan ? `${rawEan.slice(0, 4)} •••• ${rawEan.slice(-4)}` : null;

                  const date = lead.last_contact_date || lead.created_at;

                  return (
                    <tr
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className={`hover:bg-[var(--surface-hover)]/70 transition-smooth cursor-pointer group ${
                        isOptOut ? "bg-pink-500/5 opacity-75" : ""
                      }`}
                    >
                      {/* 1. Prospect info with avatar */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 transition-smooth shadow-2xs ${
                              isOptOut
                                ? "bg-rose-500/15 text-rose-500 border border-rose-500/30"
                                : isCustomer
                                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-bold"
                                : "bg-[var(--color-teal)]/15 text-[var(--color-teal)] border border-[var(--color-teal)]/25 group-hover:scale-105"
                            }`}
                          >
                            {initials}
                          </div>
                          <div className="overflow-hidden max-w-[200px] sm:max-w-xs">
                            <span
                              className={`font-semibold text-xs block truncate ${
                                isOptOut ? "line-through text-rose-600 dark:text-rose-400" : "text-[var(--ink)]"
                              }`}
                            >
                              {displayName}
                            </span>
                            <span className="text-[11px] text-[var(--ink-muted)] flex items-center gap-1 truncate font-mono">
                              {lead.phone ? (
                                <Phone className="w-2.5 h-2.5 text-[var(--color-teal)] shrink-0" />
                              ) : lead.email ? (
                                <Mail className="w-2.5 h-2.5 text-blue-500 shrink-0" />
                              ) : lead.telegram_chat_id ? (
                                <Send className="w-2.5 h-2.5 text-emerald-500 shrink-0" />
                              ) : (
                                <Globe className="w-2.5 h-2.5 text-[var(--ink-subtle)] shrink-0" />
                              )}
                              <span>{subtitle}</span>
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* 2. Status Badge */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <Badge variant={lead.status as LeadStatus} />
                      </td>

                      {/* 3. Language */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-md bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)]">
                          {lang === "FR" ? "🇫🇷 FR" : "🇳🇱 NL"}
                        </span>
                      </td>

                      {/* 4. Region & GRD */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="space-y-0.5">
                          <span className="font-medium text-xs text-[var(--ink)] block">{region}</span>
                          <span className="text-[10px] font-mono text-[var(--color-teal)] block font-semibold">
                            GRD : {grd}
                          </span>
                        </div>
                      </td>

                      {/* 5. Equipment icons (Motion pitch triggers) */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        {hasEquip ? (
                          <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 text-[10px] font-semibold">
                            {lead.has_ev && <span title="Véhicule Électrique"><Car className="w-3 h-3" /></span>}
                            {lead.has_heat_pump && <span title="Pompe à chaleur"><Flame className="w-3 h-3" /></span>}
                            {lead.has_battery && <span title="Batterie domestique"><BatteryCharging className="w-3 h-3" /></span>}
                            <span className="font-bold font-mono">Motion</span>
                          </div>
                        ) : (
                          <span className="text-[10px] font-mono text-[var(--ink-subtle)] px-2 py-0.5 rounded bg-[var(--surface-hover)]">
                            Standard
                          </span>
                        )}
                      </td>

                      {/* 6. EAN Code */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {isOptOut ? (
                          <span className="text-[var(--ink-subtle)] font-mono">—</span>
                        ) : displayEan ? (
                          <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--surface-hover)] border border-[var(--border)] font-mono text-[11px] text-[var(--ink)] group-hover:border-[var(--color-teal)]/40 transition-smooth">
                            <span>{displayEan}</span>
                            <button
                              onClick={(e) => copyEan(rawEan!, e)}
                              title="Copier le code EAN complet"
                              className="p-1 rounded hover:bg-[var(--border)] text-[var(--ink-subtle)] hover:text-[var(--ink)] transition-smooth cursor-pointer"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                        ) : (
                          <span className="text-[var(--ink-subtle)] font-mono text-[11px]">—</span>
                        )}
                      </td>

                      {/* 7. Last Contact Date */}
                      <td className="px-4 py-3 whitespace-nowrap font-mono text-[11px] text-[var(--ink-muted)]">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-[var(--ink-subtle)]" />
                          <span>{new Date(date).toLocaleDateString("fr-BE")}</span>
                        </div>
                      </td>

                      {/* 8. Quick Action */}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedLead(lead);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[var(--border)] hover:border-[var(--color-teal)] hover:bg-[var(--color-teal-soft)] text-xs font-semibold text-[var(--ink)] transition-smooth cursor-pointer shadow-2xs group-hover:bg-[var(--surface)]"
                        >
                          <span>Fiche</span>
                          <ChevronRight className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                        </button>
                      </td>
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

      {/* Add Lead Modal */}
      <AddLeadModal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} />

      {/* CSV Upload Modal */}
      <CsvUploadModal
        isOpen={isCsvModalOpen}
        onClose={() => setIsCsvModalOpen(false)}
        onSuccess={() => {
          refetch();
        }}
      />

      {/* Rich Export Modal (Excel / CSV) */}
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

export default LeadsPage;
