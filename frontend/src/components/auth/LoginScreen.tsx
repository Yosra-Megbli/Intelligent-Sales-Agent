import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useTranslation } from "react-i18next";
import {
  ShieldCheck,
  Lock,
  Globe2,
  KeyRound,
  ArrowRight,
  Loader2,
  AlertCircle,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";

export const LoginScreen: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [apiKeyInput, setApiKeyInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // VITE_DEMO_API_KEY from environment (optional helper)
  const demoApiKey = import.meta.env.VITE_DEMO_API_KEY as string | undefined;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      setErrorMessage(t("login.errorInvalid"));
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const success = await login(trimmed);
    if (!success) {
      setErrorMessage(t("login.errorInvalid"));
    }
    setIsSubmitting(false);
  };

  const handleFillDemo = () => {
    if (demoApiKey) {
      setApiKeyInput(demoApiKey);
      if (errorMessage) setErrorMessage(null);
    }
  };

  const currentLang = i18n.language ? i18n.language.substring(0, 2) : "fr";

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-[var(--bg-app)] text-[var(--ink)] font-sans antialiased selection:bg-[var(--brand-green)]/20">
      {/* LEFT PANEL: 60% width on md+, hidden on mobile */}
      <div
        className="hidden md:flex md:w-[60%] flex-col justify-between p-10 lg:p-16 relative overflow-hidden text-white select-none"
        style={{
          background: "linear-gradient(165deg, oklch(60% 0.14 160) 0%, oklch(48% 0.11 165) 100%)",
        }}
      >
        {/* Subtle 28px grid texture at 6% opacity */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(255, 255, 255, 0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.06) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        {/* Ambient glow decorative accent */}
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-white/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-black/15 blur-3xl pointer-events-none" />

        {/* Top brand header */}
        <div className="relative z-10">
          <div className="flex items-center gap-3.5">
            {/* 'S' logo chip */}
            <div className="w-12 h-12 rounded-[0.75rem] bg-white/15 border border-white/25 backdrop-blur-md flex items-center justify-center font-bold text-white text-2xl font-mono shadow-sm">
              S
            </div>
            <div>
              <span className="text-2xl font-bold tracking-tight text-white block">
                Sophie
              </span>
              <span className="text-xs text-white/80 font-medium tracking-wide uppercase">
                Ecofix Belgique
              </span>
            </div>
          </div>
        </div>

        {/* Center narrative statement */}
        <div className="relative z-10 max-w-xl my-auto py-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/20 text-xs font-semibold text-white/90 mb-6 backdrop-blur-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse" />
            <span>Agent Commercial Déterministe</span>
          </div>

          <h1 className="text-3xl lg:text-4xl font-extrabold tracking-tight text-white leading-tight">
            L'intelligence artificielle au service de la transition énergétique belge.
          </h1>

          <p className="mt-4 text-sm lg:text-base text-white/85 leading-relaxed font-normal">
            {t("login.brandTagline")}
          </p>
        </div>

        {/* Bottom Trust Badges (Lucide icons) */}
        <div className="relative z-10 pt-6 border-t border-white/15">
          <p className="text-[11px] font-semibold text-white/70 uppercase tracking-wider mb-3">
            Standards de sécurité & conformité
          </p>
          <div className="flex flex-wrap items-center gap-3">
            {/* Badge 1: ShieldCheck - Conforme AI Act */}
            <div className="px-3.5 py-2 rounded-[0.75rem] bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <ShieldCheck className="w-4 h-4 text-emerald-200 shrink-0" />
              <span>{t("login.badgeAiAct")}</span>
            </div>

            {/* Badge 2: Lock - RGPD by design */}
            <div className="px-3.5 py-2 rounded-[0.75rem] bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <Lock className="w-4 h-4 text-emerald-200 shrink-0" />
              <span>{t("login.badgeGdpr")}</span>
            </div>

            {/* Badge 3: Globe2 - Hébergé UE-ready */}
            <div className="px-3.5 py-2 rounded-[0.75rem] bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <Globe2 className="w-4 h-4 text-emerald-200 shrink-0" />
              <span>{t("login.badgeHosting")}</span>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: 40% width on md+, full width on mobile */}
      <div className="w-full md:w-[40%] flex flex-col justify-between p-6 sm:p-8 lg:p-12 relative bg-[var(--bg-app)] min-h-screen">
        {/* Subtle top bar for theme toggle */}
        <div className="w-full flex items-center justify-between">
          <div className="md:hidden flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-[0.5rem] bg-[var(--brand-green)] text-white font-bold font-mono flex items-center justify-center text-sm shadow-xs">
              S
            </div>
            <span className="font-bold text-base text-[var(--ink)] tracking-tight">
              Sophie
            </span>
          </div>

          <div className="ml-auto">
            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-[0.5rem] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface)] border border-transparent hover:border-[var(--border)] transition-all duration-200 cursor-pointer"
              title={theme === "dark" ? "Mode clair" : "Mode sombre"}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4 text-[var(--warn-amber)]" />
              ) : (
                <Moon className="w-4 h-4 text-[var(--ink-muted)]" />
              )}
            </button>
          </div>
        </div>

        {/* Centered 400px Card */}
        <div className="w-full max-w-[400px] mx-auto my-auto py-8">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] p-7 sm:p-8 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.04),0_12px_24px_-4px_rgba(0,0,0,0.06),0_24px_48px_-12px_rgba(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgba(0,0,0,0.45)] transition-all duration-200 relative overflow-hidden">
            {/* Top brand line indicator */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-[var(--brand-green)]" />

            {/* Header */}
            <div className="mb-6">
              <h2 className="text-xl font-bold text-[var(--ink)] tracking-tight">
                {t("login.title")}
              </h2>
              <p className="text-xs text-[var(--ink-muted)] mt-1.5 leading-relaxed">
                {t("login.subtitle")}
              </p>
            </div>

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[var(--ink)] mb-1.5">
                  {t("login.labelApiKey")}
                </label>
                <div
                  className={`relative flex items-center rounded-[0.75rem] transition-all duration-200 focus-within:ring-3 focus-within:ring-[var(--brand-green)]/30 ${
                    errorMessage
                      ? "ring-2 ring-[var(--danger-red)]/20"
                      : ""
                  }`}
                >
                  <KeyRound className="w-4 h-4 text-[var(--ink-muted)] absolute left-3.5 pointer-events-none" />
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => {
                      setApiKeyInput(e.target.value);
                      if (errorMessage) setErrorMessage(null);
                    }}
                    placeholder={t("login.placeholderApiKey")}
                    className={`w-full pl-10 pr-3.5 py-2.5 text-xs sm:text-sm font-mono rounded-[0.75rem] border bg-[var(--surface)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none transition-all duration-200 ${
                      errorMessage
                        ? "border-[var(--danger-red)]"
                        : "border-[var(--border)] focus:border-[var(--brand-green)]"
                    }`}
                    autoFocus
                    autoComplete="current-password"
                  />
                </div>

                {/* Inline Error State with Danger Border */}
                {errorMessage && (
                  <div className="flex items-center gap-2 mt-2.5 p-2.5 rounded-[0.5rem] bg-[var(--danger-soft)] border border-[var(--danger-border)] text-xs text-[var(--danger-red)] font-medium animate-in fade-in duration-200">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                )}
              </div>

              {/* Full-width brand green CTA with ArrowRight + Loader2 */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full mt-2 py-2.5 px-4 rounded-[0.75rem] bg-[var(--brand-green)] hover:bg-[var(--color-brand-hover)] active:bg-[var(--color-brand-active)] text-white text-sm font-semibold flex items-center justify-center gap-2 shadow-xs transition-all duration-200 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed group"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>{t("login.submitting")}</span>
                  </>
                ) : (
                  <>
                    <span>{t("login.submit")}</span>
                    <ArrowRight className="w-4 h-4 shrink-0 transition-transform duration-200 group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </form>

            {/* Optional Demo Key helper (if VITE_DEMO_API_KEY is configured) */}
            {demoApiKey && (
              <>
                <div className="flex items-center my-4 text-xs text-[var(--ink-subtle)]">
                  <div className="flex-1 border-t border-[var(--border)]" />
                  <span className="px-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--ink-subtle)]">
                    {t("login.or")}
                  </span>
                  <div className="flex-1 border-t border-[var(--border)]" />
                </div>

                <button
                  type="button"
                  onClick={handleFillDemo}
                  className="w-full text-xs font-medium text-[var(--brand-green)] hover:text-[var(--color-brand-hover)] bg-[var(--brand-soft)] hover:bg-[var(--brand-soft)]/80 py-2 px-3 rounded-[0.5rem] border border-[var(--brand-soft-border)] transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 shrink-0" />
                  <span>{t("login.useDemoKey")}</span>
                </button>
              </>
            )}

            {/* Footer with Language switcher + Help mailto */}
            <div className="mt-6 pt-5 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--ink-muted)]">
              {/* Language Switcher (FR / NL / EN) */}
              <div className="flex items-center gap-1 bg-[var(--bg-app)] p-0.5 rounded-[0.5rem] border border-[var(--border)]">
                {(["fr", "nl", "en"] as const).map((lang) => {
                  const isActive = currentLang === lang;
                  return (
                    <button
                      key={lang}
                      type="button"
                      onClick={() => i18n.changeLanguage(lang)}
                      className={`px-2 py-1 rounded-[0.375rem] text-[11px] font-semibold uppercase transition-all duration-150 cursor-pointer ${
                        isActive
                          ? "bg-[var(--surface)] text-[var(--brand-green)] shadow-xs font-bold"
                          : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                      }`}
                    >
                      {lang}
                    </button>
                  );
                })}
              </div>

              {/* Help Link mailto */}
              <a
                href="mailto:support@ecofix.be"
                className="text-[11px] text-[var(--ink-muted)] hover:text-[var(--brand-green)] hover:underline transition-colors font-medium"
              >
                {t("login.helpLink")}
              </a>
            </div>
          </div>
        </div>

        {/* Bottom subtle copyright */}
        <div className="text-center text-[11px] text-[var(--ink-subtle)]">
          <span>© {new Date().getFullYear()} Ecofix Belgique • Sophie AI</span>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
