import React from "react";
import { useTranslation } from "react-i18next";
import { X, FileSpreadsheet, FileText, CheckCircle2, Sparkles, Download } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  itemCount?: number;
  itemLabel?: string;
  onExportExcel: () => void;
  onExportCsv: () => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  itemCount,
  itemLabel = "éléments",
  onExportExcel,
  onExportCsv,
}) => {
  const { t } = useTranslation();

  if (!isOpen) return null;

  const handleExcel = () => {
    onExportExcel();
    onClose();
  };

  const handleCsv = () => {
    onExportCsv();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl transition-all animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-full text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors"
          aria-label="Fermer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3.5 mb-6">
          <div className="w-10 h-10 rounded-xl bg-teal/15 border border-teal/20 flex items-center justify-center text-teal-dim shrink-0">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-[var(--ink)] tracking-tight">
              {title}
            </h3>
            <p className="text-xs text-[var(--ink-muted)] mt-0.5 leading-relaxed">
              {subtitle || "Choisissez le format adapté à votre besoin pour une lisibilité optimale."}
            </p>
          </div>
        </div>

        {/* Format Selection Cards */}
        <div className="space-y-3.5 mb-6">
          {/* Option 1: Excel Stylisé (Recommandé) */}
          <div
            onClick={handleExcel}
            className="group relative p-4 rounded-xl border-2 border-teal/40 hover:border-teal bg-teal/[0.03] hover:bg-teal/[0.08] transition-all cursor-pointer flex flex-col gap-2.5 shadow-xs"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-teal-dim" />
                <span className="text-sm font-bold text-[var(--ink)]">
                  Tableur Excel Stylisé (.xls)
                </span>
              </div>
              <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-teal/15 text-teal-dim border border-teal/25">
                <Sparkles className="w-3 h-3" /> Recommandé
              </span>
            </div>

            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              Mise en page haute fidélité aux couleurs Ecofix : en-têtes contrastés, largeurs de colonnes ajustées (<strong>zéro coupure ni #####</strong>), badges de statuts colorés et dates parfaitement formatées.
            </p>

            <div className="pt-1 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[11px] text-teal-dim font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Ouvrable instantanément dans Microsoft Excel</span>
              </div>
              <Button
                variant="primary"
                size="sm"
                className="text-xs pointer-events-none group-hover:scale-105 transition-transform"
              >
                <Download className="w-3.5 h-3.5 mr-1" />
                <span>Télécharger Excel</span>
              </Button>
            </div>
          </div>

          {/* Option 2: CSV Optimisé */}
          <div
            onClick={handleCsv}
            className="group relative p-4 rounded-xl border border-[var(--border)] hover:border-[var(--ink-muted)] bg-[var(--surface-hover)]/40 hover:bg-[var(--surface-hover)] transition-all cursor-pointer flex flex-col gap-2.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[var(--ink-muted)]" />
                <span className="text-sm font-semibold text-[var(--ink)]">
                  Fichier CSV Optimisé (.csv)
                </span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[var(--surface)] text-[var(--ink-muted)] border border-[var(--border)]">
                Données Brutes
              </span>
            </div>

            <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
              Format délimité standard point-virgule (;) avec encodage UTF-8 BOM, colonnes ordonnées (coordonnées en tête, identifiants en fin) et protection contre les injections de formules.
            </p>

            <div className="pt-1 flex items-center justify-between">
              <span className="text-[11px] text-[var(--ink-subtle)]">
                Compatible tout tableur &amp; scripts CRM
              </span>
              <Button
                variant="secondary"
                size="sm"
                className="text-xs pointer-events-none group-hover:scale-105 transition-transform"
              >
                <Download className="w-3.5 h-3.5 mr-1" />
                <span>Télécharger CSV</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between pt-3 border-t border-[var(--border)] text-xs text-[var(--ink-muted)]">
          {itemCount !== undefined && (
            <span>
              <strong>{itemCount}</strong> {itemLabel} à exporter
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs ml-auto">
            {t("common.close") || "Fermer"}
          </Button>
        </div>
      </div>
    </div>
  );
};
