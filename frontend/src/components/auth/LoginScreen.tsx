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

/**
 * EcofixMark: Two crossed chevrons in brand teal
 */
const EcofixMark: React.FC<{ className?: string }> = ({ className = "w-6 h-6" }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`text-teal shrink-0 ${className}`}
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Crossed chevrons creating the Sophie/Ecofix energy emblem */}
    <path d="M4 8l8 6 8-6" />
    <path d="M4 14l8-6 8 6" />
  </svg>
);

/**
 * WindmillMotif: 3 thin white lines + center dot SVG, bottom-right, 420px, opacity 10%
 */
const WindmillMotif: React.FC = () => (
  <svg
    viewBox="0 0 420 420"
    className="absolute -bottom-16 -right-16 w-[420px] h-[420px] opacity-10 pointer-events-none text-white select-none"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Center dot */}
    <circle cx="210" cy="210" r="4.5" fill="currentColor" />
    {/* Blade 1 (0 deg: pointing upwards) */}
    <line x1="210" y1="210" x2="210" y2="25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    {/* Blade 2 (120 deg: bottom-right) */}
    <line x1="210" y1="210" x2="370" y2="302.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    {/* Blade 3 (240 deg: bottom-left) */}
    <line x1="210" y1="210" x2="50" y2="302.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

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
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-bg text-ink font-sans antialiased selection:bg-teal/20">
      {/* LEFT PANEL: 60% width on md+, hidden on mobile */}
      <div
        className="hidden md:flex md:w-[60%] flex-col justify-between p-10 lg:p-16 relative overflow-hidden text-white select-none bg-navy"
        style={{
          background:
            "radial-gradient(120% 90% at 15% 10%, oklch(15% 0.045 280) 0%, oklch(15% 0.045 280) 45%, oklch(45% 0.12 185) 100%)",
          opacity: 0.9,
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

        {/* Windmill motif: 3 thin white lines + center dot, bottom-right, opacity 10%, 420px */}
        <WindmillMotif />

        {/* Ambient glow decorative accent */}
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-teal/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-navy-soft/30 blur-3xl pointer-events-none" />

        {/* Top brand header: EcofixMark + wordmark "Sophie · Ecofix" */}
        <div className="relative z-10">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-white/10 border border-white/15 backdrop-blur-md flex items-center justify-center shadow-xs">
              <EcofixMark className="w-6 h-6 text-teal" />
            </div>
            <div>
              <span className="text-2xl font-bold tracking-tight text-white block">
                Sophie · Ecofix
              </span>
              <span className="text-xs text-teal font-medium tracking-wide uppercase">
                Ecofix Belgique
              </span>
            </div>
          </div>
        </div>

        {/* Center narrative statement */}
        <div className="relative z-10 max-w-xl my-auto py-12">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/10 border border-white/20 text-xs font-semibold text-white/90 mb-6 backdrop-blur-xs">
            <span className="w-2 h-2 rounded-full bg-teal animate-pulse" />
            <span>Agent Commercial Déterministe</span>
          </div>

          <h1 className="text-3xl lg:text-4xl font-extrabold tracking-tight text-white leading-tight">
            L'intelligence artificielle au service de la transition énergétique belge.
          </h1>

          <p className="mt-4 text-sm lg:text-base text-white/85 leading-relaxed font-normal">
            {t("login.brandTagline")}
          </p>
        </div>

        {/* Bottom Trust Badges: pill shape (rounded-full), bg-white/10, teal icons */}
        <div className="relative z-10 pt-6 border-t border-white/15">
          <p className="text-[11px] font-semibold text-white/70 uppercase tracking-wider mb-3">
            Standards de sécurité & conformité
          </p>
          <div className="flex flex-wrap items-center gap-3">
            {/* Badge 1: ShieldCheck - Conforme AI Act */}
            <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <ShieldCheck className="w-4 h-4 text-teal shrink-0" />
              <span>{t("login.badgeAiAct")}</span>
            </div>

            {/* Badge 2: Lock - RGPD by design */}
            <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <Lock className="w-4 h-4 text-teal shrink-0" />
              <span>{t("login.badgeGdpr")}</span>
            </div>

            {/* Badge 3: Globe2 - Hébergé UE-ready */}
            <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs transition-transform duration-200 hover:scale-[1.02]">
              <Globe2 className="w-4 h-4 text-teal shrink-0" />
              <span>{t("login.badgeHosting")}</span>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: 40% width on md+, full width on mobile */}
      <div className="w-full md:w-[40%] flex flex-col justify-between p-6 sm:p-8 lg:p-12 relative bg-bg min-h-screen">
        {/* Subtle top bar for mobile brand header + theme toggle */}
        <div className="w-full flex items-center justify-between">
          <div className="md:hidden flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-navy border border-white/10 flex items-center justify-center">
              <EcofixMark className="w-4 h-4 text-teal" />
            </div>
            <span className="font-bold text-sm text-ink tracking-tight">
              Sophie · Ecofix
            </span>
          </div>

          <div className="ml-auto">
            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-xl text-ink/70 hover:text-ink hover:bg-surface border border-transparent hover:border-[var(--border)] transition-all duration-200 cursor-pointer"
              title={theme === "dark" ? "Mode clair" : "Mode sombre"}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4 text-[var(--warn-amber)]" />
              ) : (
                <Moon className="w-4 h-4 text-ink/70" />
              )}
            </button>
          </div>
        </div>

        {/* Centered 400px Card: rounded-2xl, multi-layer soft shadow */}
        <div className="w-full max-w-[400px] mx-auto my-auto py-8">
          <div className="bg-surface border border-[var(--border)] rounded-2xl p-7 sm:p-8 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.04),0_12px_24px_-4px_rgba(0,0,0,0.06),0_24px_48px_-12px_rgba(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgba(0,0,0,0.45)] transition-all duration-200 relative overflow-hidden">
            {/* Top brand accent line */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-teal" />

            {/* Header */}
            <div className="mb-6">
              <h2 className="text-xl font-bold text-ink tracking-tight">
                {t("login.title")}
              </h2>
              <p className="text-xs text-ink/70 mt-1.5 leading-relaxed">
                {t("login.subtitle")}
              </p>
            </div>

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink mb-1.5">
                  {t("login.labelApiKey")}
                </label>
                <div
                  className={`relative flex items-center rounded-2xl transition-all duration-200 focus-within:ring-3 focus-within:ring-teal/40 ${
                    errorMessage
                      ? "ring-2 ring-danger/20"
                      : ""
                  }`}
                >
                  <KeyRound className="w-4 h-4 text-ink/40 absolute left-3.5 pointer-events-none" />
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => {
                      setApiKeyInput(e.target.value);
                      if (errorMessage) setErrorMessage(null);
                    }}
                    placeholder={t("login.placeholderApiKey")}
                    className={`w-full pl-10 pr-3.5 py-2.5 text-xs sm:text-sm font-mono rounded-2xl border bg-surface text-ink placeholder:text-ink/40 focus:outline-none transition-all duration-200 ${
                      errorMessage
                        ? "border-danger"
                        : "border-[var(--border)] focus:border-teal"
                    }`}
                    autoFocus
                    autoComplete="current-password"
                  />
                </div>

                {/* Inline Error State with Danger Border */}
                {errorMessage && (
                  <div className="flex items-center gap-2 mt-2.5 p-2.5 rounded-xl bg-danger/10 border border-danger/30 text-xs text-danger font-medium animate-in fade-in duration-200">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                )}
              </div>

              {/* CTA: rounded-full bg-lavender text-lavender-ink font-semibold, hover:bg-lavender-hover */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full mt-2 py-2.5 px-4 rounded-full bg-lavender hover:bg-lavender-hover text-lavender-ink text-sm font-semibold flex items-center justify-center gap-2 shadow-xs transition-all duration-200 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed group active:scale-[0.99]"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin shrink-0 text-lavender-ink" />
                    <span>{t("login.submitting")}</span>
                  </>
                ) : (
                  <>
                    <span>{t("login.submit")}</span>
                    <ArrowRight className="w-4 h-4 shrink-0 text-lavender-ink transition-transform duration-200 group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </form>

            {/* Optional Demo Key helper (if VITE_DEMO_API_KEY is configured) */}
            {demoApiKey && (
              <>
                <div className="flex items-center my-4 text-xs text-ink/40">
                  <div className="flex-1 border-t border-[var(--border)]" />
                  <span className="px-3 text-[10px] font-semibold uppercase tracking-wider text-ink/40">
                    {t("login.or")}
                  </span>
                  <div className="flex-1 border-t border-[var(--border)]" />
                </div>

                <button
                  type="button"
                  onClick={handleFillDemo}
                  className="w-full text-xs font-medium text-teal-dim hover:text-teal bg-teal/10 hover:bg-teal/15 py-2 px-3 rounded-full border border-teal/20 transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 shrink-0 text-teal-dim" />
                  <span>{t("login.useDemoKey")}</span>
                </button>
              </>
            )}

            {/* Footer with Language switcher + Help mailto */}
            <div className="mt-6 pt-5 border-t border-[var(--border)] flex items-center justify-between text-xs text-ink/70">
              {/* Pill group container: bg-ink/[0.04], active pill bg-surface + shadow-sm */}
              <div className="flex items-center gap-1 bg-ink/[0.04] p-1 rounded-full border border-[var(--border)]/60">
                {(["fr", "nl", "en"] as const).map((lang) => {
                  const isActive = currentLang === lang;
                  return (
                    <button
                      key={lang}
                      type="button"
                      onClick={() => i18n.changeLanguage(lang)}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase transition-all duration-150 cursor-pointer ${
                        isActive
                          ? "bg-surface text-ink shadow-sm font-bold"
                          : "text-ink/60 hover:text-ink"
                      }`}
                    >
                      {lang}
                    </button>
                  );
                })}
              </div>

              {/* Help Link mailto in teal-dim */}
              <a
                href="mailto:support@ecofix.be"
                className="text-[11px] text-teal-dim hover:text-teal hover:underline transition-colors font-medium"
              >
                {t("login.helpLink")}
              </a>
            </div>
          </div>
        </div>

        {/* Bottom subtle copyright */}
        <div className="text-center text-[11px] text-ink/40">
          <span>© {new Date().getFullYear()} Ecofix Belgique • Sophie AI</span>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
