import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { ContractSummary, ContractStatus } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import {
  FileCheck2,
  Download,
  Eye,
  CheckCircle2,
  Clock,
  Sparkles,
  Search,
  FileText,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Zap,
  ArrowUpDown,
  Filter,
  X,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

export const ContractsPage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [productFilter, setProductFilter] = useState<string>("ALL");
  const [selectedContract, setSelectedContract] = useState<ContractSummary | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);

  const {
    data: contractsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => apiClient.getContracts({ limit: 100 }),
    staleTime: 15000,
  });

  const simulateSignMutation = useMutation({
    mutationFn: (contractId: string) => apiClient.simulateSignContract(contractId),
    onSuccess: (updatedContract) => {
      queryClient.invalidateQueries({ queryKey: ["contracts"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      toast.success(
        `Contrat ${updatedContract.id.slice(0, 8)} signé avec succès ! Cachet eIDAS appliqué au PDF.`
      );
      if (selectedContract?.id === updatedContract.id) {
        setSelectedContract(updatedContract);
      }
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Erreur lors de la simulation de signature";
      toast.error(msg);
    },
  });

  const handleDownload = async (contract: ContractSummary, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const filename = `contrat_ecofix_${contract.product.toLowerCase()}_${contract.id.slice(0, 8)}.pdf`;
      await apiClient.downloadContractPdf(contract.id, filename);
      toast.success("Téléchargement du contrat PDF lancé !");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de télécharger le contrat";
      toast.error(msg);
    }
  };

  const handleSimulateSign = (contract: ContractSummary, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    simulateSignMutation.mutate(contract.id);
  };

  const items = contractsData?.items || [];

  // Filtered dataset
  const filteredContracts = useMemo(() => {
    return items.filter((c) => {
      if (statusFilter !== "ALL" && c.status !== statusFilter) return false;
      if (productFilter !== "ALL" && c.product.toUpperCase() !== productFilter) return false;
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchesName = (c.lead_name || "").toLowerCase().includes(query);
        const matchesEmail = (c.lead_email || "").toLowerCase().includes(query);
        const matchesId = c.id.toLowerCase().includes(query);
        const matchesProduct = c.product.toLowerCase().includes(query);
        if (!matchesName && !matchesEmail && !matchesId && !matchesProduct) return false;
      }
      return true;
    });
  }, [items, statusFilter, productFilter, searchTerm]);

  // Derived KPI calculations
  const totalCount = items.length;
  const signedCount = items.filter((c) => c.status === "SIGNED").length;
  const pendingCount = items.filter((c) => c.status === "SENT" || c.status === "DRAFT").length;
  const conversionRate = totalCount > 0 ? Math.round((signedCount / totalCount) * 100) : 0;
  const estimatedArr = signedCount * 60; // 60 €/an base fee guaranteed

  const getStatusBadge = (status: ContractStatus) => {
    switch (status) {
      case "SIGNED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            Signé (Certifié)
          </span>
        );
      case "SENT":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            <Clock className="w-3 h-3 text-amber-600 dark:text-amber-400" />
            En attente signature
          </span>
        );
      case "DRAFT":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
            Brouillon PDF
          </span>
        );
      case "WITHDRAWN":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-pink-100 text-pink-800 dark:bg-pink-950/60 dark:text-pink-300 border border-pink-300 dark:border-pink-800 line-through">
            Rétracté (14j)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800">
            {status}
          </span>
        );
    }
  };

  const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return String(iso);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-teal-500/15 border border-teal-500/25 flex items-center justify-center text-teal-600 dark:text-teal-400">
              <FileCheck2 className="w-5 h-5" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
              Contrats & Ventes Énergie
            </h1>
          </div>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Gestion du cycle de vie des contrats générés par Sophie, signature électronique Yousign Sandbox certifiée eIDAS et conformité légale CWaPE / VREG.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            <span>Actualiser</span>
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5">
        <Card className="p-4 bg-[var(--surface)] border border-[var(--border)] shadow-xs">
          <span className="text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider block">
            Total Contrats
          </span>
          <div className="text-2xl font-bold text-[var(--ink)] mt-1">{totalCount}</div>
          <span className="text-[10px] text-[var(--ink-subtle)] mt-0.5 block">
            Générés par Sophie AI
          </span>
        </Card>

        <Card className="p-4 bg-emerald-50/40 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40 shadow-xs">
          <span className="text-[11px] font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider block">
            Contrats Signés
          </span>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {signedCount}
          </div>
          <span className="text-[10px] text-emerald-700 dark:text-emerald-400 mt-0.5 block">
            Certifiés eIDAS Yousign
          </span>
        </Card>

        <Card className="p-4 bg-amber-50/40 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 shadow-xs">
          <span className="text-[11px] font-semibold text-amber-800 dark:text-amber-300 uppercase tracking-wider block">
            En Attente
          </span>
          <div className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {pendingCount}
          </div>
          <span className="text-[10px] text-amber-700 dark:text-amber-400 mt-0.5 block">
            Lien transmis au prospect
          </span>
        </Card>

        <Card className="p-4 bg-[var(--surface)] border border-[var(--border)] shadow-xs">
          <span className="text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider block">
            Taux de Signature
          </span>
          <div className="text-2xl font-bold text-teal-600 dark:text-teal-400 mt-1">
            {conversionRate} %
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] mt-0.5 block">
            Ratio signés / émis
          </span>
        </Card>

        <Card className="p-4 bg-[var(--surface)] border border-[var(--border)] shadow-xs col-span-2 lg:col-span-1">
          <span className="text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider block">
            Revenu Récurrent Fixe
          </span>
          <div className="text-2xl font-bold text-[var(--ink)] mt-1">
            {estimatedArr.toLocaleString("fr-BE")} €/an
          </div>
          <span className="text-[10px] text-[var(--ink-subtle)] mt-0.5 block">
            Base 60 €/an par contrat actif
          </span>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[var(--surface)] border border-[var(--border)] p-3 rounded-[0.75rem] shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search bar */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)]" />
            <input
              type="text"
              placeholder="Rechercher par prospect, email ou ID contrat..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 transition-smooth"
            />
          </div>

          {/* Counters */}
          <div className="flex items-center gap-2 text-xs font-mono text-[var(--ink-muted)] self-end md:self-auto">
            <span>{filteredContracts.length} contrat(s) affiché(s)</span>
          </div>
        </div>

        {/* Status & Product Badges filters */}
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-[var(--border)] text-xs">
          <span className="text-[var(--ink-muted)] font-medium flex items-center gap-1 mr-1">
            <Filter className="w-3 h-3" /> Statut :
          </span>
          {["ALL", "SIGNED", "SENT", "DRAFT", "WITHDRAWN"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-smooth cursor-pointer ${
                statusFilter === st
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                  : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
            >
              {st === "ALL"
                ? "Tous"
                : st === "SIGNED"
                ? "Signés"
                : st === "SENT"
                ? "En attente"
                : st === "DRAFT"
                ? "Brouillons"
                : "Rétractés"}
            </button>
          ))}

          <span className="text-[var(--ink-muted)] font-medium flex items-center gap-1 ml-3 mr-1">
            Offre :
          </span>
          {["ALL", "FLEXY", "MOTION"].map((prod) => (
            <button
              key={prod}
              onClick={() => setProductFilter(prod)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-smooth cursor-pointer ${
                productFilter === prod
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-[var(--surface-hover)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
              }`}
            >
              {prod === "ALL" ? "Toutes" : prod === "FLEXY" ? "Flexy (Variable)" : "Motion (Dynamique)"}
            </button>
          ))}
        </div>
      </div>

      {/* Contracts Table */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3 text-[var(--ink-muted)]">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
            <span className="text-xs">Chargement des contrats en cours...</span>
          </div>
        ) : filteredContracts.length === 0 ? (
          <div className="p-12 text-center text-[var(--ink-muted)] space-y-2">
            <FileText className="w-8 h-8 mx-auto text-[var(--ink-subtle)] stroke-1" />
            <p className="text-sm font-semibold text-[var(--ink)]">Aucun contrat trouvé</p>
            <p className="text-xs max-w-sm mx-auto">
              {items.length === 0
                ? "Sophie génère automatiquement les contrats dès qu'un prospect est qualifié (Flexy ou Motion) et valide ses coordonnées."
                : "Aucun contrat ne correspond aux critères de recherche ou filtres sélectionnés."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-hover)]/60 text-[var(--ink-muted)] font-semibold">
                  <th className="py-3 px-4">Client / Prospect</th>
                  <th className="py-3 px-3">Offre Énergie</th>
                  <th className="py-3 px-3">Option Digi</th>
                  <th className="py-3 px-3">Statut e-Signature</th>
                  <th className="py-3 px-3">Date d'émission</th>
                  <th className="py-3 px-3">Date signature</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredContracts.map((c) => {
                  const isSigned = c.status === "SIGNED";
                  const isFlexy = c.product.toLowerCase().includes("flexy");

                  return (
                    <tr
                      key={c.id}
                      onClick={() => setSelectedContract(c)}
                      className="hover:bg-[var(--surface-hover)]/50 transition-colors cursor-pointer group"
                    >
                      <td className="py-3 px-4">
                        <div className="font-semibold text-[var(--ink)] flex items-center gap-1.5">
                          <span>{c.lead_name || "Client Prospect"}</span>
                        </div>
                        <div className="text-[11px] text-[var(--ink-muted)] mt-0.5">
                          {c.lead_email || c.lead_phone || `ID: ${c.lead_id.slice(0, 8)}`}
                        </div>
                      </td>

                      <td className="py-3 px-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                            isFlexy
                              ? "bg-teal-50 text-teal-800 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800"
                              : "bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800"
                          }`}
                        >
                          Ecofix {c.product}
                        </span>
                      </td>

                      <td className="py-3 px-3">
                        {c.digi_subscribed ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-600 dark:text-teal-400">
                            <Sparkles className="w-3 h-3" /> 5,99 €/m
                          </span>
                        ) : (
                          <span className="text-[11px] text-[var(--ink-subtle)]">Non</span>
                        )}
                      </td>

                      <td className="py-3 px-3">{getStatusBadge(c.status)}</td>

                      <td className="py-3 px-3 font-mono text-[11px] text-[var(--ink-muted)]">
                        {formatDate(c.created_at)}
                      </td>

                      <td className="py-3 px-3 font-mono text-[11px]">
                        {c.signed_at ? (
                          <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                            {formatDate(c.signed_at)}
                          </span>
                        ) : (
                          <span className="text-[var(--ink-subtle)]">-</span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          {!isSigned && (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={(e) => handleSimulateSign(c, e)}
                              disabled={simulateSignMutation.isPending}
                              className="text-[11px] h-7 px-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
                            >
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              <span>Simuler Signature</span>
                            </Button>
                          )}

                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => handleDownload(c, e)}
                            className="text-[11px] h-7 px-2"
                            title="Télécharger le contrat PDF ReportLab"
                          >
                            <Download className="w-3 h-3 text-[var(--ink-muted)]" />
                          </Button>

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedContract(c)}
                            className="text-[11px] h-7 px-2"
                            title="Voir les détails et le certificat"
                          >
                            <Eye className="w-3 h-3 text-[var(--ink-muted)]" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Contract Detail & Visual Stamp Modal */}
      {selectedContract && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4 animate-in zoom-in-95 duration-200">
            {/* Close button */}
            <button
              onClick={() => setSelectedContract(null)}
              className="absolute top-4 right-4 p-1.5 rounded-full text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Header */}
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-teal-500/15 border border-teal-500/25 flex items-center justify-center text-teal-600 dark:text-teal-400 shrink-0">
                <FileCheck2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[var(--ink)] tracking-tight">
                  Contrat de fourniture Ecofix {selectedContract.product}
                </h3>
                <p className="text-xs text-[var(--ink-muted)] mt-0.5">
                  ID: <span className="font-mono">{selectedContract.id}</span>
                </p>
              </div>
            </div>

            {/* Status & Details */}
            <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface-hover)]/50 space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]">
                <span className="text-[var(--ink-muted)]">Statut du contrat :</span>
                <div>{getStatusBadge(selectedContract.status)}</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[var(--ink-muted)] block">Souscripteur :</span>
                  <span className="font-semibold text-[var(--ink)] block mt-0.5">
                    {selectedContract.lead_name || "Client Prospect"}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--ink-muted)] block">Contact :</span>
                  <span className="font-medium text-[var(--ink)] block mt-0.5">
                    {selectedContract.lead_email || selectedContract.lead_phone || "-"}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--ink-muted)] block">Frais fixes obligatoires :</span>
                  <span className="font-semibold text-[var(--ink)] block mt-0.5">
                    60,00 € TTC / an (5 €/mois)
                  </span>
                </div>
                <div>
                  <span className="text-[var(--ink-muted)] block">Option Ecofix Digi :</span>
                  <span className="font-medium text-[var(--ink)] block mt-0.5">
                    {selectedContract.digi_subscribed ? "Souscrite (+5,99 €/mois)" : "Non souscrite"}
                  </span>
                </div>
              </div>
            </div>

            {/* eIDAS Signature Certification Box */}
            {selectedContract.status === "SIGNED" ? (
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800/60 text-xs space-y-2">
                <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-bold">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>Certificat de Signature Électronique eIDAS (Yousign v3)</span>
                </div>
                <div className="space-y-1 text-emerald-900/90 dark:text-emerald-200/90 text-[11px]">
                  <p>
                    • <strong>Signataire certifié :</strong> {selectedContract.lead_name || "Souscripteur"}
                  </p>
                  <p>
                    • <strong>Horodatage cryptographique :</strong> {formatDate(selectedContract.signed_at)}
                  </p>
                  <p className="font-mono text-[10px] text-emerald-800/80 dark:text-emerald-300/80">
                    • <strong>Transaction ID :</strong> {selectedContract.id.replace(/-/g, "").toUpperCase()}
                  </p>
                  <p className="text-[10px] italic pt-1">
                    Conforme au Code de droit économique belge et au Règlement européen sur l'Intelligence Artificielle (AI Act, Art. 50).
                  </p>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800/60 text-xs space-y-2">
                <div className="flex items-center gap-2 text-amber-800 dark:text-amber-300 font-bold">
                  <Clock className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>En attente de signature par le prospect</span>
                </div>
                <p className="text-[11px] text-amber-900/90 dark:text-amber-200/90 leading-relaxed">
                  Le contrat PDF ReportLab a été préparé avec succès. Pour la démonstration, vous pouvez déclencher immédiatement la signature électronique simulée ci-dessous.
                </p>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedContract(null)}
              >
                Fermer
              </Button>

              <div className="flex items-center gap-2">
                {selectedContract.status !== "SIGNED" && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSimulateSign(selectedContract)}
                    disabled={simulateSignMutation.isPending}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
                  >
                    {simulateSignMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                    )}
                    <span>Simuler la Signature Client</span>
                  </Button>
                )}

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleDownload(selectedContract)}
                  className="font-semibold"
                >
                  <Download className="w-3.5 h-3.5 mr-1 text-teal-600" />
                  <span>Télécharger le PDF Certifié</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
