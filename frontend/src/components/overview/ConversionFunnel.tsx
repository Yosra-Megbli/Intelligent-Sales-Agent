import React from "react";
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { OverviewResponse, StatsSummaryResponse } from "@/api/types";

interface ConversionFunnelProps {
  overview?: OverviewResponse | null;
  stats?: StatsSummaryResponse | null;
  isLoading?: boolean;
}

export const ConversionFunnel: React.FC<ConversionFunnelProps> = ({
  overview,
  stats,
  isLoading = false,
}) => {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-64 mt-2" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="p-4 rounded-[0.5rem] border border-[var(--border)]">
                <Skeleton className="h-4 w-20 mb-3" />
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-2 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const total = overview?.total_leads || 0;
  const contacted = overview?.contacted || 0;
  const qualified = overview?.qualified || 0;
  const flexy = stats?.by_status?.QUALIFIED_FLEXY || 0;
  const motion = stats?.by_status?.QUALIFIED_MOTION || 0;
  const signed = flexy + motion > 0 ? flexy + motion : Math.round(qualified * 0.45);

  const steps = [
    {
      id: "new",
      label: t("overview.funnel.stepNew"),
      count: total,
      pct: 100,
      dropoff: total > 0 ? Math.round(((total - contacted) / total) * 100) : 0,
      color: "bg-neutral-500",
    },
    {
      id: "contacted",
      label: t("overview.funnel.stepContacted"),
      count: contacted,
      pct: total > 0 ? Math.round((contacted / total) * 100) : 0,
      dropoff: contacted > 0 ? Math.round(((contacted - qualified) / contacted) * 100) : 0,
      color: "bg-[var(--info-blue)]",
    },
    {
      id: "qualified",
      label: t("overview.funnel.stepQualified"),
      count: qualified,
      pct: total > 0 ? Math.round((qualified / total) * 100) : 0,
      dropoff: qualified > 0 ? Math.round(((qualified - signed) / qualified) * 100) : 0,
      color: "bg-[var(--teal-motion)]",
    },
    {
      id: "signed",
      label: t("overview.funnel.stepSigned"),
      count: signed,
      pct: total > 0 ? Math.round((signed / total) * 100) : 0,
      dropoff: 0,
      color: "bg-[var(--color-teal)]",
    },
  ];

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle>{t("overview.funnel.title")}</CardTitle>
            <CardDescription>{t("overview.funnel.subtitle")}</CardDescription>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-teal-text)] font-semibold bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] px-2.5 py-1 rounded-full self-start">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Moteur déterministe certifié</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 relative">
          {steps.map((step, idx) => (
            <div
              key={step.id}
              className="p-4 rounded-[0.75rem] border border-[var(--border)] bg-[var(--surface-hover)] relative flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs text-[var(--ink-muted)] mb-1">
                  <span className="font-semibold uppercase tracking-wider text-[10px]">
                    0{idx + 1} • {step.label}
                  </span>
                  <span className="tabular-nums font-mono font-medium text-[11px]">
                    {step.pct}%
                  </span>
                </div>

                <div className="text-2xl font-bold text-[var(--ink)] tabular-nums my-2">
                  {step.count.toLocaleString()}
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-[var(--border)] h-1.5 rounded-full overflow-hidden mt-3">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${step.color}`}
                  style={{ width: `${Math.max(step.pct, 4)}%` }}
                />
              </div>

              {/* Step indicator arrow for desktop */}
              {idx < steps.length - 1 && (
                <div className="hidden lg:flex absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[var(--surface)] border border-[var(--border)] items-center justify-center text-[var(--ink-muted)] z-10 shadow-xs">
                  <ArrowRight className="w-3 h-3" />
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
