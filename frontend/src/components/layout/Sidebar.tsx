import React from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Users,
  UserCheck,
  Megaphone,
  MessageSquare,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Zap,
  Settings,
  BookOpen,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";

export interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  collapsed,
  onToggleCollapse,
}) => {
  const { t } = useTranslation();

  const navItems = [
    {
      id: "overview",
      label: t("nav.overview"),
      icon: LayoutDashboard,
      isPhase2: false,
    },
    {
      id: "leads",
      label: t("nav.leads"),
      icon: Users,
      isPhase2: false,
    },
    {
      id: "conversations",
      label: t("conversations.title"),
      icon: MessageSquare,
      isPhase2: false,
    },
    {
      id: "chat",
      label: t("nav.chat"),
      icon: Zap,
      isPhase2: false,
    },
    {
      id: "campaigns",
      label: t("campaignsPage.title"),
      icon: Megaphone,
      isPhase2: false,
    },
    {
      id: "compliance",
      label: t("compliancePage.title"),
      icon: ShieldCheck,
      isPhase2: false,
    },
    {
      id: "knowledge",
      label: t("knowledgePage.title"),
      icon: BookOpen,
      isPhase2: false,
    },
    {
      id: "settings",
      label: t("settingsPage.title"),
      icon: Settings,
      isPhase2: false,
    },
  ];


  const handleNavClick = (item: (typeof navItems)[0]) => {
    if (item.isPhase2) {
      toast.info(t("toast.phase2Title"), {
        description: t("toast.phase2Desc"),
      });
      return;
    }
    onTabChange(item.id);
  };

  return (
    <aside
      className={`relative flex flex-col shrink-0 border-r border-[var(--border)] bg-[var(--surface)] transition-smooth z-30 select-none ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center px-4 border-b border-[var(--border)] justify-between">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-[0.5rem] bg-[var(--color-navy)] text-[var(--color-teal)] border border-white/10 flex items-center justify-center shrink-0 shadow-xs">
            <Zap className="w-4 h-4 fill-current" />
          </div>
          {!collapsed && (
            <div className="leading-none truncate">
              <span className="font-bold text-sm tracking-tight text-[var(--ink)] block">
                {t("brand.name")}
              </span>
              <span className="text-[10px] text-[var(--ink-muted)] block mt-0.5 truncate">
                {t("brand.company")}
              </span>
            </div>
          )}
        </div>

        <button
          onClick={onToggleCollapse}
          className="w-7 h-7 rounded-[0.5rem] flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-smooth cursor-pointer"
          title={collapsed ? "Agrandir" : "Réduire"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation list */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleNavClick(item)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-[0.5rem] text-xs font-medium transition-smooth cursor-pointer ${
                isActive
                  ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] font-semibold shadow-xs"
                  : "text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]"
              }`}
            >
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive ? "text-[var(--color-teal-text)]" : "text-[var(--ink-muted)]"
                }`}
              />
              {!collapsed && (
                <span className="flex-1 text-left truncate">{item.label}</span>
              )}
              {!collapsed && item.isPhase2 && (
                <Badge variant="phase2" className="ml-auto">
                  Phase 2
                </Badge>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer / System Status */}
      <div className="p-3 border-t border-[var(--border)]">
        {!collapsed ? (
          <div className="p-2.5 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[var(--color-teal)] animate-pulse" />
              <span className="text-[11px] font-medium text-[var(--ink)]">
                Sophie v1.0 • Ecofix
              </span>
            </div>
            <p className="text-[10px] text-[var(--ink-muted)] mt-1">
              Flandre (Fluvius) & Wallonie (ORES/RESA)
            </p>
          </div>
        ) : (
          <div className="flex justify-center" title="Sophie Online">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-teal)] animate-pulse" />
          </div>
        )}
      </div>
    </aside>
  );
};
