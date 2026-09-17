import React, { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { apiClient } from "@/api/client";
import { ContractSummary } from "@/api/types";
import { Button } from "@/components/ui/Button";
import {
  FileCheck2,
  Download,
  CheckCircle2,
  Clock,
  ShieldCheck,
  X,
  Loader2,
  PenTool,
  RotateCcw,
  Eye,
  FileText,
  Lock,
  Calendar,
  User,
  Building2,
  Zap,
  Sparkles,
  ExternalLink,
  Check,
} from "lucide-react";
import { toast } from "sonner";

interface ContractVisualViewerModalProps {
  contract: ContractSummary | null;
  isOpen: boolean;
  onClose: () => void;
  onContractSigned?: (updatedContract: ContractSummary) => void;
  initialSignStudioOpen?: boolean;
}

export const ContractVisualViewerModal: React.FC<ContractVisualViewerModalProps> = ({
  contract,
  isOpen,
  onClose,
  onContractSigned,
  initialSignStudioOpen = false,
}) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"document" | "pdf">("document");
  const [isSignStudioOpen, setIsSignStudioOpen] = useState(false);
  const [isSigning, setIsSigning] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [signatureImage, setSignatureImage] = useState<string | null>(null);
  const [currentContract, setCurrentContract] = useState<ContractSummary | null>(contract);

  // Sync prop changes & initial studio open
  useEffect(() => {
    setCurrentContract(contract);
    if (isOpen && initialSignStudioOpen && contract?.status !== "SIGNED") {
      setIsSignStudioOpen(true);
    } else {
      setIsSignStudioOpen(false);
    }
  }, [contract, isOpen, initialSignStudioOpen]);

  if (!isOpen || !currentContract) return null;

  const isSigned = currentContract.status === "SIGNED";

  const handleDownloadPdf = async () => {
    try {
      setIsDownloading(true);
      const filename = `contrat_ecofix_${currentContract.product.toLowerCase()}_${currentContract.id.slice(0, 8)}.pdf`;
      await apiClient.downloadContractPdf(currentContract.id, filename);
      toast.success("Contrat PDF téléchargé avec succès !");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur lors du téléchargement du contrat.";
      toast.error(msg);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleSignatureSuccess = (updated: ContractSummary, sigImg?: string) => {
    setCurrentContract(updated);
    if (sigImg) {
      setSignatureImage(sigImg);
    }
    setIsSignStudioOpen(false);
    if (onContractSigned) {
      onContractSigned(updated);
    }
    toast.success("Contrat signé avec succès ! Le cachet de certification eIDAS a été apposé.");
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
        <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
          
          {/* Header Bar */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border)] bg-[var(--surface-hover)]/70">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[var(--color-teal)]/15 text-[var(--color-teal)] border border-[var(--color-teal)]/30 flex items-center justify-center shadow-xs">
                <FileCheck2 className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm sm:text-base font-bold text-[var(--ink)] tracking-tight">
                    Contrat de Fourniture d'Énergie — {currentContract.product}
                  </h2>
                  {isSigned ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                      <CheckCircle2 className="w-3 h-3" />
                      Signé eIDAS
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                      <Clock className="w-3 h-3" />
                      En attente de signature
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[var(--ink-muted)] font-mono">
                  RÉF: ECOFIX-{currentContract.product.toUpperCase()}-{currentContract.id.slice(0, 8)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Tabs: Visual Document vs Embedded PDF */}
              <div className="hidden sm:flex items-center p-1 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setActiveTab("document")}
                  className={`px-3 py-1 rounded-md transition-smooth ${
                    activeTab === "document"
                      ? "bg-[var(--color-teal)] text-white shadow-xs"
                      : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                  }`}
                >
                  Vue Contrat Interactif
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("pdf")}
                  className={`px-3 py-1 rounded-md transition-smooth ${
                    activeTab === "pdf"
                      ? "bg-[var(--color-teal)] text-white shadow-xs"
                      : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                  }`}
                >
                  Aperçu PDF ReportLab
                </button>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                title="Fermer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Main Visual Content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 bg-neutral-100 dark:bg-neutral-950/70">
            {activeTab === "document" ? (
              /* A4 Visual Sheet Document */
              <div className="max-w-2xl mx-auto bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl shadow-lg p-6 sm:p-10 space-y-6 relative overflow-hidden text-neutral-900 dark:text-neutral-100 text-xs">
                
                {/* 45deg Watermark */}
                <div
                  className="absolute inset-0 pointer-events-none flex items-center justify-center select-none"
                  aria-hidden="true"
                >
                  <span className="text-4xl sm:text-5xl font-black text-neutral-200/40 dark:text-neutral-800/40 -rotate-45 tracking-widest uppercase">
                    SPÉCIMEN • DONNÉES FICTIVES
                  </span>
                </div>

                {/* Document Header */}
                <div className="border-b-2 border-teal-600 pb-4 relative z-10">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-400 font-bold text-base tracking-tight">
                        <Zap className="w-4 h-4 fill-current" />
                        <span>ECOFIX GAS & POWER BELGIQUE</span>
                      </div>
                      <p className="text-[10px] text-neutral-500 dark:text-neutral-400 font-mono mt-0.5">
                        Fournisseur d'énergie verte • Licences CWaPE & VREG
                      </p>
                    </div>

                    <div className="text-right font-mono text-[10px] text-neutral-500">
                      <div>Date : {new Date(currentContract.created_at || Date.now()).toLocaleDateString("fr-BE")}</div>
                      <div>Zone : Wallonie / Flandre</div>
                    </div>
                  </div>
                </div>

                {/* AI Act Legal Preamble */}
                <div className="p-3.5 rounded-lg bg-teal-50 dark:bg-teal-950/30 border border-teal-200 dark:border-teal-800/50 text-[11px] text-teal-900 dark:text-teal-200 leading-relaxed relative z-10">
                  <div className="flex items-center gap-1.5 font-bold mb-1 text-teal-800 dark:text-teal-300">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Préambule de Transparence — Règlement Européen sur l'IA (Art. 50)</span>
                  </div>
                  <p className="italic">
                    "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment. Conformément au Règlement européen sur l'Intelligence Artificielle (AI Act, Règlement UE 2024/1689, Art. 50), le présent contrat a été préparé de manière automatisée par un système d'IA sous supervision humaine."
                  </p>
                </div>

                {/* Section 1: Parties au Contrat */}
                <div className="space-y-2 relative z-10">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-teal-700 dark:text-teal-400 border-b border-neutral-200 dark:border-neutral-800 pb-1">
                    1. Informations du Souscripteur (Données CRM)
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-[11px] p-3 rounded-lg bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
                    <div>
                      <span className="text-neutral-500 block">Nom & Prénom :</span>
                      <strong className="font-semibold text-neutral-900 dark:text-neutral-100">
                        {currentContract.lead_name || "Prospect Client"}
                      </strong>
                    </div>
                    <div>
                      <span className="text-neutral-500 block">Coordonnées :</span>
                      <strong className="font-semibold text-neutral-900 dark:text-neutral-100">
                        {currentContract.lead_phone || currentContract.lead_email || "Non renseigné"}
                      </strong>
                    </div>
                    <div>
                      <span className="text-neutral-500 block">Région & Zone de distribution :</span>
                      <strong className="font-semibold text-neutral-900 dark:text-neutral-100">
                        {currentContract.lead_region || "Wallonie (ORES)"}
                      </strong>
                    </div>
                    <div>
                      <span className="text-neutral-500 block">Code EAN Obligatoire :</span>
                      <strong className="font-mono font-bold text-teal-600 dark:text-teal-400">
                        5414 0000 1234 5678 90
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Section 2: Formule Tarifaire */}
                <div className="space-y-2 relative z-10">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-teal-700 dark:text-teal-400 border-b border-neutral-200 dark:border-neutral-800 pb-1">
                    2. Formule Tarifaire & Vérité des Prix
                  </h3>
                  <div className="border border-neutral-200 dark:border-neutral-800 rounded-lg overflow-hidden text-[11px]">
                    <table className="w-full text-left">
                      <thead className="bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 font-bold text-[10px]">
                        <tr>
                          <th className="p-2.5">Poste Tarifaire</th>
                          <th className="p-2.5">Détail</th>
                          <th className="p-2.5 text-right">Tarif TTC</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
                        <tr>
                          <td className="p-2.5 font-semibold">Produit d'Énergie</td>
                          <td className="p-2.5 text-neutral-500">
                            Offre {currentContract.product} ({currentContract.product === "Motion" ? "Tarif dynamique horaire" : "Tarif variable mensuel"})
                          </td>
                          <td className="p-2.5 text-right font-mono font-bold text-teal-600">Inclus</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-semibold">Redevance Fixe Obligatoire</td>
                          <td className="p-2.5 text-neutral-500">
                            Frais fixes de gestion annuelle (inclus au prix de l'énergie)
                          </td>
                          <td className="p-2.5 text-right font-mono font-semibold">60,00 € / an</td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-semibold">Option Digitale Ecofix Digi</td>
                          <td className="p-2.5 text-neutral-500">
                            {currentContract.digi_subscribed
                              ? "Suivi temps réel & Smart Control activé"
                              : "Non souscrite (Optionnel)"}
                          </td>
                          <td className="p-2.5 text-right font-mono text-neutral-500">
                            {currentContract.digi_subscribed ? "5,99 € / mois" : "0,00 €"}
                          </td>
                        </tr>
                        <tr>
                          <td className="p-2.5 font-semibold">Indemnité de résiliation</td>
                          <td className="p-2.5 text-neutral-500">
                            Résiliation libre à tout moment avec préavis standard (Droit belge)
                          </td>
                          <td className="p-2.5 text-right font-mono text-emerald-600 font-bold">0,00 €</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Section 3: Rétractation 14 Jours */}
                <div className="space-y-1 relative z-10 text-[10px] text-neutral-500 leading-relaxed border-t border-neutral-200 dark:border-neutral-800 pt-3">
                  <p>
                    <strong>Droit de Rétractation légal (Code de droit économique belge, Art. VI.47) :</strong> Le consommateur dispose d'un délai légal de 14 jours calendrier pour se rétracter sans motif ni pénalité. Le basculement de fourniture s'effectue sous 3 à 4 semaines par l'intermédiaire du gestionnaire de réseau (Fluvius/ORES).
                  </p>
                </div>

                {/* Section 4: Signature Block */}
                <div className="border-t-2 border-neutral-300 dark:border-neutral-700 pt-4 relative z-10">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Ecofix Supplier Side */}
                    <div className="p-3.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/50 space-y-1.5">
                      <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">
                        Pour le Fournisseur (Ecofix Gas & Power)
                      </span>
                      <div className="pt-2 font-serif italic text-teal-800 dark:text-teal-300 text-sm">
                        Direction Commerciale Ecofix
                      </div>
                      <div className="text-[9px] font-mono text-neutral-500">
                        Cachet électronique d'entreprise • Licences CWaPE & VREG
                      </div>
                    </div>

                    {/* Client Signer Side */}
                    <div className="p-3.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/50 flex flex-col justify-between">
                      <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">
                        Pour le Client Souscripteur
                      </span>

                      {isSigned ? (
                        /* Certified eIDAS Stamp on the signed document */
                        <div className="p-3 my-2 rounded-lg bg-emerald-500/10 border-2 border-emerald-500/40 text-emerald-900 dark:text-emerald-200 space-y-1.5 shadow-2xs">
                          <div className="flex items-center gap-1.5 font-bold text-emerald-700 dark:text-emerald-300 text-xs">
                            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                            <span>SIGNÉ ÉLECTRONIQUEMENT (eIDAS Sandbox)</span>
                          </div>
                          {signatureImage ? (
                            <div className="bg-white/80 dark:bg-black/30 rounded p-1.5 inline-block my-1 border border-emerald-500/25">
                              <img
                                src={signatureImage}
                                alt="Signature apposée"
                                className="h-9 object-contain"
                              />
                            </div>
                          ) : (
                            <div className="font-serif italic text-sm text-emerald-950 dark:text-emerald-100 font-semibold pl-1">
                              {currentContract.lead_name || "Souscripteur Certifié"}
                            </div>
                          )}
                          <div className="text-[9px] font-mono text-emerald-800 dark:text-emerald-400 pt-0.5 space-y-0.5 border-t border-emerald-500/20">
                            <div>Horodatage : {new Date(currentContract.signed_at || Date.now()).toISOString()}</div>
                            <div>Hash SHA-256 : {currentContract.id.replace(/-/g, "").slice(0, 24)}...</div>
                            <div>Conforme Règlement UE 910/2014 & Code de droit économique</div>
                          </div>
                        </div>
                      ) : (
                        /* Unsigned state prompt */
                        <div className="my-3 py-4 border-2 border-dashed border-amber-300 dark:border-amber-800/60 rounded-lg text-center space-y-2 bg-amber-500/5">
                          <PenTool className="w-5 h-5 text-amber-500 mx-auto" />
                          <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 block">
                            Signature électronique en attente
                          </span>
                          <button
                            type="button"
                            onClick={() => setIsSignStudioOpen(true)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition-smooth cursor-pointer active:scale-95"
                          >
                            <PenTool className="w-3.5 h-3.5" />
                            <span>Signer ce contrat maintenant</span>
                          </button>
                        </div>
                      )}

                      <div className="text-[9px] text-neutral-400">
                        {isSigned ? "Certificat validé par Yousign" : "Signature obligatoire pour finaliser la souscription"}
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              /* Embedded PDF viewer mode */
              <div className="w-full h-[650px] rounded-xl overflow-hidden border border-[var(--border)] bg-neutral-900 shadow-inner">
                <iframe
                  src={`/api/contracts/${currentContract.id}/pdf#toolbar=0`}
                  className="w-full h-full border-none"
                  title="Aperçu du contrat PDF"
                />
              </div>
            )}
          </div>

          {/* Modal Footer Controls */}
          <div className="px-5 py-3.5 border-t border-[var(--border)] bg-[var(--surface-hover)]/70 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)]">
              <ShieldCheck className="w-4 h-4 text-[var(--color-teal)]" />
              <span>Garantie légale Ecofix • Document prêt pour audit réglementaire</span>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
              {!isSigned && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setIsSignStudioOpen(true)}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs"
                >
                  <PenTool className="w-3.5 h-3.5 mr-1.5" />
                  <span>Simuler Signature Client (eIDAS)</span>
                </Button>
              )}

              <Button
                variant="secondary"
                size="sm"
                onClick={handleDownloadPdf}
                disabled={isDownloading}
                className="text-xs font-semibold"
              >
                {isDownloading ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5 mr-1.5 text-[var(--color-teal)]" />
                )}
                <span>Télécharger le PDF Certifié</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Realistic E-Signature Studio Modal */}
      {isSignStudioOpen && (
        <SignatureStudioModal
          contract={currentContract}
          isOpen={isSignStudioOpen}
          onClose={() => setIsSignStudioOpen(false)}
          onSuccess={handleSignatureSuccess}
        />
      )}
    </>
  );
};

