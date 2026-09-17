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
    <div className="min-h-screen w-full bg-[radial-gradient(circle_at_top,_rgba(137,196,255,0.16),_rgba(255,255,255,0)_35%)] bg-bg text-ink font-sans antialiased selection:bg-teal/20">
      <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col lg:flex-row">
        {/* LEFT PANEL: 60% width on lg+, hidden on smaller screens */}
        <div
          className="hidden lg:flex lg:w-[58%] flex-col justify-between relative overflow-hidden p-8 xl:p-12 text-white select-none bg-navy"
          style={{
            background:
              "radial-gradient(120% 90% at 15% 10%, oklch(15% 0.045 280) 0%, oklch(15% 0.045 280) 45%, oklch(45% 0.12 185) 100%)",
            opacity: 0.95,
          }}
        >
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgba(255, 255, 255, 0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.06) 1px, transparent 1px)",
              backgroundSize: "28px 28px",
            }}
          />

          <WindmillMotif />

          <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-teal/10 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-navy-soft/30 blur-3xl pointer-events-none" />

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

          <div className="relative z-10 max-w-xl py-12">
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/10 border border-white/20 text-xs font-semibold text-white/90 mb-6 backdrop-blur-xs">
              <span className="w-2 h-2 rounded-full bg-teal animate-pulse" />
              <span>Agent Commercial Déterministe</span>
            </div>

            <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight text-white leading-tight">
              L'intelligence artificielle au service de la transition énergétique belge.
            </h1>

            <p className="mt-4 text-sm xl:text-base text-white/85 leading-relaxed font-normal">
              {t("login.brandTagline")}
            </p>
          </div>

          <div className="relative z-10 pt-6 border-t border-white/15">
            <p className="text-[11px] font-semibold text-white/70 uppercase tracking-wider mb-3">
              Standards de sécurité & conformité
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs">
                <ShieldCheck className="w-4 h-4 text-teal shrink-0" />
                <span>{t("login.badgeAiAct")}</span>
              </div>

              <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs">
                <Lock className="w-4 h-4 text-teal shrink-0" />
                <span>{t("login.badgeGdpr")}</span>
              </div>

              <div className="px-4 py-2 rounded-full bg-white/10 border border-white/20 backdrop-blur-xs text-xs font-medium text-white flex items-center gap-2 shadow-xs">
                <Globe2 className="w-4 h-4 text-teal shrink-0" />
                <span>{t("login.badgeHosting")}</span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL: form area */}
        <div className="flex w-full flex-1 items-center justify-center bg-bg px-4 py-5 sm:px-6 sm:py-8 lg:w-[42%] lg:px-8 xl:px-12">
          <div className="w-full max-w-[440px]">
            <div className="mb-5 flex items-center justify-between gap-3 lg:hidden">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-navy border border-white/10 shadow-sm">
                  <EcofixMark className="h-4 w-4 text-teal" />
                </div>
                <div>
                  <div className="text-sm font-bold tracking-tight text-ink">Sophie · Ecofix</div>
                  <div className="text-[10px] uppercase tracking-[0.12em] text-ink/50">Ecofix Belgique</div>
                </div>
              </div>

              <button
                type="button"
                onClick={toggleTheme}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-surface text-ink/70 transition hover:border-[var(--border-hover)] hover:text-ink"
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

            <div className="rounded-[28px] border border-[var(--border)] bg-surface p-5 shadow-[0_8px_32px_rgba(15,23,42,0.08)] sm:p-7 lg:p-8">
              <div className="mb-6 hidden items-center justify-between lg:flex">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-navy/95 shadow-sm">
                    <EcofixMark className="h-5 w-5 text-teal" />
                  </div>
                  <div>
                    <div className="text-lg font-bold tracking-tight text-ink">Sophie AI</div>
                    <div className="text-[10px] uppercase tracking-[0.12em] text-ink/50">Console sécurisée</div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={toggleTheme}
                  className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--border)] bg-surface text-ink/70 transition hover:border-[var(--border-hover)] hover:text-ink"
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

              <div className="mb-6">
                <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-teal/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-teal-dim border border-teal/15">
                  <span className="h-2 w-2 rounded-full bg-teal" />
                  {t("login.helpLink")}
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-ink sm:text-[2rem]">
                  {t("login.title")}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-ink/70 sm:text-[0.95rem]">
                  {t("login.subtitle")}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-ink sm:text-sm">
                    {t("login.labelApiKey")}
                  </label>
                  <div
                    className={`relative flex items-center rounded-2xl transition-all duration-200 focus-within:ring-3 focus-within:ring-teal/40 ${
                      errorMessage ? "ring-2 ring-danger/20" : ""
                    }`}
                  >
                    <KeyRound className="pointer-events-none absolute left-3.5 h-4 w-4 text-ink/40" />
                    <input
                      type="password"
                      value={apiKeyInput}
                      onChange={(e) => {
                        setApiKeyInput(e.target.value);
                        if (errorMessage) setErrorMessage(null);
                      }}
                      placeholder={t("login.placeholderApiKey")}
                      className={`w-full rounded-2xl border bg-surface py-3 pl-10 pr-3.5 text-xs font-mono text-ink placeholder:text-ink/40 focus:outline-none transition-all duration-200 sm:text-sm ${
                        errorMessage ? "border-danger" : "border-[var(--border)] focus:border-teal"
                      }`}
                      autoFocus
                      autoComplete="current-password"
                    />
                  </div>

                  {errorMessage && (
                    <div className="mt-2.5 flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/10 p-2.5 text-xs font-medium text-danger animate-in fade-in duration-200">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>{errorMessage}</span>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="group mt-1 flex w-full items-center justify-center gap-2 rounded-full bg-lavender px-4 py-3 text-sm font-semibold text-lavender-ink shadow-xs transition hover:bg-lavender-hover disabled:cursor-not-allowed disabled:opacity-80"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin shrink-0 text-lavender-ink" />
                      <span>{t("login.submitting")}</span>
                    </>
                  ) : (
                    <>
                      <span>{t("login.submit")}</span>
                      <ArrowRight className="h-4 w-4 shrink-0 text-lavender-ink transition-transform duration-200 group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>

              {demoApiKey && (
                <>
                  <div className="my-4 flex items-center gap-3 text-xs text-ink/40">
                    <div className="h-px flex-1 bg-[var(--border)]" />
                    <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink/40">
                      {t("login.or")}
                    </span>
                    <div className="h-px flex-1 bg-[var(--border)]" />
                  </div>

                  <button
                    type="button"
                    onClick={handleFillDemo}
                    className="flex w-full items-center justify-center gap-2 rounded-full border border-teal/20 bg-teal/10 px-3 py-2.5 text-xs font-medium text-teal-dim transition hover:bg-teal/15"
                  >
                    <Sparkles className="h-3.5 w-3.5 shrink-0 text-teal-dim" />
                    <span>{t("login.useDemoKey")}</span>
                  </button>
                </>
              )}

              <div className="mt-6 flex items-center justify-between gap-3 border-t border-[var(--border)] pt-5 text-xs text-ink/70">
                <div className="flex items-center gap-1 rounded-full border border-[var(--border)]/60 bg-ink/[0.04] p-1">
                  {(["fr", "nl", "en"] as const).map((lang) => {
                    const isActive = currentLang === lang;
                    return (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => i18n.changeLanguage(lang)}
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase transition-all duration-150 ${
                          isActive ? "bg-surface text-ink shadow-sm" : "text-ink/60 hover:text-ink"
                        }`}
                      >
                        {lang}
                      </button>
                    );
                  })}
                </div>

                <a
                  href="mailto:support@ecofix.be"
                  className="text-[11px] font-medium text-teal-dim transition hover:text-teal hover:underline"
                >
                  {t("login.helpLink")}
                </a>
              </div>
            </div>

            <div className="mt-4 text-center text-[11px] text-ink/40">
              <span>© {new Date().getFullYear()} Ecofix Belgique • Sophie AI</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
