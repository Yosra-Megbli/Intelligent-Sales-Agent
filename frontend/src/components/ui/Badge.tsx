import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { useTranslation } from "react-i18next";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export type BadgeVariant =
  | "NEW"
  | "CONTACTED"
  | "QUALIFIED_FLEXY"
  | "QUALIFIED_MOTION"
  | "FIXED_SEEKER"
  | "OPT_OUT"
  | "HUMAN_HANDOFF"
  | "LOST"
  | "CUSTOMER"
  | "CONTRACT"
  | "phase2"
  | "default";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant | string;
}

export const Badge: React.FC<BadgeProps> = ({ variant = "default", className, children, ...props }) => {
  const { t } = useTranslation();

  const styles: Record<string, string> = {
    NEW: "bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border-neutral-200 dark:border-neutral-700",
    CONTACTED: "bg-[var(--info-soft)] text-[var(--info-blue)] border-[var(--info-border)]",
    QUALIFIED_FLEXY: "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border-[var(--color-teal-soft-border)] font-semibold",
    QUALIFIED_MOTION: "bg-[var(--color-motion-soft)] text-[var(--color-motion)] border-[var(--color-motion-border)] font-semibold",
    FIXED_SEEKER: "bg-[var(--warn-soft)] text-[var(--warn-amber)] border-[var(--warn-border)]",
    OPT_OUT: "bg-pink-50 dark:bg-pink-950/40 text-pink-600 dark:text-pink-400 border-pink-200 dark:border-pink-900 line-through opacity-80",
    HUMAN_HANDOFF: "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800",
    LOST: "bg-[var(--danger-soft)] text-[var(--danger-red)] border-[var(--danger-border)]",
    CUSTOMER: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 font-bold",
    CONTRACT: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/30 font-semibold",
    phase2: "bg-[var(--warn-soft)] text-[var(--warn-amber)] border-[var(--warn-border)] uppercase tracking-wider text-[9px] font-bold py-0.5 px-1.5",
    default: "bg-[var(--surface-hover)] text-[var(--ink-muted)] border-[var(--border)]",
  };

  const displayText = children || (variant !== "phase2" && variant !== "default" ? t(`status.${variant}`, variant) : children);

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-2 py-0.5 text-xs font-medium rounded-full border border-solid transition-smooth select-none",
        styles[variant],
        className
      )}
      {...props}
    >
      {displayText}
    </span>
  );
};
