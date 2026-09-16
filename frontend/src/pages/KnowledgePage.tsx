import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { KnowledgeDocument, KnowledgeEntry, TestQueryChunk } from "@/api/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import {
  BookOpen,
  Plus,
  Pencil,
  Trash2,
  Search,
  Info,
  X,
  Loader2,
  Save,
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  Layers,
  Coins,
  Send,
  ShieldCheck,
  RotateCcw,
  Archive,
} from "lucide-react";
import { toast } from "sonner";

interface EntryFormState {
  category: string;
  question: string;
  keywords: string;
  answer_fr: string;
  answer_nl: string;
  answer_en: string;
}

const EMPTY_FORM: EntryFormState = {
  category: "faq",
  question: "",
  keywords: "",
  answer_fr: "",
  answer_nl: "",
  answer_en: "",
};

const toFormState = (entry: KnowledgeEntry): EntryFormState => ({
  category: entry.category,
  question: entry.question,
  keywords: entry.keywords.join(", "),
  answer_fr: entry.answer_fr,
  answer_nl: entry.answer_nl || "",
  answer_en: entry.answer_en || "",
});

const inputClass =
  "w-full px-3 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth";

export const KnowledgePage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  // RAG v1 states
  const [searchTerm, setSearchTerm] = useState("");
  const [editingEntry, setEditingEntry] = useState<KnowledgeEntry | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState<EntryFormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeEntry | null>(null);

  // RAG v2 states
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState("");
  const [docSourceType, setDocSourceType] = useState("tariff_card");
  const [docLanguage, setDocLanguage] = useState("fr");
  const [docReviewDate, setDocReviewDate] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);

  // Document action confirmation modals
  const [actionTargetDoc, setActionTargetDoc] = useState<KnowledgeDocument | null>(null);
  const [actionType, setActionType] = useState<"publish" | "archive" | null>(null);

  // QA Test tool state
  const [testQueryText, setTestQueryText] = useState("");
  const [testLang, setTestLang] = useState("fr");
  const [testResults, setTestResults] = useState<{
    chunks: TestQueryChunk[];
    would_refuse: boolean;
  } | null>(null);

  // Queries
  const { data: v1Data, isLoading: isV1Loading } = useQuery({
    queryKey: ["knowledgeEntries"],
    queryFn: () => apiClient.getKnowledgeEntries(),
  });

  const { data: docsData, isLoading: isDocsLoading } = useQuery({
    queryKey: ["knowledgeDocuments"],
    queryFn: () => apiClient.getKnowledgeDocuments(),
  });

  const { data: statsData } = useQuery({
    queryKey: ["knowledgeStats"],
    queryFn: () => apiClient.getKnowledgeStats(),
  });

  const { data: obsolescenceData } = useQuery({
    queryKey: ["knowledgeObsolescence"],
    queryFn: () => apiClient.getKnowledgeObsolescence(),
  });

  const entries = v1Data?.items || [];
  const documents = docsData || [];

  const filteredEntries = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.question.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q) ||
        e.keywords.some((k) => k.toLowerCase().includes(q))
    );
  }, [entries, searchTerm]);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["knowledgeEntries"] });
    queryClient.invalidateQueries({ queryKey: ["knowledgeDocuments"] });
    queryClient.invalidateQueries({ queryKey: ["knowledgeStats"] });
    queryClient.invalidateQueries({ queryKey: ["knowledgeObsolescence"] });
  };

  // RAG v2 Document Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error("Veuillez sélectionner un fichier PDF");
      if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
        throw new Error("Seuls les fichiers PDF sont acceptés.");
      }
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (docTitle.trim()) formData.append("title", docTitle.trim());
      formData.append("source_type", docSourceType);
      formData.append("language", docLanguage);
      if (docReviewDate) formData.append("review_date", docReviewDate);

      return apiClient.uploadKnowledgeDocument(formData);
    },
    onSuccess: (res) => {
      setUploadError(null);
      setSelectedFile(null);
      setDocTitle("");
      setDocReviewDate("");
      const successText = t("knowledgePage.uploadSuccess", { count: res.chunks_created }) ||
        `Document ingéré (${res.chunks_created} segments créés). Statut = BROUILLON — publier après vérification.`;
      setUploadSuccessMsg(successText);
      toast.success(successText);
      invalidateAll();
    },
    onError: (err: any) => {
      const msg = err?.message || "Erreur lors de l'ingestion du document.";
      setUploadError(msg);
      toast.error(msg);
    },
  });

  // Document publish / archive mutation
  const docActionMutation = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "publish" | "archive" }) => {
      if (action === "publish") {
        return apiClient.publishKnowledgeDocument(id);
      } else {
        return apiClient.archiveKnowledgeDocument(id);
      }
    },
    onSuccess: (_, vars) => {
      toast.success(
        vars.action === "publish"
          ? "Document publié avec succès"
          : "Document archivé avec succès"
      );
      setActionTargetDoc(null);
      setActionType(null);
      invalidateAll();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur d'action sur le document"),
  });

  // QA Test Mutation
  const testMutation = useMutation({
    mutationFn: () => apiClient.testKnowledgeQuery(testQueryText, testLang),
    onSuccess: (res) => {
      setTestResults(res);
    },
    onError: (err: any) => toast.error(err?.message || "Erreur de test RAG"),
  });

  // RAG v1 Mutations
  const toggleMutation = useMutation({
    mutationFn: (id: string) => apiClient.toggleKnowledgeEntryActive(id),
    onSuccess: invalidateAll,
    onError: (err: any) => toast.error(err?.message || "Erreur"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteKnowledgeEntry(id),
    onSuccess: () => {
      toast.success(t("knowledgePage.deleteSuccess") || "Entrée supprimée");
      invalidateAll();
      setDeleteTarget(null);
    },
    onError: (err: any) => toast.error(err?.message || "Erreur"),
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const keywords = form.keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      if (!form.question.trim() || !form.answer_fr.trim() || keywords.length === 0) {
        throw new Error(t("knowledgePage.validationError") || "Champs requis manquants");
      }
      const payload = {
        category: form.category,
        question: form.question.trim(),
        keywords,
        answer_fr: form.answer_fr.trim(),
        answer_nl: form.answer_nl.trim() || undefined,
        answer_en: form.answer_en.trim() || undefined,
      };
      if (editingEntry) {
        return apiClient.updateKnowledgeEntry(editingEntry.id, payload);
      }
      return apiClient.createKnowledgeEntry(payload);
    },
    onSuccess: () => {
      toast.success(
        editingEntry
          ? t("knowledgePage.updateSuccess") || "Entrée mise à jour"
          : t("knowledgePage.createSuccess") || "Entrée créée"
      );
      invalidateAll();
      closeModal();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur d'enregistrement"),
  });

  const openCreateModal = () => {
    setEditingEntry(null);
    setForm(EMPTY_FORM);
    setIsModalOpen(true);
  };

  const openEditModal = (entry: KnowledgeEntry) => {
    setEditingEntry(entry);
    setForm(toFormState(entry));
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingEntry(null);
    setForm(EMPTY_FORM);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveMutation.mutate();
  };

  // Review date helper: returns "overdue", "due_soon", or "ok"
  const getReviewStatus = (reviewDateStr: string | null) => {
    if (!reviewDateStr) return "none";
    const target = new Date(reviewDateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return "overdue";
    if (diffDays <= 7) return "due_soon";
    return "ok";
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[var(--color-teal)]" />
            <h1 className="text-xl font-bold tracking-tight text-[var(--ink)]">
              {t("knowledgePage.title") || "Base de Connaissances"}
            </h1>
          </div>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("knowledgePage.subtitle") ||
              "Faits, tarifs et réponses certifiées que Sophie est autorisée à exploiter."}
          </p>
        </div>
      </div>

      {/* Honest Banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-[var(--surface)] border border-[var(--color-teal)]/30 shadow-xs">
        <Info className="w-4 h-4 text-[var(--color-teal)] shrink-0 mt-0.5" />
        <p className="text-xs text-[var(--ink)] leading-relaxed">
          <span className="font-semibold text-[var(--color-teal)]">Architecture RAG v2 : </span>
          {t("knowledgePage.honestBanner") ||
            "Embeddings via API (Google text-embedding-004) — coût estimé visible dans Stats. Upload ≠ publié : la publication est une action explicite."}
        </p>
      </div>

      {/* Stats Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Card 1: Documents */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
            <span>{t("knowledgePage.statsDocs") || "Documents"}</span>
            <FileText className="w-3.5 h-3.5 text-[var(--color-teal)]" />
          </div>
          <div className="text-xl font-bold text-[var(--ink)]">
            {documents.length}
          </div>
          <div className="flex items-center gap-2 text-[11px] text-[var(--ink-muted)] pt-1">
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 font-medium">
              {statsData?.documents_by_status?.published || 0} {t("knowledgePage.statusPublished") || "publiés"}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 font-medium">
              {statsData?.documents_by_status?.draft || 0} {t("knowledgePage.statusDraft") || "brouillons"}
            </span>
          </div>
        </div>

        {/* Card 2: Chunks */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
            <span>{t("knowledgePage.statsChunks") || "Total segments"}</span>
            <Layers className="w-3.5 h-3.5 text-[var(--color-navy)]" />
          </div>
          <div className="text-xl font-bold text-[var(--ink)]">
            {statsData?.total_chunks || 0}
          </div>
          <div className="text-[11px] text-[var(--ink-muted)] pt-1">
            FR: {statsData?.chunks_by_language?.fr || 0} · NL: {statsData?.chunks_by_language?.nl || 0} · EN: {statsData?.chunks_by_language?.en || 0}
          </div>
        </div>

        {/* Card 3: Estimated Cost */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
            <span>{t("knowledgePage.statsCost") || "Coût estimé embeddings"}</span>
            <Coins className="w-3.5 h-3.5 text-[var(--color-lavender)]" />
          </div>
          <div className="text-xl font-bold text-[var(--ink)]">
            {statsData?.estimated_embedding_cost_eur?.toFixed(4) || "0.0000"} €
          </div>
          <div className="text-[11px] text-[var(--ink-muted)] pt-1">
            ~500 tokens/segment · 0,00002 €/1k
          </div>
        </div>

        {/* Card 4: Obsolescence */}
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-1">
          <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
            <span>{t("knowledgePage.obsolescenceTitle") || "Obsolescence (W3)"}</span>
            <Clock className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="text-xl font-bold text-[var(--ink)]">
            {(obsolescenceData?.due_soon?.length || 0) + (obsolescenceData?.overdue?.length || 0)}
          </div>
          <div className="flex items-center gap-2 text-[11px] pt-1">
            {obsolescenceData?.overdue && obsolescenceData.overdue.length > 0 ? (
              <span className="text-danger font-semibold">
                {obsolescenceData.overdue.length} {t("knowledgePage.reviewOverdue") || "en retard"}
              </span>
            ) : obsolescenceData?.due_soon && obsolescenceData.due_soon.length > 0 ? (
              <span className="text-amber-500 font-semibold">
                {obsolescenceData.due_soon.length} {t("knowledgePage.reviewDueSoon") || "sous 7j"}
              </span>
            ) : (
              <span className="text-emerald-500 font-medium">
                {t("knowledgePage.obsolescenceOk") || "Tous à jour"}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Obsolescence Warning Banner if items exist */}
      {((obsolescenceData?.overdue && obsolescenceData.overdue.length > 0) ||
        (obsolescenceData?.due_soon && obsolescenceData.due_soon.length > 0)) && (
        <div className="p-4 rounded-xl border border-amber-500/40 bg-amber-500/5 space-y-3">
          <div className="flex items-center gap-2 text-amber-500 font-semibold text-xs">
            <AlertTriangle className="w-4 h-4" />
            <span>{t("knowledgePage.obsolescenceTitle") || "Documents nécessitant une revue"}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {obsolescenceData?.overdue?.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-2.5 rounded-lg border border-danger/30 bg-danger/5 text-xs"
              >
                <div>
                  <div className="font-semibold text-danger flex items-center gap-1.5">
                    <AlertOctagon className="w-3.5 h-3.5" />
                    <span>{doc.title}</span>
                  </div>
                  <div className="text-[11px] text-[var(--ink-muted)]">
                    Revue échue le : {doc.review_date}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setActionTargetDoc({ id: doc.id, title: doc.title } as KnowledgeDocument);
                    setActionType("archive");
                  }}
                  className="px-2.5 py-1 rounded bg-danger text-white text-[11px] font-semibold hover:opacity-90 transition-smooth cursor-pointer"
                >
                  {t("knowledgePage.actionArchive") || "Archiver"}
                </button>
              </div>
            ))}
            {obsolescenceData?.due_soon?.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/5 text-xs"
              >
                <div>
                  <div className="font-semibold text-amber-500 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{doc.title}</span>
                  </div>
                  <div className="text-[11px] text-[var(--ink-muted)]">
                    À réviser avant le : {doc.review_date}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setActionTargetDoc({ id: doc.id, title: doc.title } as KnowledgeDocument);
                    setActionType("archive");
                  }}
                  className="px-2.5 py-1 rounded bg-amber-500 text-white text-[11px] font-semibold hover:opacity-90 transition-smooth cursor-pointer"
                >
                  {t("knowledgePage.actionArchive") || "Archiver"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ingestion & QA Testing Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Zone */}
        <div className="p-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] space-y-4">
          <div className="flex items-center gap-2">
            <UploadCloud className="w-4 h-4 text-[var(--color-teal)]" />
            <h2 className="text-sm font-bold text-[var(--ink)]">
              {t("knowledgePage.uploadTitle") || "Importer un document PDF (RAG v2)"}
            </h2>
          </div>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const f = e.dataTransfer.files?.[0];
              if (f) {
                if (!f.name.toLowerCase().endsWith(".pdf")) {
                  toast.error("Seuls les fichiers PDF sont acceptés.");
                  return;
                }
                setSelectedFile(f);
                if (!docTitle) setDocTitle(f.name.replace(/\.[^/.]+$/, ""));
              }
            }}
            className="border-2 border-dashed border-[var(--border)] hover:border-[var(--color-teal)] rounded-xl p-5 text-center transition-smooth cursor-pointer bg-[var(--surface-hover)]/30"
            onClick={() => document.getElementById("pdf-upload-input")?.click()}
          >
            <input
              id="pdf-upload-input"
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  setSelectedFile(f);
                  if (!docTitle) setDocTitle(f.name.replace(/\.[^/.]+$/, ""));
                }
              }}
            />
            <UploadCloud className="w-6 h-6 text-[var(--ink-muted)] mx-auto mb-2" />
            {selectedFile ? (
              <div className="text-xs font-semibold text-[var(--color-teal)]">
                Fichier sélectionné : {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </div>
            ) : (
              <p className="text-xs text-[var(--ink-muted)]">
                {t("knowledgePage.uploadDrop") || "Glissez-déposez un PDF ici ou cliquez pour parcourir"}
              </p>
            )}
          </div>

          {/* Form fields */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                {t("knowledgePage.tableDocTitle") || "Titre du document"}
              </label>
              <input
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="Ex: Flexy Électricité Septembre 2026"
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                {t("knowledgePage.tableType") || "Type de source"}
              </label>
              <select
                value={docSourceType}
                onChange={(e) => setDocSourceType(e.target.value)}
                className={inputClass}
              >
                <option value="tariff_card">Grille Tarifaire (Priorité 1)</option>
                <option value="terms">Conditions Générales (Priorité 2)</option>
                <option value="faq">FAQ / Helpdesk (Priorité 3)</option>
                <option value="regulatory">Régulateur (CWaPE/VREG)</option>
                <option value="marketing">Marketing</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                {t("knowledgePage.tableLang") || "Langue"}
              </label>
              <select
                value={docLanguage}
                onChange={(e) => setDocLanguage(e.target.value)}
                className={inputClass}
              >
                <option value="fr">Français (FR)</option>
                <option value="nl">Nederlands (NL)</option>
                <option value="en">English (EN)</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                {t("knowledgePage.tableReviewDate") || "Date de revue (obsolescence)"}
              </label>
              <input
                type="date"
                value={docReviewDate}
                onChange={(e) => setDocReviewDate(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          {uploadError && (
            <div className="p-3 rounded-lg bg-danger/10 border border-danger/20 text-danger text-xs flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccessMsg && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{uploadSuccessMsg}</span>
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!selectedFile || uploadMutation.isPending}
              onClick={() => uploadMutation.mutate()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
            >
              {uploadMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <UploadCloud className="w-3.5 h-3.5" />
              )}
              <span>
                {uploadMutation.isPending
                  ? t("knowledgePage.uploading") || "Traitement et vectorisation..."
                  : t("knowledgePage.uploadButton") || "Importer le PDF"}
              </span>
            </button>
          </div>
        </div>

        {/* QA Testing Box */}
        <div className="p-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--color-lavender)]" />
            <h2 className="text-sm font-bold text-[var(--ink)]">
              {t("knowledgePage.testTitle") || "Tester le RAG (Transparence QA)"}
            </h2>
          </div>
          <p className="text-xs text-[var(--ink-muted)]">
            {t("knowledgePage.testSubtitle") ||
              "Vérifiez exactement ce que Sophie extrait pour une question sans appel LLM."}
          </p>

          <div className="flex items-center gap-2">
            <input
              value={testQueryText}
              onChange={(e) => setTestQueryText(e.target.value)}
              placeholder={t("knowledgePage.testPlaceholder") || "Posez une question technique ou tarifaire..."}
              className={inputClass}
              onKeyDown={(e) => {
                if (e.key === "Enter" && testQueryText.trim() && !testMutation.isPending) {
                  testMutation.mutate();
                }
              }}
            />
            <select
              value={testLang}
              onChange={(e) => setTestLang(e.target.value)}
              className="px-2.5 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth"
            >
              <option value="fr">FR</option>
              <option value="nl">NL</option>
              <option value="en">EN</option>
            </select>
            <button
              type="button"
              disabled={!testQueryText.trim() || testMutation.isPending}
              onClick={() => testMutation.mutate()}
              className="inline-flex items-center gap-1 px-3 py-2 rounded-[0.5rem] bg-[var(--color-navy)] text-white hover:opacity-90 text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50 shrink-0"
            >
              {testMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
              <span>{t("knowledgePage.testButton") || "Tester"}</span>
            </button>
          </div>

          {/* QA Test Result panel */}
          {testResults && (
            <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface-hover)]/40 space-y-3 max-h-[300px] overflow-y-auto">
              {testResults.would_refuse ? (
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-500 text-xs flex items-center gap-2 font-medium">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{t("knowledgePage.testWouldRefuse") || "Refus Sophie (aucun segment n'atteint le seuil de pertinence)"}</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[var(--color-teal)] flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{testResults.chunks.length} segments documentaires extraits :</span>
                  </div>
                  {testResults.chunks.map((m, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-[var(--ink)]">
                          [SOURCE {idx + 1}] {m.document_title} (v{m.version})
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-[var(--color-teal)]/10 text-[var(--color-teal)] font-bold">
                          score : {m.score.toFixed(4)}
                        </span>
                      </div>
                      <p className="text-[var(--ink-muted)] text-[11px] leading-relaxed line-clamp-3">
                        {m.content_preview}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* RAG v2 Documents Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[var(--ink)]">
              {t("knowledgePage.documentsTitle") || "Documents Sources RAG v2"}
            </h2>
            <p className="text-xs text-[var(--ink-muted)]">
              {t("knowledgePage.documentsSubtitle") ||
                "Documents officiels ingérés, versionnés et indexés vectoriellement pour Sophie."}
            </p>
          </div>
        </div>

        <div className="border border-[var(--border)] rounded-xl bg-[var(--surface)] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[var(--ink)]">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-hover)] text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider">
                <tr>
                  <th className="p-3.5">{t("knowledgePage.tableDocTitle") || "Titre"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableType") || "Type"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableVersion") || "Version"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableLang") || "Langue"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableStatus") || "Statut"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableReviewDate") || "Revue"}</th>
                  <th className="p-3.5">{t("knowledgePage.tableChunks") || "Segments"}</th>
                  <th className="p-3.5 text-right">{t("knowledgePage.table.actions") || "Actions"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {isDocsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={8} className="p-3.5">
                        <Skeleton className="h-5 w-full" />
                      </td>
                    </tr>
                  ))
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-xs text-[var(--ink-muted)]">
                      Aucun document RAG v2 ingéré pour l'instant. Utilisez le formulaire d'upload ci-dessus.
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => {
                    const reviewStatus = getReviewStatus(doc.review_date);
                    return (
                      <tr key={doc.id} className="hover:bg-[var(--surface-hover)]/50 transition-smooth">
                        <td className="p-3.5 font-semibold text-[var(--ink)]">
                          {doc.title}
                        </td>
                        <td className="p-3.5">
                          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--border)]/60 text-[var(--ink)]">
                            {doc.source_type}
                          </span>
                        </td>
                        <td className="p-3.5 text-[var(--ink-muted)]">v{doc.version}</td>
                        <td className="p-3.5 uppercase text-[var(--ink-muted)] font-mono">{doc.language}</td>
                        <td className="p-3.5">
                          {doc.status === "published" ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-500">
                              {t("knowledgePage.statusPublished") || "Publié"}
                            </span>
                          ) : doc.status === "archived" ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-pink-500/10 text-pink-500">
                              {t("knowledgePage.statusArchived") || "Archivé"}
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-500/10 text-gray-400">
                              {t("knowledgePage.statusDraft") || "Brouillon"}
                            </span>
                          )}
                        </td>
                        <td className="p-3.5">
                          {doc.review_date ? (
                            <span
                              className={`text-[11px] font-medium ${
                                reviewStatus === "overdue"
                                  ? "text-danger font-bold"
                                  : reviewStatus === "due_soon"
                                  ? "text-amber-500 font-bold"
                                  : "text-[var(--ink-muted)]"
                              }`}
                            >
                              {doc.review_date}
                            </span>
                          ) : (
                            <span className="text-[var(--ink-subtle)]">—</span>
                          )}
                        </td>
                        <td className="p-3.5 text-[var(--ink-muted)] font-mono">{doc.chunk_count}</td>
                        <td className="p-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {doc.status === "draft" && (
                              <button
                                type="button"
                                onClick={() => {
                                  setActionTargetDoc(doc);
                                  setActionType("publish");
                                }}
                                className="px-2.5 py-1 rounded bg-[var(--color-teal)] text-white text-[11px] font-semibold hover:bg-[var(--color-teal-hover)] transition-smooth cursor-pointer"
                              >
                                {t("knowledgePage.actionPublish") || "Publier"}
                              </button>
                            )}
                            {doc.status === "published" && (
                              <button
                                type="button"
                                onClick={() => {
                                  setActionTargetDoc(doc);
                                  setActionType("archive");
                                }}
                                className="px-2.5 py-1 rounded bg-amber-500 text-white text-[11px] font-semibold hover:opacity-90 transition-smooth cursor-pointer"
                              >
                                {t("knowledgePage.actionArchive") || "Archiver"}
                              </button>
                            )}
                            {doc.status === "archived" && (
                              <button
                                type="button"
                                onClick={() => {
                                  setActionTargetDoc(doc);
                                  setActionType("publish");
                                }}
                                className="px-2.5 py-1 rounded bg-[var(--color-navy)] text-white text-[11px] font-semibold hover:opacity-90 transition-smooth cursor-pointer"
                              >
                                {t("knowledgePage.actionRepublish") || "Republier"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RAG v1 Section Divider & Header */}
      <div className="pt-6 border-t border-[var(--border)] space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-[var(--ink)]">
              {t("knowledgePage.v1SectionTitle") || "Base de Connaissances RAG v1 (repli mot-clé)"}
            </h2>
            <p className="text-xs text-[var(--ink-muted)]">
              Paires questions/réponses mot-clé consultées en secours en l'absence de chunk vectoriel.
            </p>
          </div>
          <button
            type="button"
            onClick={openCreateModal}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold shadow-xs transition-smooth cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{t("knowledgePage.addButton") || "Ajouter une entrée"}</span>
          </button>
        </div>

        {/* Filter input */}
        <div className="relative max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-muted)]" />
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={
              t("knowledgePage.searchPlaceholder") || "Filtrer par question, catégorie, mot-clé..."
            }
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth"
          />
        </div>

        {/* Entries table */}
        <div className="border border-[var(--border)] rounded-xl bg-[var(--surface)] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[var(--ink)]">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-hover)] text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider">
                <tr>
                  <th className="p-3.5">{t("knowledgePage.table.category") || "Catégorie"}</th>
                  <th className="p-3.5">{t("knowledgePage.table.question") || "Question"}</th>
                  <th className="p-3.5">Mots-clés</th>
                  <th className="p-3.5">{t("knowledgePage.table.languages") || "Langues"}</th>
                  <th className="p-3.5">{t("knowledgePage.table.active") || "Actif"}</th>
                  <th className="p-3.5 text-right">{t("knowledgePage.table.actions") || "Actions"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {isV1Loading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={6} className="p-3.5">
                        <Skeleton className="h-5 w-full" />
                      </td>
                    </tr>
                  ))
                ) : filteredEntries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-xs text-[var(--ink-muted)]">
                      {t("knowledgePage.empty") || "Aucune entrée trouvée."}
                    </td>
                  </tr>
                ) : (
                  filteredEntries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-[var(--surface-hover)]/50 transition-smooth">
                      <td className="p-3.5">
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--border)]/60 text-[var(--ink)]">
                          {entry.category}
                        </span>
                      </td>
                      <td className="p-3.5 font-medium text-[var(--ink)] max-w-xs truncate">
                        {entry.question}
                      </td>
                      <td className="p-3.5 text-[var(--ink-muted)] max-w-xs truncate">
                        {entry.keywords.join(", ")}
                      </td>
                      <td className="p-3.5">
                        <div className="flex items-center gap-1 text-[11px] font-mono text-[var(--ink-muted)]">
                          <span className="text-[var(--color-teal)] font-bold">FR</span>
                          {entry.answer_nl && <span>· NL</span>}
                          {entry.answer_en && <span>· EN</span>}
                        </div>
                      </td>
                      <td className="p-3.5">
                        <button
                          type="button"
                          onClick={() => toggleMutation.mutate(entry.id)}
                          disabled={toggleMutation.isPending}
                          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                            entry.active ? "bg-[var(--color-teal)]" : "bg-[var(--border)]"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                              entry.active ? "translate-x-4" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </td>
                      <td className="p-3.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => openEditModal(entry)}
                            className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(entry)}
                            className="p-1.5 rounded-[0.5rem] text-danger/80 hover:text-danger hover:bg-danger/10 transition-smooth cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Action confirmation modal for Publish / Archive */}
      {actionTargetDoc && actionType && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs z-[60]"
            onClick={() => !docActionMutation.isPending && setActionTargetDoc(null)}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
            <div className="w-full max-w-sm bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 font-bold text-sm text-[var(--ink)]">
                {actionType === "publish" ? (
                  <CheckCircle2 className="w-4 h-4 text-[var(--color-teal)]" />
                ) : (
                  <Archive className="w-4 h-4 text-amber-500" />
                )}
                <span>
                  {actionType === "publish"
                    ? t("knowledgePage.confirmPublishTitle") || "Publier ce document ?"
                    : t("knowledgePage.confirmArchiveTitle") || "Archiver ce document ?"}
                </span>
              </div>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                « {actionTargetDoc.title} » —{" "}
                {actionType === "publish"
                  ? t("knowledgePage.confirmPublishBody") ||
                    "Ses segments deviendront immédiatement interrogeables par Sophie en production."
                  : t("knowledgePage.confirmArchiveBody") ||
                    "Ses segments seront immédiatement retirés de la recherche documentaire de Sophie."}
              </p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setActionTargetDoc(null)}
                  disabled={docActionMutation.isPending}
                  className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                >
                  {t("common.close")}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    docActionMutation.mutate({
                      id: actionTargetDoc.id,
                      action: actionType,
                    })
                  }
                  disabled={docActionMutation.isPending}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] text-white text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50 ${
                    actionType === "publish"
                      ? "bg-[var(--color-teal)] hover:bg-[var(--color-teal-hover)]"
                      : "bg-amber-500 hover:opacity-90"
                  }`}
                >
                  {docActionMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{actionType === "publish" ? "Confirmer la publication" : "Confirmer l'archivage"}</span>
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* V1 Entry Modal */}
      {isModalOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50"
            onClick={closeModal}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-lg bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden"
            >
              <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--surface-hover)]">
                <h2 className="text-sm font-bold text-[var(--ink)]">
                  {editingEntry
                    ? t("knowledgePage.editTitle") || "Modifier l'entrée"
                    : t("knowledgePage.addButton") || "Ajouter une entrée"}
                </h2>
                <button
                  onClick={closeModal}
                  className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                  type="button"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <form onSubmit={handleSubmit} className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                      {t("knowledgePage.form.category") || "Catégorie"}
                    </label>
                    <select
                      value={form.category}
                      onChange={(e) => setForm({ ...form, category: e.target.value })}
                      className={inputClass}
                    >
                      <option value="faq">FAQ</option>
                      <option value="objection">Objection</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                      {t("knowledgePage.form.question") || "Question / intitulé"}
                    </label>
                    <input
                      value={form.question}
                      onChange={(e) => setForm({ ...form, question: e.target.value })}
                      className={inputClass}
                      autoFocus
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("knowledgePage.form.keywords") || "Mots-clés (séparés par des virgules)"}
                  </label>
                  <input
                    value={form.keywords}
                    onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                    placeholder="gratuit, frais, payant"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("knowledgePage.form.answerFr") || "Réponse (FR) *"}
                  </label>
                  <textarea
                    value={form.answer_fr}
                    onChange={(e) => setForm({ ...form, answer_fr: e.target.value })}
                    rows={3}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("knowledgePage.form.answerNl") || "Réponse (NL) — optionnel, sinon FR utilisé"}
                  </label>
                  <textarea
                    value={form.answer_nl}
                    onChange={(e) => setForm({ ...form, answer_nl: e.target.value })}
                    rows={2}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">
                    {t("knowledgePage.form.answerEn") || "Réponse (EN) — optionnel, sinon FR utilisé"}
                  </label>
                  <textarea
                    value={form.answer_en}
                    onChange={(e) => setForm({ ...form, answer_en: e.target.value })}
                    rows={2}
                    className={inputClass}
                  />
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={closeModal}
                    className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
                  >
                    {t("common.close")}
                  </button>
                  <button
                    type="submit"
                    disabled={saveMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                  >
                    {saveMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Save className="w-3.5 h-3.5" />
                    )}
                    <span>{t("common.save") || "Enregistrer"}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs z-[60]"
            onClick={() => !deleteMutation.isPending && setDeleteTarget(null)}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
            <div className="w-full max-w-sm bg-[var(--surface)] border border-danger rounded-2xl shadow-2xl p-5 space-y-3">
              <div className="flex items-center gap-2 text-danger font-bold text-sm">
                <Trash2 className="w-4 h-4" />
                <span>{t("knowledgePage.deleteConfirmTitle") || "Supprimer cette entrée ?"}</span>
              </div>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">
                « {deleteTarget.question} » — {t("knowledgePage.deleteConfirmBody") || "cette action est irréversible."}
              </p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setDeleteTarget(null)}
                  disabled={deleteMutation.isPending}
                  className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {t("common.close")}
                </button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deleteTarget.id)}
                  disabled={deleteMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[0.5rem] bg-danger text-white hover:opacity-90 text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
                >
                  {deleteMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{t("leads.drawer.deleteButton") || "Supprimer"}</span>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default KnowledgePage;
