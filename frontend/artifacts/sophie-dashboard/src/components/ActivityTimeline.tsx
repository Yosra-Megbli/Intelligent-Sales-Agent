import { useListActivities } from '@workspace/api-client-react';
import type { ActivityFeedEntry } from '@workspace/api-client-react';
import { Link } from 'wouter';
import {
  History, MessageSquarePlus, MessageSquareText, RefreshCw, Send,
  CheckCircle2, XCircle, UserCheck, UploadCloud, CircleDot,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingState';

const TYPE_CONFIG: Record<string, { label: string; icon: typeof CircleDot; className: string }> = {
  MESSAGE_SENT:     { label: 'Message envoyé',   icon: Send,                className: 'text-blue-600 bg-blue-50' },
  MESSAGE_RECEIVED: { label: 'Message reçu',      icon: MessageSquareText,   className: 'text-indigo-600 bg-indigo-50' },
  STATUS_CHANGED:   { label: 'Statut modifié',    icon: RefreshCw,           className: 'text-slate-600 bg-slate-100' },
  STATE_CHANGED:    { label: 'Conversation',      icon: RefreshCw,           className: 'text-slate-600 bg-slate-100' },
  FOLLOW_UP_SENT:   { label: 'Relance envoyée',   icon: MessageSquarePlus,   className: 'text-amber-600 bg-amber-50' },
  QUALIFIED:        { label: 'Lead qualifié',     icon: CheckCircle2,        className: 'text-emerald-600 bg-emerald-50' },
  REJECTED:         { label: 'Lead rejeté',       icon: XCircle,             className: 'text-red-600 bg-red-50' },
  HUMAN_HANDOFF:    { label: 'Transfert humain',  icon: UserCheck,          className: 'text-amber-600 bg-amber-50' },
  LEAD_IMPORTED:    { label: 'Lead importé',      icon: UploadCloud,        className: 'text-blue-600 bg-blue-50' },
};

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.round(hours / 24);
  return `il y a ${days} j`;
}

const LIVE_REFRESH_MS = 4000;

export function ActivityTimeline() {
  const { data, isLoading, isError, refetch } = useListActivities(
    { limit: 20 },
    { query: { refetchInterval: LIVE_REFRESH_MS, refetchIntervalInBackground: true } },
  );

  const items = data?.items ?? [];

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
          <History className="h-4 w-4 text-slate-500" />
          Activité récente
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isError ? (
          <div className="p-4">
            <ErrorState message="Impossible de charger l'activité." onRetry={() => { void refetch(); }} />
          </div>
        ) : isLoading ? (
          <div className="p-4">
            <TableSkeleton rows={5} cols={2} />
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Aucune activité pour le moment.
          </div>
        ) : (
          <div className="divide-y divide-border max-h-96 overflow-auto">
            {items.map((item: ActivityFeedEntry) => {
              const config = TYPE_CONFIG[item.type] ?? {
                label: item.type.replace(/_/g, ' '),
                icon: CircleDot,
                className: 'text-slate-600 bg-slate-100',
              };
              const Icon = config.icon;
              return (
                <div key={item.id} className="flex items-start gap-3 px-4 py-2.5">
                  <div className={`rounded-full p-1.5 shrink-0 ${config.className}`}>
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-foreground truncate">
                        {config.label}
                        {' — '}
                        <Link href={`/leads/${item.lead_id}`} className="hover:text-primary hover:underline">
                          {item.lead_name}
                        </Link>
                      </p>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {timeAgo(item.created_at)}
                      </span>
                    </div>
                    {item.details && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">{item.details}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
