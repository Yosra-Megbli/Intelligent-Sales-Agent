import React from "react";
import { Sparkline } from "@/components/ui/Sparkline";
import { Skeleton } from "@/components/ui/Skeleton";
import { TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";

export interface KpiCardProps {
  title: string;
  value: string | number;
  delta?: {
    value: number; // e.g. +14.2%
    label?: string; // e.g. "vs semaine précédente"
    isPositive?: boolean;
  };
  sparklineData?: number[];
  isLoading?: boolean;
  prefix?: string;
  suffix?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  delta,
  sparklineData,
  isLoading = false,
  prefix,
  suffix,
}) => {
  if (isLoading) {
    return (
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] p-5 shadow-xs flex flex-col justify-between h-[130px]">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-6 w-14" />
        </div>
        <Skeleton className="h-8 w-24 my-2" />
        <Skeleton className="h-3 w-36" />
      </div>
    );
  }

  const isPositive = delta ? delta.isPositive ?? delta.value >= 0 : true;

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[0.75rem] p-5 shadow-xs flex flex-col justify-between hover:border-[var(--border-hover)] transition-smooth">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-[var(--ink-muted)] truncate">
          {title}
        </span>
        {sparklineData && sparklineData.length > 0 && (
          <Sparkline
            data={sparklineData}
            positive={isPositive}
            width={56}
            height={20}
          />
        )}
      </div>

      <div className="my-2">
        <div className="text-2xl font-bold tracking-tight text-[var(--ink)] tabular-nums flex items-baseline gap-1">
          {prefix && <span className="text-base font-semibold">{prefix}</span>}
          <span>{value}</span>
          {suffix && <span className="text-sm font-medium text-[var(--ink-muted)]">{suffix}</span>}
        </div>
      </div>

      {delta ? (
        <div className="flex items-center gap-1.5 text-[11px]">
          <span
            className={`inline-flex items-center gap-0.5 font-medium px-1.5 py-0.5 rounded-[0.35rem] ${
              delta.value === 0
                ? "bg-[var(--surface-hover)] text-[var(--ink-muted)]"
                : isPositive
                ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)]"
                : "bg-[var(--danger-soft)] text-[var(--danger-red)]"
            }`}
          >
            {delta.value === 0 ? (
              <Minus className="w-3 h-3" />
            ) : isPositive ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            <span className="tabular-nums">
              {delta.value > 0 ? `+${delta.value}%` : `${delta.value}%`}
            </span>
          </span>
          {delta.label && (
            <span className="text-[var(--ink-subtle)] truncate">
              {delta.label}
            </span>
          )}
        </div>
      ) : (
        /* No invented delta: show a neutral real-time indicator */
        <div className="flex items-center gap-1 text-[10px] text-[var(--ink-subtle)]">
          <Activity className="w-3 h-3 text-[var(--color-teal)]" />
          <span>Données en temps réel</span>
        </div>
      )}
    </div>
  );
};
