import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { KnowledgeEntry } from "@/api/types";
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
  const [searchTerm, setSearchTerm] = useState("");
  const [editingEntry, setEditingEntry] = useState<KnowledgeEntry | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState<EntryFormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeEntry | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["knowledgeEntries"],
    queryFn: () => apiClient.getKnowledgeEntries(),
  });

  const entries = data?.items || [];
  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.question.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q) ||
        e.keywords.some((k) => k.toLowerCase().includes(q))
    );
  }, [entries, searchTerm]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["knowledgeEntries"] });
  };

  const toggleMutation = useMutation({
    mutationFn: (id: string) => apiClient.toggleKnowledgeEntryActive(id),
    onSuccess: invalidate,
    onError: (err: any) => toast.error(err?.message || "Erreur"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteKnowledgeEntry(id),
    onSuccess: () => {
      toast.success(t("knowledgePage.deleteSuccess") || "Entrée supprimée");
      invalidate();
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
      const payload = {
        category: form.category,
        question: form.question,
        keywords,
        answer_fr: form.answer_fr,
        answer_nl: form.answer_nl || undefined,
        answer_en: form.answer_en || undefined,
      };
      return editingEntry
        ? apiClient.updateKnowledgeEntry(editingEntry.id, payload)
        : apiClient.createKnowledgeEntry(payload);
    },
    onSuccess: () => {
      toast.success(
        editingEntry
          ? t("knowledgePage.updateSuccess") || "Entrée mise à jour"
          : t("knowledgePage.createSuccess") || "Entrée créée"
      );
      invalidate();
      closeModal();
    },
    onError: (err: any) => toast.error(err?.message || "Erreur lors de l'enregistrement"),
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
    if (saveMutation.isPending) return;
    setIsModalOpen(false);
    setEditingEntry(null);
    setForm(EMPTY_FORM);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.question.trim() || !form.answer_fr.trim() || !form.keywords.trim()) {
      toast.error(t("knowledgePage.validationError") || "Question, mots-clés et réponse FR sont requis");
      return;
    }
    saveMutation.mutate();
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)] flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[var(--color-teal)]" />
            {t("knowledgePage.title") || "Base de Connaissances"}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            {t("knowledgePage.subtitle") ||
              "Faits et réponses que Sophie est autorisée à donner aux questions et objections."}
          </p>
        </div>
        <Button size="sm" onClick={openCreateModal} className="text-xs">
          <Plus className="w-3.5 h-3.5 mr-1" />
          <span>{t("knowledgePage.addButton") || "Ajouter une entrée"}</span>
        </Button>
      </div>

      {/* Honest RAG v2 banner */}
      <div className="flex items-start gap-2.5 p-3.5 rounded-[0.75rem] bg-[var(--color-teal-soft)]/30 border border-[var(--color-teal-soft-border)] text-xs text-[var(--ink)]">
        <Info className="w-4 h-4 text-[var(--color-teal)] shrink-0 mt-0.5" />
        <span>
          {t("knowledgePage.ragV1Banner") ||
            "RAG mot-clé v1 — la recherche vectorielle avec documents PDF (upload, versions, obsolescence) arrive en RAG v2 — voir docs/RAG_BACKLOG.md."}
        </span>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--ink-subtle)]" />
        <input
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder={t("knowledgePage.searchPlaceholder") || "Filtrer par question, catégorie, mot-clé..."}
          className="w-full pl-9 pr-3 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:border-[var(--color-teal)] transition-smooth"
        />
      </div>

      <div className="rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-[var(--surface-hover)] border-b border-[var(--border)]">
              <tr className="text-left text-[var(--ink-muted)]">
                <th className="px-4 py-2.5 font-semibold">{t("knowledgePage.table.category") || "Catégorie"}</th>
                <th className="px-4 py-2.5 font-semibold">{t("knowledgePage.table.question") || "Question"}</th>
                <th className="px-4 py-2.5 font-semibold">{t("knowledgePage.table.languages") || "Langues"}</th>
                <th className="px-4 py-2.5 font-semibold text-center">{t("knowledgePage.table.active") || "Actif"}</th>
                <th className="px-4 py-2.5 font-semibold text-right">{t("knowledgePage.table.actions") || "Actions"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3" colSpan={5}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-[var(--ink-muted)]" colSpan={5}>
                    {t("knowledgePage.empty") || "Aucune entrée trouvée."}
                  </td>
                </tr>
              ) : (
                filtered.map((entry) => {
                  const langs = [
                    "FR",
                    entry.answer_nl ? "NL" : null,
                    entry.answer_en ? "EN" : null,
                  ].filter(Boolean);
                  return (
                    <tr key={entry.id} className="hover:bg-[var(--surface-hover)] transition-smooth">
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)]">
                          {entry.category}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--ink)] font-medium max-w-xs truncate">
                        {entry.question}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex gap-1">
                          {langs.map((l) => (
                            <span
                              key={l}
                              className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink-muted)]"
                            >
                              {l}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <button
                          type="button"
                          onClick={() => toggleMutation.mutate(entry.id)}
                          disabled={toggleMutation.isPending}
                          role="switch"
                          aria-checked={entry.active}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-smooth cursor-pointer disabled:opacity-50 ${
                            entry.active ? "bg-[var(--color-teal)]" : "bg-[var(--border)]"
                          }`}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                              entry.active ? "translate-x-[18px]" : "translate-x-1"
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openEditModal(entry)}
                            className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--color-teal)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                            title={t("leads.drawer.editButton") || "Modifier"}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteTarget(entry)}
                            className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-danger hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
                            title={t("leads.drawer.deleteButton") || "Supprimer"}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
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

      {/* Create/Edit modal */}
      {isModalOpen && (
        <>
          <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40" onClick={closeModal} aria-hidden="true" />
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
