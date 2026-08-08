import { useGetOverview, useGetStats, useListLeads } from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Users, MessageCircle, Megaphone, CheckCircle2, XCircle, TrendingUp,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { KpiCard } from '@/components/KpiCard';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState } from '@/components/ErrorState';
import { KpiSkeleton, TableSkeleton } from '@/components/LoadingState';
import { HandoffQueue } from '@/components/HandoffQueue';
import { QuickActions } from '@/components/QuickActions';
import { StatusWidget } from '@/components/StatusWidget';
import { ActivityTimeline } from '@/components/ActivityTimeline';

const STATUS_COLORS: Record<string, string> = {
  new: 'hsl(var(--muted-foreground))',
  contacted: 'hsl(var(--chart-4))',
  replied: 'hsl(var(--chart-2))',
  qualified: 'hsl(var(--primary))',
  rejected: 'hsl(var(--destructive))',
  human_handoff: 'hsl(var(--chart-3))',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacté',
  replied: 'A répondu',
  qualified: 'Qualifié',
  rejected: 'Rejeté',
  human_handoff: 'Transfert',
};

function fmt(d: string) {
  return new Date(d).toLocaleDateString('fr-FR');
}

function leadName(lead: { first_name?: string | null; last_name?: string | null; phone?: string | null }) {
  const n = [lead.first_name, lead.last_name].filter(Boolean).join(' ');
  return n || lead.phone || '—';
}

// Poll interval for live demo mode: numbers move on their own, no manual refresh needed.
const LIVE_REFRESH_MS = 4000;

export default function Dashboard() {
  const qc = useQueryClient();

  const {
    data: overview,
    isLoading: ovLoading,
    isError: ovError,
    refetch: ovRefetch,
    dataUpdatedAt: overviewUpdatedAt,
  } = useGetOverview({
    query: {
      refetchInterval: LIVE_REFRESH_MS,
      refetchIntervalInBackground: true,
    },
  });

  const lastOverviewUpdate = overviewUpdatedAt
    ? new Date(overviewUpdatedAt).toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '—';

  const {
    data: stats,
    isLoading: stLoading,
    isError: stError,
  } = useGetStats({
    query: {
      refetchInterval: LIVE_REFRESH_MS,
      refetchIntervalInBackground: true,
    },
  });

  const {
    data: recentLeads,
    isLoading: llLoading,
    isError: llError,
  } = useListLeads(
    { limit: 10, offset: 0 },
    {
      query: {
        refetchInterval: LIVE_REFRESH_MS,
        refetchIntervalInBackground: true,
      },
    },
  );

  const chartData = stats?.by_status
    ? Object.entries(stats.by_status).map(([k, v]) => ({
        name: STATUS_LABELS[k] ?? k,
        count: v,
        key: k,
      }))
    : [];

  const rejectionRate =
    overview && overview.total_leads > 0
      ? ((overview.rejected / overview.total_leads) * 100).toFixed(1)
      : '0.0';

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Vue d'ensemble</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Tableau de bord Sophie — activité en temps réel
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            En direct · mis à jour à {lastOverviewUpdate}
          </div>
        </div>

        {/* Quick Actions */}
        <QuickActions onDataChanged={() => void qc.invalidateQueries()} />

        {/* KPIs */}
        {ovError ? (
          <ErrorState
            message="Impossible de charger les KPIs."
            onRetry={() => { void qc.invalidateQueries(); }}
          />
        ) : ovLoading ? (
          <KpiSkeleton />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            <KpiCard
              title="Total Leads"
              value={overview?.total_leads}
              icon={Users}
              accent="slate"
            />
            <KpiCard
              title="Conversations actives"
              value={overview?.active_conversations}
              icon={MessageCircle}
              accent="blue"
            />
            <KpiCard
              title="Campagnes actives"
              value={overview?.active_campaigns}
              icon={Megaphone}
              accent="green"
            />
            <KpiCard
              title="Leads qualifiés"
              value={overview?.qualified}
              subtitle={`sur ${overview?.contacted ?? 0} contactés`}
              icon={CheckCircle2}
              accent="green"
            />
            <KpiCard
              title="Taux de rejet"
              value={`${rejectionRate} %`}
              subtitle={`${overview?.rejected ?? 0} leads rejetés`}
              icon={XCircle}
              accent="red"
            />
            <KpiCard
              title="Taux de conversion"
              value={`${((overview?.conversion_rate ?? 0) * 100).toFixed(1)} %`}
              subtitle="qualification / contactés"
              icon={TrendingUp}
              accent="amber"
            />
          </div>
        )}

        {/* Human Handoff Queue (P04) - who Simon's sales team needs to call, not just how many */}
        <HandoffQueue />

        {/* Chart + recent leads */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Status chart */}
          <Card className="border shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-foreground">
                Leads par statut
              </CardTitle>
            </CardHeader>
            <CardContent>
              {stLoading ? (
                <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                  Chargement…
                </div>
              ) : stError ? (
                <ErrorState message="Erreur chargement stats." />
              ) : chartData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                  Aucune donnée
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                      <Tooltip
                        cursor={{ fill: 'rgba(0,0,0,0.04)' }}
                        contentStyle={{ fontSize: 12, borderRadius: 6 }}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {chartData.map((entry) => (
                          <Cell
                            key={entry.key}
                            fill={STATUS_COLORS[entry.key] ?? 'hsl(var(--muted-foreground))'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {chartData.map((entry) => (
                      <div
                        key={entry.key}
                        className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/70 px-2 py-1 text-xs text-muted-foreground"
                      >
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: STATUS_COLORS[entry.key] ?? 'hsl(var(--muted-foreground))' }}
                        />
                        {entry.name}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Recent leads */}
          <Card className="border shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-foreground">
                Leads récents
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {llLoading ? (
                <div className="p-4">
                  <TableSkeleton rows={5} cols={3} />
                </div>
              ) : llError ? (
                <div className="p-4">
                  <ErrorState message="Erreur chargement leads." />
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {(recentLeads?.items ?? []).slice(0, 8).map((lead) => (
                    <div
                      key={lead.id}
                      className="flex items-center justify-between px-4 py-2.5 hover:bg-muted/40 transition-colors"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {leadName(lead)}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">
                          {lead.region ?? lead.source ?? '—'}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        <StatusBadge status={lead.status} />
                        <span className="text-xs text-muted-foreground hidden sm:block">
                          {fmt(lead.updated_at)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {(recentLeads?.items ?? []).length === 0 && (
                    <div className="px-4 py-10 text-center">
                      <Users className="mx-auto h-8 w-8 text-muted-foreground/40" />
                      <p className="mt-2 text-sm font-medium text-foreground">Aucun lead pour l'instant</p>
                      <p className="mt-1 text-xs text-muted-foreground">Importez ou ajoutez un lead pour commencer.</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Activity Timeline + System status */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ActivityTimeline />
          <StatusWidget dbStatus={ovError ? 'error' : ovLoading ? 'loading' : 'ok'} />
        </div>
      </div>
    </div>
  );
}
