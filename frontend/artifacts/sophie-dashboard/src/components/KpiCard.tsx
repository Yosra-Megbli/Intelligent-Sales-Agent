import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number | undefined;
  subtitle?: string;
  icon: LucideIcon;
  loading?: boolean;
  accent?: 'green' | 'amber' | 'red' | 'blue' | 'slate';
}

const ACCENT_CLASSES: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-600 ring-emerald-100',
  amber: 'bg-amber-50 text-amber-600 ring-amber-100',
  red:   'bg-red-50 text-red-600 ring-red-100',
  blue:  'bg-blue-50 text-blue-600 ring-blue-100',
  slate: 'bg-slate-50 text-slate-600 ring-slate-100',
};

const ACCENT_BAR: Record<string, string> = {
  green: 'bg-emerald-500',
  amber: 'bg-amber-500',
  red:   'bg-red-500',
  blue:  'bg-blue-500',
  slate: 'bg-slate-400',
};

export function KpiCard({ title, value, subtitle, icon: Icon, loading, accent = 'slate' }: KpiCardProps) {
  return (
    <Card className="group relative overflow-hidden border bg-card shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
      {/* Signature accent bar: a quiet strip of color that identifies the metric at a glance */}
      <div className={cn('absolute inset-x-0 top-0 h-0.5', ACCENT_BAR[accent])} />
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide truncate">{title}</p>
            {loading ? (
              <Skeleton className="mt-2 h-8 w-24" />
            ) : (
              <p className="mt-1 text-3xl font-bold text-foreground tabular-nums tracking-tight">{value ?? '—'}</p>
            )}
            {subtitle && !loading && (
              <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className={cn('rounded-lg p-2.5 shrink-0 ring-1 transition-transform duration-200 group-hover:scale-105', ACCENT_CLASSES[accent])}>
            <Icon className="h-5 w-5" strokeWidth={2} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
