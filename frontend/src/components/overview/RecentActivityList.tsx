import React from "react";
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { ActivityFeedEntryResponse } from "@/api/types";
import { ShieldAlert, Clock, ArrowUpRight } from "lucide-react";

interface RecentActivityListProps {
  activities?: ActivityFeedEntryResponse[] | null;
  isLoading?: boolean;
}

export const RecentActivityList: React.FC<RecentActivityListProps> = ({
  activities,
  isLoading = false,
}) => {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-3 w-56 mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
              <div className="flex items-center gap-3">
                <Skeleton className="w-8 h-8 rounded-full" />
                <div>
                  <Skeleton className="h-4 w-32 mb-1" />
                  <Skeleton className="h-3 w-48" />
                </div>
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  const items = activities || [];

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{t("overview.recentActivity.title")}</CardTitle>
            <CardDescription>{t("overview.recentActivity.subtitle")}</CardDescription>
          </div>
          <span className="text-xs font-mono text-[var(--ink-subtle)] flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Dernière synchro temps réel</span>
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="py-8 text-center text-xs text-[var(--ink-muted)]">
            {t("overview.recentActivity.empty")}
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {items.map((entry) => {
              const isOptOut = entry.type.includes("OPT_OUT") || (entry.details && entry.details.includes("STOP"));

              return (
                <div
                  key={entry.id}
                  className={`py-3 flex items-center justify-between gap-4 transition-smooth ${
                    isOptOut ? "opacity-75 bg-pink-50/30 dark:bg-pink-950/10 px-2 rounded" : ""
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${
                        isOptOut
                          ? "bg-pink-100 dark:bg-pink-900/30 text-pink-600 border-pink-200"
                          : "bg-[var(--surface-hover)] text-[var(--ink-muted)] border-[var(--border)]"
                      }`}
                    >
                      {isOptOut ? (
                        <ShieldAlert className="w-4 h-4 text-pink-600 dark:text-pink-400" />
                      ) : (
                        <ArrowUpRight className="w-4 h-4 text-[var(--color-teal-text)]" />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-semibold truncate ${
                            isOptOut
                              ? "line-through text-pink-700 dark:text-pink-300 font-mono"
                              : "text-[var(--ink)]"
                          }`}
                        >
                          {isOptOut ? t("compliance.gdprPurged") : entry.lead_name}
                        </span>
                        {isOptOut && (
                          <Badge variant="OPT_OUT">
                            {t("status.OPT_OUT")}
                          </Badge>
                        )}
                      </div>
                      <p className="text-[11px] text-[var(--ink-muted)] truncate mt-0.5">
                        {entry.details || entry.type}
                      </p>
                    </div>
                  </div>

                  <div className="text-[11px] font-mono text-[var(--ink-subtle)] shrink-0">
                    {new Date(entry.created_at).toLocaleTimeString("fr-BE", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