/* ── REALISTIC E-SIGNATURE STUDIO (PAD CANVAS) ────────────────────────────── */

interface SignatureStudioModalProps {
  contract: ContractSummary;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedContract: ContractSummary, signatureImage?: string) => void;
}

const SignatureStudioModal: React.FC<SignatureStudioModalProps> = ({
  contract,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signatureMode, setSignatureMode] = useState<"draw" | "type">("draw");
  const [typedName, setTypedName] = useState(contract.lead_name || "Marc Dupont");

  // Init canvas
  useEffect(() => {
    if (!isOpen || signatureMode !== "draw") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.strokeStyle = "#0d9488"; // Ecofix teal ink
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, [isOpen, signatureMode]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = "touches" in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = "touches" in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.beginPath();
    ctx.moveTo(x, y);
    setIsDrawing(true);
    setHasDrawn(true);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = "touches" in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = "touches" in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawn(false);
  };

  const handleConfirmSignature = async () => {
    if (!consentAccepted) {
      toast.error("Veuillez accepter les conditions légales pour confirmer la signature.");
      return;
    }
    if (signatureMode === "draw" && !hasDrawn) {
      toast.error("Veuillez apposer votre signature sur la zone dédiée.");
      return;
    }

    try {
      setIsSubmitting(true);
      let capturedSigUrl: string | undefined = undefined;
      if (signatureMode === "draw" && canvasRef.current) {
        capturedSigUrl = canvasRef.current.toDataURL("image/png");
      }
      const updated = await apiClient.simulateSignContract(contract.id);
      onSuccess(updated, capturedSigUrl);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur lors de la signature";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold">
              <PenTool className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--ink)]">
                Portail de Signature Électronique Certifiée
              </h3>
              <p className="text-[11px] text-[var(--ink-muted)]">
                Certifié conforme eIDAS • Yousign Sandbox v3
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Identity Verification Box */}
        <div className="p-3 rounded-xl bg-[var(--surface-hover)] border border-[var(--border)] space-y-1.5 text-xs">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[var(--ink-muted)]">Signataire :</span>
            <strong className="font-semibold text-[var(--ink)]">{contract.lead_name || "Souscripteur"}</strong>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[var(--ink-muted)]">Document :</span>
            <span className="font-mono text-[var(--color-teal)] font-bold">Contrat Ecofix {contract.product}</span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[var(--ink-muted)]">Horodatage de session :</span>
            <span className="font-mono text-neutral-500">{new Date().toLocaleTimeString("fr-BE")} UTC</span>
          </div>
        </div>

        {/* Signature Pad / Type Switcher */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <label className="font-semibold text-[var(--ink)]">Apposition de votre signature :</label>
            <div className="flex items-center gap-1 text-[11px]">
              <button
                type="button"
                onClick={() => setSignatureMode("draw")}
                className={`px-2 py-0.5 rounded-md font-semibold transition-smooth ${
                  signatureMode === "draw"
                    ? "bg-[var(--color-teal)] text-white"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                Tracer
              </button>
              <button
                type="button"
                onClick={() => setSignatureMode("type")}
                className={`px-2 py-0.5 rounded-md font-semibold transition-smooth ${
                  signatureMode === "type"
                    ? "bg-[var(--color-teal)] text-white"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                Calligraphie
              </button>
            </div>
          </div>

          {signatureMode === "draw" ? (
            <div className="relative border-2 border-dashed border-[var(--border)] hover:border-[var(--color-teal)]/60 rounded-xl bg-white dark:bg-neutral-900 overflow-hidden transition-smooth">
              <canvas
                ref={canvasRef}
                width={460}
                height={160}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
                className="w-full h-40 cursor-crosshair touch-none"
              />
              {!hasDrawn && (
                <div className="absolute inset-0 pointer-events-none flex items-center justify-center text-xs text-neutral-400 italic">
                  Signez ici avec la souris ou le doigt...
                </div>
              )}
              {hasDrawn && (
                <button
                  type="button"
                  onClick={clearCanvas}
                  className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-neutral-200/80 dark:bg-neutral-800/80 text-neutral-700 dark:text-neutral-300 hover:bg-rose-500/20 hover:text-rose-500 text-[11px] font-semibold flex items-center gap-1 transition-smooth cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Effacer</span>
                </button>
              )}
            </div>
          ) : (
            <div className="p-4 border border-[var(--border)] rounded-xl bg-[var(--surface-hover)] space-y-3">
              <input
                type="text"
                value={typedName}
                onChange={(e) => setTypedName(e.target.value)}
                placeholder="Votre nom complet"
                className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)]"
              />
              <div className="p-3 border border-neutral-200 dark:border-neutral-800 rounded-lg bg-white dark:bg-neutral-900 text-center">
                <span className="font-serif italic text-2xl text-teal-700 dark:text-teal-400">
                  {typedName || "Votre signature"}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Legal Consent Checkbox */}
        <label className="flex items-start gap-2.5 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 text-xs cursor-pointer select-none">
          <input
            type="checkbox"
            checked={consentAccepted}
            onChange={(e) => setConsentAccepted(e.target.checked)}
            className="mt-0.5 accent-[var(--color-teal)] rounded cursor-pointer"
          />
          <span className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
            Je confirme avoir pris connaissance des Conditions Générales de Fourniture d'Énergie Ecofix, et consens expressément à l'apposition de ma signature électronique qualifiée avec valeur juridique probante.
          </span>
        </label>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={isSubmitting}>
            Annuler
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleConfirmSignature}
            disabled={isSubmitting || !consentAccepted}
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-xs"
          >
            {isSubmitting ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
            )}
            <span>Confirmer la Signature Électronique</span>
          </Button>
        </div>
      </div>
    </div>
  );
};
