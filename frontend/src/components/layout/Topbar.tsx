import React from "react";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useAuth } from "@/context/AuthContext";
import {
  Search,
  Moon,
  Sun,
  Globe,
  Key,
  LogOut,
  Radio,
} from "lucide-react";

interface TopbarProps {
  onSearchChange?: (q: string) => void;
}

export const Topbar: React.FC<TopbarProps> = ({ onSearchChange }) => {
  const { t, i18n } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const { apiKey, logout } = useAuth();

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem("sophie_language", lang);
  };

  const keyDisplay = apiKey
    ? `${apiKey.slice(0, 5)}...${apiKey.slice(-4)}`
    : "Non connecté";

  return (
    <header className="h-16 border-b border-[var(--border)] bg-[var(--surface)] px-6 flex items-center justify-between gap-4 select-none shrink-0 z-20">
      {/* Search Bar */}
      <div className="flex-1 max-w-md relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-subtle)] pointer-events-none" />
        <input
          type="text"
          placeholder={t("topbar.search")}
          onChange={(e) => onSearchChange?.(e.target.value)}
          className="w-full pl-9 pr-12 py-1.5 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)] focus:bg-[var(--surface)] transition-smooth"
        />
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5 text-[10px] text-[var(--ink-subtle)] font-mono border border-[var(--border)] rounded px-1 bg-[var(--surface)]">
          <span>⌘K</span>
        </div>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {/* Backend live indicator */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] text-xs">
          <Radio className="w-3.5 h-3.5 text-[var(--color-teal)] animate-pulse" />
          <span className="text-[11px] font-medium text-[var(--ink-muted)]">
            Render Cloud
          </span>
        </div>

        {/* Language Switcher */}
        <div className="flex items-center border border-[var(--border)] rounded-[0.5rem] bg-[var(--surface-hover)] p-0.5 text-xs font-medium">
          {(["fr", "nl", "en"] as const).map((lang) => {
            const isCurrent = i18n.language.startsWith(lang);
            return (
              <button
                key={lang}
                onClick={() => handleLanguageChange(lang)}
                className={`px-2 py-1 rounded-[0.35rem] uppercase text-[11px] font-semibold transition-smooth cursor-pointer ${
                  isCurrent
                    ? "bg-[var(--surface)] text-[var(--color-teal-text)] shadow-xs font-bold"
                    : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {lang}
              </button>
            );
          })}
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="w-8 h-8 rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] hover:bg-[var(--surface)] flex items-center justify-center text-[var(--ink)] transition-smooth cursor-pointer"
          title={theme === "dark" ? t("topbar.themeLight") : t("topbar.themeDark")}
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-neutral-600" />
          )}
        </button>

        {/* Auth / Key Indicator & Logout */}
        <div className="flex items-center gap-1.5 pl-2 border-l border-[var(--border)]">
          <div
            className="flex items-center gap-1.5 px-2 py-1 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] font-mono text-[11px] text-[var(--ink-muted)]"
            title="Clé API active"
          >
            <Key className="w-3 h-3 text-[var(--color-teal-text)]" />
            <span>{keyDisplay}</span>
          </div>

          <button
            onClick={logout}
            className="w-8 h-8 rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface-hover)] hover:bg-red-50 hover:text-[var(--danger-red)] dark:hover:bg-red-950/40 flex items-center justify-center text-[var(--ink-muted)] transition-smooth cursor-pointer"
            title={t("auth.logout")}
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
};
