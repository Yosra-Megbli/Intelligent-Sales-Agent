import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "react-i18next";
import { KeyRound, ShieldCheck, ArrowRight, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";

export const ApiKeyModal: React.FC = () => {
  const { t } = useTranslation();
  const { login } = useAuth();
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    const success = await login(apiKeyInput);
    if (!success) {
      setErrorMessage(t("auth.invalidKey"));
    }
    setIsSubmitting(false);
  };

  const fillDemoKey = () => {
    // Quick demo helper using the project's standard key
    setApiKeyInput("sk-live-ecofix-demo-2026");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] shadow-xl p-7 relative overflow-hidden transition-smooth">
        {/* Subtle decorative top border */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-[var(--brand-green)]" />

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-[0.5rem] bg-[var(--brand-soft)] border border-[var(--brand-soft-border)] flex items-center justify-center text-[var(--brand-green)]">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--ink)] tracking-tight">
              {t("auth.title")}
            </h2>
            <p className="text-xs text-[var(--ink-muted)] flex items-center gap-1 mt-0.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--brand-green)]" />
              <span>{t("brand.company")} • {t("brand.tagline")}</span>
            </p>
          </div>
        </div>

        <p className="text-xs text-[var(--ink-muted)] leading-relaxed mb-6">
          {t("auth.subtitle")}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--ink)] mb-1.5">
              Clé d'authentification API (X-API-Key)
            </label>
            <div className="relative">
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => {
                  setApiKeyInput(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                placeholder={t("auth.keyPlaceholder")}
                className="w-full px-3.5 py-2.5 text-sm rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-green)] font-mono transition-smooth"
                autoFocus
              />
            </div>
            {errorMessage && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-[var(--danger-red)] font-medium">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}
          </div>

          <Button
            type="submit"
            size="lg"
            isLoading={isSubmitting}
            className="w-full text-sm font-semibold"
          >
            <span>{isSubmitting ? t("auth.connecting") : t("auth.connect")}</span>
            {!isSubmitting && <ArrowRight className="w-4 h-4 ml-1" />}
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-[var(--border)] flex flex-col gap-2">
          <p className="text-[11px] text-[var(--ink-subtle)] text-center">
            {t("auth.demoHint")}
          </p>
          <button
            type="button"
            onClick={fillDemoKey}
            className="text-xs text-[var(--brand-green)] hover:underline self-center font-medium cursor-pointer"
          >
            Utiliser la clé démo par défaut
          </button>
        </div>
      </div>
    </div>
  );
};
