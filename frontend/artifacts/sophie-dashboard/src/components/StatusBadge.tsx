import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  new:           { label: 'Nouveau',      className: 'bg-slate-100 text-slate-700 border-slate-300' },
  contacted:     { label: 'Contacté',     className: 'bg-blue-100 text-blue-700 border-blue-300' },
  replied:       { label: 'A répondu',    className: 'bg-indigo-100 text-indigo-700 border-indigo-300' },
  qualified:     { label: 'Qualifié',     className: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  rejected:      { label: 'Rejeté',       className: 'bg-red-100 text-red-700 border-red-300' },
  human_handoff: { label: 'Transfert',    className: 'bg-amber-100 text-amber-700 border-amber-300' },
  draft:         { label: 'Brouillon',    className: 'bg-slate-100 text-slate-600 border-slate-300' },
  running:       { label: 'En cours',     className: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  paused:        { label: 'En pause',     className: 'bg-amber-100 text-amber-700 border-amber-300' },
  completed:     { label: 'Terminée',     className: 'bg-blue-100 text-blue-700 border-blue-300' },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status.toLowerCase()] ?? { label: status, className: 'bg-gray-100 text-gray-600 border-gray-300' };
  return (
    <Badge
      variant="outline"
      className={cn('text-xs font-medium px-2 py-0.5', config.className, className)}
    >
      {config.label}
    </Badge>
  );
}
