import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { X, Loader2, UserPlus, AlertCircle } from "lucide-react";
import { toast } from "sonner";

interface AddLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface FormState {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  region: string;
  city: string;
  customer_type: string;
  current_supplier: string;
  ean: string;
}

const EMPTY_FORM: FormState = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  region: "",
  city: "",
  customer_type: "",
  current_supplier: "",
  ean: "",
};

// Mirrors backend/business_rules/validation_rules.yaml, read through
// application/lead_service.py's create_lead - client-side feedback only,
// never the source of truth. The server re-validates every field
// regardless of what passes here.
const PHONE_PATTERN = /^0[0-9]{8,9}$/;
const EAN_PATTERN = /^[0-9]{18}$/;

const inputClass = (hasError?: boolean) =>
  `w-full px-3 py-2 text-xs rounded-[0.5rem] border bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none transition-smooth ${
    hasError
      ? "border-danger focus:border-danger"
      : "border-[var(--border)] focus:border-[var(--color-teal)]"
  }`;

export const AddLeadModal: React.FC<AddLeadModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.createLead({
        first_name: form.first_name || undefined,
        last_name: form.last_name || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        region: form.region || undefined,
        city: form.city || undefined,
        customer_type: form.customer_type || undefined,
        current_supplier: form.current_supplier || undefined,
        ean: form.ean || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.success(t("leads.addModal.success") || "Prospect ajouté avec succès");
      setForm(EMPTY_FORM);
      setErrors({});
      onClose();
    },
    onError: (err: any) => {
      const code = err?.code;
      if (code === "duplicate_lead") {
        toast.error(t("leads.addModal.errorDuplicate") || "Un prospect avec cet email/téléphone existe déjà");
      } else if (code === "rijksregisternummer_rejected") {
        toast.error(t("leads.addModal.errorRrn") || "Ce champ ressemble à un numéro de registre national — jamais collecté");
      } else {
        toast.error(err?.message || t("leads.addModal.errorGeneric") || "Erreur lors de la création du prospect");
      }
    },
  });

  const setField = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = (): boolean => {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (form.email && !form.email.includes("@")) {
      next.email = t("leads.addModal.invalidEmail") || "Email invalide";
    }
    if (form.phone && !PHONE_PATTERN.test(form.phone)) {
      next.phone = t("leads.addModal.invalidPhone") || "Format belge attendu : 0XXXXXXXXX";
    }
    if (form.ean && !EAN_PATTERN.test(form.ean)) {
      next.ean = t("leads.addModal.invalidEan") || "18 chiffres attendus";
    }
    if (form.region && form.region !== "Wallonie" && form.region !== "Flandre") {
      next.region = t("leads.addModal.invalidRegion") || "Zone hors couverture (Bruxelles non desservi)";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    mutation.mutate();
  };

  const handleClose = () => {
    if (mutation.isPending) return;
    setForm(EMPTY_FORM);
    setErrors({});
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-40" onClick={handleClose} aria-hidden="true" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t("leads.addModal.title") || "Ajouter un prospect"}
          className="w-full max-w-lg bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden"
        >
          <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--surface-hover)]">
            <div className="flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-[var(--color-teal)]" />
              <h2 className="text-sm font-bold text-[var(--ink)]">
                {t("leads.addModal.title") || "Ajouter un prospect"}
              </h2>
            </div>
            <button
              onClick={handleClose}
              className="p-1.5 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--border)]/40 transition-smooth cursor-pointer"
              aria-label={t("common.close")}
              type="button"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("leads.drawer.fields.fullName") + " (prénom)"}>
                <input
                  value={form.first_name}
                  onChange={(e) => setField("first_name", e.target.value)}
                  className={inputClass()}
                  autoFocus
                />
              </Field>
              <Field label={t("leads.drawer.fields.fullName") + " (nom)"}>
                <input
                  value={form.last_name}
                  onChange={(e) => setField("last_name", e.target.value)}
                  className={inputClass()}
                />
              </Field>
            </div>

            <Field label={t("leads.drawer.fields.email")} error={errors.email}>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setField("email", e.target.value)}
                className={inputClass(!!errors.email)}
              />
            </Field>

            <Field label={t("leads.drawer.fields.phone")} error={errors.phone}>
              <input
                value={form.phone}
                onChange={(e) => setField("phone", e.target.value)}
                placeholder="0488112233"
                className={inputClass(!!errors.phone)}
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label={t("leads.drawer.fields.location")} error={errors.region}>
                <select
                  value={form.region}
                  onChange={(e) => setField("region", e.target.value)}
                  className={inputClass(!!errors.region)}
                >
                  <option value="">—</option>
                  <option value="Wallonie">Wallonie</option>
                  <option value="Flandre">Flandre</option>
                </select>
              </Field>
              <Field label="Ville">
                <input
                  value={form.city}
                  onChange={(e) => setField("city", e.target.value)}
                  className={inputClass()}
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label={t("leads.drawer.fields.customerType")}>
                <select
                  value={form.customer_type}
                  onChange={(e) => setField("customer_type", e.target.value)}
                  className={inputClass()}
                >
                  <option value="">—</option>
                  <option value="particulier">Particulier</option>
                  <option value="professionnel">Professionnel</option>
                </select>
              </Field>
              <Field label={t("leads.drawer.fields.supplier")}>
                <input
                  value={form.current_supplier}
                  onChange={(e) => setField("current_supplier", e.target.value)}
                  className={inputClass()}
                />
              </Field>
            </div>

            <Field label={t("leads.drawer.fields.ean")} error={errors.ean}>
              <input
                value={form.ean}
                onChange={(e) => setField("ean", e.target.value)}
                placeholder="5414..."
                className={`${inputClass(!!errors.ean)} font-mono`}
              />
            </Field>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleClose}
                className="px-3 py-1.5 rounded-[0.5rem] text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
              >
                {t("common.close")}
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[var(--color-teal)] text-white hover:bg-[var(--color-teal-hover)] text-xs font-semibold transition-smooth cursor-pointer disabled:opacity-50"
              >
                {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{t("leads.addModal.submit") || "Ajouter le prospect"}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
};

const Field: React.FC<{ label: string; error?: string; children: React.ReactNode }> = ({
  label,
  error,
  children,
}) => (
  <div>
    <label className="block text-[11px] font-semibold text-[var(--ink-muted)] mb-1">{label}</label>
    {children}
    {error && (
      <div className="flex items-center gap-1 mt-1 text-[10px] text-danger">
        <AlertCircle className="w-3 h-3 shrink-0" />
        <span>{error}</span>
      </div>
    )}
  </div>
);

export default AddLeadModal;
