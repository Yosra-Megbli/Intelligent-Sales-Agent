import { Skeleton } from '@/components/ui/skeleton';

export function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  // Varied widths per column mimic real text instead of uniform bars —
  // uniform-width skeletons read as "generic loading", varied ones read
  // as "content is about to appear here".
  const widths = ['w-3/4', 'w-1/2', 'w-2/3', 'w-1/3', 'w-full'];
  return (
    <div className="rounded-lg border divide-y overflow-hidden">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className={`h-4 flex-1 ${widths[j % widths.length]}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="relative overflow-hidden rounded-xl border bg-card p-5">
          <div className="absolute inset-x-0 top-0 h-0.5 bg-muted" />
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  // Mirrors the campaign-card layout: title row, three stat blocks, a
  // progress bar, and an action row — so cards don't "pop" into place.
  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-5 w-16 rounded-full shrink-0" />
      </div>
      <Skeleton className="h-3 w-1/3" />
      <div className="flex gap-4 pt-1">
        <Skeleton className="h-8 w-10" />
        <Skeleton className="h-8 w-10" />
        <Skeleton className="h-8 w-10" />
      </div>
      <Skeleton className="h-1.5 w-full rounded-full" />
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-8 rounded-md" />
      </div>
    </div>
  );
}
