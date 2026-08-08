import { useEffect, useState } from 'react';
import { useHealthCheck } from '@workspace/api-client-react';
import { Activity, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

type SignalStatus = 'ok' | 'error' | 'loading';

interface StatusWidgetProps {
  /** Database reachability, inferred from the Overview query's own
   * success/error state (no dedicated DB-health endpoint exists). */
  dbStatus: SignalStatus;
}

function Row({
  label,
  status,
  unmonitored,
}: {
  label: string;
  status?: SignalStatus;
  unmonitored?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      {unmonitored ? (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <HelpCircle className="h-3.5 w-3.5" />
          Non surveillé
        </span>
      ) : status === 'loading' ? (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-slate-300 animate-pulse" />
          Vérification…
        </span>
      ) : status === 'ok' ? (
        <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Opérationnel
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-xs font-medium text-red-600">
          <XCircle className="h-3.5 w-3.5" />
          Hors ligne
        </span>
      )}
    </div>
  );
}

const CHECK_INTERVAL_MS = 15000;

export function StatusWidget({ dbStatus }: StatusWidgetProps) {
  const { isSuccess, isError, isLoading, dataUpdatedAt } = useHealthCheck({
    query: { refetchInterval: CHECK_INTERVAL_MS, refetchIntervalInBackground: true },
  });
  const [lastChecked, setLastChecked] = useState<string>('—');

  const apiStatus: SignalStatus = isLoading ? 'loading' : isSuccess ? 'ok' : isError ? 'error' : 'loading';

  useEffect(() => {
    if (dataUpdatedAt) {
      setLastChecked(new Date(dataUpdatedAt).toLocaleTimeString('fr-FR'));
    }
  }, [dataUpdatedAt]);

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Activity className="h-4 w-4 text-slate-500" />
          État du système
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="divide-y divide-border">
          <Row label="API" status={apiStatus} />
          <Row label="Base de données" status={dbStatus} />
          <Row label="Assistant IA" unmonitored />
          <Row label="File d'attente" unmonitored />
        </div>
        <p className={cn('text-xs text-muted-foreground mt-2')}>
          Dernière vérification : {lastChecked}
        </p>
      </CardContent>
    </Card>
  );
}
