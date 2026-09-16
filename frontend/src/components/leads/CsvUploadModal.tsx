import React, { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  X,
  Download,
  ArrowRight,
  RefreshCw,
  Info,
} from "lucide-react";
import { apiClient } from "@/api/client";
import { ImportPreviewResponse, ImportReportResponse } from "@/api/types";
import { toast } from "sonner";

interface CsvUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CsvUploadModal: React.FC<CsvUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvRawText, setCsvRawText] = useState<string>("");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [isImporting, setIsImporting] = useState(false);
  const [importReport, setImportReport] = useState<ImportReportResponse | null>(null);

  if (!isOpen) return null;

  const handleReset = () => {
    setCsvFile(null);
    setCsvRawText("");
    setPreviewData(null);
    setPreviewError(null);
    setImportReport(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDownloadTemplate = () => {
    const templateContent =
      "name;email;phone;region;provider;notes\r\n" +
      "Marc Dupont;marc.dupont@example.be;+32470123456;Wallonie;TotalEnergies;Intéressé par Flexy électricité et gaz\r\n" +
      "Anke Van den Berg;anke.vandenberg@example.be;+32480987654;Flandre;Engie;Chauffage pompe à chaleur, tarif Motion\r\n" +
      "Jean Martin;jean.martin@example.be;+32490555777;Wallonie;Luminus;Compteur bi-horaire\r\n";

    const blob = new Blob(["\uFEFF" + templateContent], {
      type: "text/csv;charset=utf-8;",
    });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", "modele-import-prospects-ecofix.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success(t("leads.csvTemplateDownloaded") || "Modèle CSV téléchargé");
  };

  const processFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setPreviewError(t("leads.csvOnlyError") || "Veuillez sélectionner un fichier au format .CSV");
      return;
    }

    setCsvFile(file);
    setPreviewError(null);
    setPreviewData(null);
    setIsPreviewLoading(true);

    try {
      const text = await file.text();
      setCsvRawText(text);

      if (!text.trim()) {
        setPreviewError("Le fichier CSV est vide.");
        setIsPreviewLoading(false);
        return;
      }

      const preview = await apiClient.previewImportLeads(text);
      setPreviewData(preview);
    } catch (err: any) {
      setPreviewError(err.message || "Erreur lors de l'analyse du fichier CSV");
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleConfirmImport = async () => {
    if (!csvRawText) return;
    setIsImporting(true);
    try {
      const report = await apiClient.importLeads(csvRawText);
      setImportReport(report);
      toast.success(
        t("leads.importSuccessToast", {
          created: report.created,
          updated: report.updated,
        }) || `${report.created} prospects importés, ${report.updated} mis à jour !`
      );
      onSuccess();
    } catch (err: any) {
      toast.error(err.message || "Erreur lors de l'importation");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs z-[70] transition-opacity"
        onClick={() => !isImporting && onClose()}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
        <div
          role="dialog"
          aria-modal="true"
          className="w-full max-w-4xl bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in zoom-in-95 duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 sm:p-5 border-b border-[var(--border)] bg-[var(--surface-hover)]/60">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--color-teal)]/10 border border-[var(--color-teal)]/30 flex items-center justify-center text-[var(--color-teal)] shrink-0 shadow-xs">
                <FileSpreadsheet className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-bold text-[var(--ink)] tracking-tight">
                  {t("leads.csvUploadModalTitle") || "Importation de Prospects par Fichier CSV"}
                </h2>
                <p className="text-xs text-[var(--ink-muted)]">
                  {t("leads.csvUploadModalSubtitle") ||
                    "Prévisualisation instantanée, validation des données et déduplication automatique dans le CRM."}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] text-xs font-semibold transition-smooth cursor-pointer shadow-xs"
                title="Télécharger le modèle CSV officiel avec les colonnes acceptées"
              >
                <Download className="w-3.5 h-3.5 text-[var(--color-teal)]" />
                <span className="hidden sm:inline">
                  {t("leads.downloadSampleCsv") || "Modèle CSV"}
                </span>
              </button>

              <button
                onClick={() => !isImporting && onClose()}
                disabled={isImporting}
                className="p-2 rounded-lg text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer disabled:opacity-50"
                type="button"
                aria-label="Fermer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="p-4 sm:p-6 overflow-y-auto space-y-5 flex-1">
            {/* Step 1: Upload Zone if no preview yet */}
            {!previewData && !importReport && (
              <div className="space-y-4">
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-200 ${
                    isPreviewLoading
                      ? "border-[var(--color-teal)] bg-[var(--color-teal)]/5"
                      : "border-[var(--border)] hover:border-[var(--color-teal)] hover:bg-[var(--surface-hover)]/50 bg-[var(--surface)]"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleFileChange}
                    className="hidden"
                  />

                  {isPreviewLoading ? (
                    <div className="flex flex-col items-center justify-center space-y-3">
                      <Loader2 className="w-10 h-10 text-[var(--color-teal)] animate-spin" />
                      <p className="text-sm font-semibold text-[var(--ink)]">
                        {t("leads.analyzingCsv") || "Analyse et vérification des données CSV..."}
                      </p>
                      <p className="text-xs text-[var(--ink-muted)]">
                        Détection des séparateurs, colonnes et vérification des doublons
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center space-y-3">
                      <div className="w-14 h-14 rounded-2xl bg-[var(--color-teal)]/10 text-[var(--color-teal)] flex items-center justify-center mb-1 shadow-xs group-hover:scale-105 transition-transform">
                        <UploadCloud className="w-7 h-7" />
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm font-bold text-[var(--ink)]">
                          {t("leads.dragDropCsvPrompt") ||
                            "Glissez-déposez votre fichier CSV ici, ou cliquez pour parcourir"}
                        </p>
                        <p className="text-xs text-[var(--ink-muted)]">
                          Format supporté : <strong>.CSV</strong> (séparateur virgule ou point-virgule, UTF-8 recommandé)
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          name
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          email
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          phone
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          region
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          provider
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-[var(--surface-hover)] text-[var(--ink-muted)] border border-[var(--border)]">
                          notes
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {previewError && (
                  <div className="p-3.5 rounded-xl bg-danger/10 border border-danger/20 text-danger text-xs flex items-center gap-2.5 animate-in fade-in duration-200">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{previewError}</span>
                  </div>
                )}

                {/* Info Note */}
                <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface-hover)]/40 flex items-start gap-3 text-xs text-[var(--ink-muted)]">
                  <Info className="w-4 h-4 text-[var(--color-teal)] shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <span className="font-semibold text-[var(--ink)] block">
                      Règle de déduplication stricte
                    </span>
                    <p className="leading-relaxed">
                      Si un prospect existe déjà avec le même email ou téléphone, ses nouvelles informations seront complétées sans jamais écraser les données existantes. Aucun prospect ne sera créé en double.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Live Preview Table */}
            {previewData && !importReport && (
              <div className="space-y-4 animate-in fade-in duration-200">
                {/* File info bar & Metrics */}
                <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface-hover)]/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <FileSpreadsheet className="w-4 h-4 text-[var(--color-teal)]" />
                    <span className="text-xs font-bold text-[var(--ink)]">
                      {csvFile?.name}
                    </span>
                    {csvFile && (
                      <span className="text-[11px] text-[var(--ink-muted)] font-mono">
                        ({(csvFile.size / 1024).toFixed(1)} KB)
                      </span>
                    )}
                  </div>

                  {/* Summary Chips */}
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="px-2.5 py-1 rounded-full font-bold bg-[var(--color-navy)] text-white text-[11px]">
                      {previewData.total_rows} lignes
                    </span>
                    <span className="px-2.5 py-1 rounded-full font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-[11px]">
                      {previewData.rows.filter((r) => !r.would_be_duplicate && !r.missing_identifier).length} nouveaux
                    </span>
                    <span className="px-2.5 py-1 rounded-full font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20 text-[11px]">
                      {previewData.rows.filter((r) => r.would_be_duplicate).length} doublons (mise à jour)
                    </span>
                    {previewData.rows_missing_identifier > 0 && (
                      <span className="px-2.5 py-1 rounded-full font-bold bg-danger/10 text-danger border border-danger/20 text-[11px]">
                        {previewData.rows_missing_identifier} sans contact
                      </span>
                    )}
                  </div>
                </div>

                {/* Table container with styled UI/UX */}
                <div className="border border-[var(--border)] rounded-xl bg-[var(--surface)] overflow-hidden shadow-xs">
                  <div className="overflow-x-auto max-h-[380px]">
                    <table className="w-full text-left text-xs text-[var(--ink)]">
                      <thead className="sticky top-0 z-10 bg-[var(--surface-hover)] border-b-2 border-[var(--border)] shadow-xs">
                        <tr>
                          <th className="p-3 text-center font-bold text-xs uppercase tracking-wider text-[var(--ink)] w-12">
                            #
                          </th>
                          <th className="p-3 text-left font-bold text-xs uppercase tracking-wider text-[var(--ink)]">
                            Statut de Validation
                          </th>
                          {previewData.headers.map((h) => (
                            <th
                              key={h}
                              className="p-3 text-left font-bold text-xs uppercase tracking-wider text-[var(--ink)] font-mono"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {previewData.rows.map((row) => {
                          const isDup = row.would_be_duplicate;
                          const isMissing = row.missing_identifier;

                          return (
                            <tr
                              key={row.row_number}
                              className={`transition-colors duration-150 hover:bg-[var(--surface-hover)]/60 ${
                                isMissing
                                  ? "bg-danger/5"
                                  : isDup
                                  ? "bg-amber-500/5"
                                  : "even:bg-[var(--surface-hover)]/20"
                              }`}
                            >
                              {/* Row number */}
                              <td className="p-3 text-center text-[11px] font-mono text-[var(--ink-muted)]">
                                {row.row_number}
                              </td>

                              {/* Validation Status Badge */}
                              <td className="p-3 whitespace-nowrap">
                                {isMissing ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-danger/10 text-danger border border-danger/20">
                                    <XCircle className="w-3 h-3" />
                                    <span>Sans contact</span>
                                  </span>
                                ) : isDup ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                    <AlertTriangle className="w-3 h-3" />
                                    <span>Doublon (MàJ)</span>
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                                    <CheckCircle2 className="w-3 h-3" />
                                    <span>Nouveau</span>
                                  </span>
                                )}
                              </td>

                              {/* CSV data cells */}
                              {previewData.headers.map((h) => {
                                const val = row.data[h] ?? "";
                                const isIdField = h === "email" || h === "phone";
                                return (
                                  <td
                                    key={h}
                                    className={`p-3 max-w-[200px] truncate text-[11px] ${
                                      isIdField ? "font-mono font-medium text-[var(--ink)]" : "text-[var(--ink-muted)]"
                                    }`}
                                  >
                                    {val ? String(val) : <span className="text-[var(--ink-subtle)]">—</span>}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Final Import Report */}
            {importReport && (
              <div className="p-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 space-y-5 text-center animate-in zoom-in-95 duration-200">
                <div className="w-14 h-14 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center mx-auto shadow-xs">
                  <CheckCircle2 className="w-8 h-8" />
                </div>

                <div className="space-y-1">
                  <h3 className="text-lg font-bold text-[var(--ink)]">
                    {t("leads.importSuccessTitle") || "Importation terminée avec succès !"}
                  </h3>
                  <p className="text-xs text-[var(--ink-muted)]">
                    {importReport.rows_read} lignes traitées en {importReport.duration_seconds.toFixed(2)} secondes.
                  </p>
                </div>

                {/* Metrics Breakdown Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-xl mx-auto pt-2">
                  <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                    <span className="text-[11px] font-semibold text-[var(--ink-muted)] block">
                      Nouveaux créés
                    </span>
                    <span className="text-xl font-bold text-[var(--color-teal)] block mt-1">
                      {importReport.created}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                    <span className="text-[11px] font-semibold text-[var(--ink-muted)] block">
                      Mis à jour
                    </span>
                    <span className="text-xl font-bold text-amber-500 block mt-1">
                      {importReport.updated}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                    <span className="text-[11px] font-semibold text-[var(--ink-muted)] block">
                      Doublons gérés
                    </span>
                    <span className="text-xl font-bold text-[var(--color-navy)] block mt-1">
                      {importReport.duplicates}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xs">
                    <span className="text-[11px] font-semibold text-[var(--ink-muted)] block">
                      Ignorés / Erreurs
                    </span>
                    <span className="text-xl font-bold text-[var(--ink-muted)] block mt-1">
                      {importReport.skipped + importReport.errors}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 sm:p-5 border-t border-[var(--border)] bg-[var(--surface-hover)]/60 flex items-center justify-between gap-3">
            <div>
              {previewData && !importReport && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] transition-smooth cursor-pointer"
                >
                  Choisir un autre fichier
                </button>
              )}
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={onClose}
                disabled={isImporting}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface)] transition-smooth cursor-pointer disabled:opacity-50"
              >
                {importReport ? t("common.close") || "Fermer" : t("common.cancel") || "Annuler"}
              </button>

              {previewData && !importReport && (
                <button
                  type="button"
                  onClick={handleConfirmImport}
                  disabled={isImporting || previewData.rows.length === 0}
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-[var(--color-teal)] hover:bg-[var(--color-teal-hover)] text-white text-xs font-bold shadow-md transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {isImporting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                  <span>
                    {isImporting
                      ? t("leads.importing") || "Importation en cours..."
                      : t("leads.confirmImportButton", { count: previewData.total_rows }) ||
                        `Confirmer l'import (${previewData.total_rows} prospects)`}
                  </span>
                </button>
              )}

              {importReport && (
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-[var(--color-navy)] text-white text-xs font-bold hover:opacity-90 shadow-md transition-smooth cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>{t("leads.viewLeads") || "Voir les prospects à jour"}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
