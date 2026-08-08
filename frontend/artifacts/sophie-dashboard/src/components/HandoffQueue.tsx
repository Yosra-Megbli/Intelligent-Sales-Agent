import { useListHandoffs } from '@workspace/api-client-react';
import { Link } from 'wouter';
import { UserCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingState';

function leadName(lead: { first_name?: string | null; last_name?: string | null; phone?: string | null }) {
  const n = [lead.first_name, lead.last_name].filter(Boolean).join(' ');
  return n || lead.phone || '—';
}

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.round(hours / 24);
  return `il y a ${days} j`;
}

// Human Handoff Queue (P04): every prospect Sophie has already qualified (or
// who explicitly asked for a person) and handed to the sales team - the
// "11 prospects waiting" number on the KPI card, but with names, phones and
// a View button so it's actionable instead of just a count.
export function HandoffQueue() {
  const { data, isLoading, isError, refetch } = useListHandoffs(
    { limit: 20, offset: 0 },
    { query: { refetchInterval: 4000, refetchIntervalInBackground: true } },
  );

  const items = data?.items ?? [];

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
          <UserCheck className="h-4 w-4 text-amber-600" />
          Transferts en attente
          {data && data.total > 0 && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-amber-100 text-amber-700 text-xs font-semibold">
              {data.total}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isError ? (
          <div className="p-4">
            <ErrorState message="Impossible de charger les transferts." onRetry={() => { void refetch(); }} />
          </div>
        ) : isLoading ? (
          <div className="p-4">
            <TableSkeleton rows={3} cols={4} />
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Aucun prospect en attente d'un commercial pour le moment.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((entry) => (
              <div
                key={entry.conversation_id}
                className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/40 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {leadName(entry.lead)}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {[entry.lead.phone, entry.lead.campaign_name].filter(Boolean).join(' · ') || '—'}
                  </p>
                  {entry.reason && (
                    <p className="text-xs text-amber-700 truncate mt-0.5">{entry.reason}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-muted-foreground hidden sm:block">
                    {timeAgo(entry.handoff_at)}
                  </span>
                  <Link href={`/leads/${entry.lead.id}`}>
                    <Button variant="outline" size="sm" asChild>
                      <span>Voir</span>
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
