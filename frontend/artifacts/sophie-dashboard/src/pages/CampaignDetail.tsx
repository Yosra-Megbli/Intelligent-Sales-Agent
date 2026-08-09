import { useState } from 'react';
import { Link, useLocation } from 'wouter';
import {
  useGetCampaign, useGetCampaignAnalytics,
  useStartCampaign, usePauseCampaign, useResumeCampaign,
  useUpdateCampaign, useDeleteCampaign,
} from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Play, Pause, Pencil, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  ResponsiveContainer, FunnelChart, Funnel, LabelList, Tooltip,
} from 'recharts';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';

function fmt(d: string) {
  return new Date(d).toLocaleDateString('fr-FR');
}

function leadName(lead: { first_name?: string | null; last_name?: string | null; phone?: string | null }) {
  return [lead.first_name, lead.last_name].filter(Boolean).join(' ') || lead.phone || '—';
}

const FUNNEL_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--destructive))',
];

interface Props {
  campaignId: string;
}

export default function CampaignDetail({ campaignId }: Props) {
  const qc = useQueryClient();
  const [, navigate] = useLocation();
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: campData, isLoading: campLoading, isError: campError, refetch } = useGetCampaign(campaignId);
  const { data: analytics, isLoading: anlLoading } = useGetCampaignAnalytics(campaignId);

  const startMut  = useStartCampaign();
  const pauseMut  = usePauseCampaign();
  const resumeMut = useResumeCampaign();
  const updateMut = useUpdateCampaign();
  const deleteMut = useDeleteCampaign();

  function invalidate() {
    void qc.invalidateQueries({ queryKey: ['getCampaign', campaignId] });
    void qc.invalidateQueries({ queryKey: ['listCampaigns'] });
  }

  async function handleRename() {
    if (!renameValue.trim()) return;
    try {
      await updateMut.mutateAsync({ campaignId, data: { name: renameValue.trim() } });
      toast.success('Campagne renommée');
      setRenameOpen(false);
      invalidate();
    } catch {
      toast.error('Le renommage a échoué');
    }
  }

  async function handleDelete() {
    try {
      await deleteMut.mutateAsync({ campaignId });
      toast.success('Campagne supprimée');
      void qc.invalidateQueries({ queryKey: ['listCampaigns'] });
      navigate('/campaigns');
    } catch {
      toast.error("La suppression a échoué (une campagne EN COURS doit d'abord être mise en pause).");
    }
  }

  async function handleStart() {
    try {
      await startMut.mutateAsync({ campaignId });
      toast.success('Campagne démarrée');
      invalidate();
    } catch { toast.error('Erreur'); }
  }
  async function handlePause() {
    try {
      await pauseMut.mutateAsync({ campaignId });
      toast.success('Campagne mise en pause');
      invalidate();
    } catch { toast.error('Erreur'); }
  }
  async function handleResume() {
    try {
      await resumeMut.mutateAsync({ campaignId });
      toast.success('Campagne reprise');
      invalidate();
    } catch { toast.error('Erreur'); }
  }

  if (campLoading) {
    return (
      <div className="flex-1 overflow-auto p-6 max-w-5xl mx-auto space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (campError || !campData) {
    return (
      <div className="flex-1 overflow-auto p-6">
        <Link href="/campaigns" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4 gap-1">
          <ArrowLeft className="h-4 w-4" /> Retour aux campagnes
        </Link>
        <ErrorState message="Impossible de charger cette campagne." onRetry={() => void refetch()} />
      </div>
    );
  }

  const { campaign, leads } = campData;

  const funnelData = analytics
    ? [
        { name: 'Total',    value: analytics.total,     fill: FUNNEL_COLORS[0] },
        { name: 'Contactés', value: analytics.contacted, fill: FUNNEL_COLORS[1] },
        { name: 'Répondu',  value: analytics.replied,   fill: FUNNEL_COLORS[2] },
        { name: 'Qualifiés', value: analytics.qualified, fill: FUNNEL_COLORS[3] },
        { name: 'Rejetés',  value: analytics.rejected,  fill: FUNNEL_COLORS[4] },
      ].filter((d) => d.value > 0)
    : [];

  const progress =
    campaign.total_leads > 0
      ? Math.round((campaign.sent / campaign.total_leads) * 100)
      : 0;

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-5xl mx-auto space-y-5">
        {/* Back */}
        <Link href="/campaigns" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground gap-1">
          <ArrowLeft className="h-4 w-4" /> Retour aux campagnes
        </Link>

        {/* Header card */}
        <Card className="border shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <h1 className="text-xl font-bold text-foreground tracking-tight">{campaign.name}</h1>
                <div className="flex items-center gap-2 mt-1.5">
                  <StatusBadge status={campaign.status} />
                  <span className="text-xs text-muted-foreground">
                    Créée le {fmt(campaign.created_at)}
                  </span>
                  <span className="text-xs text-muted-foreground">·</span>
                  <span className="text-xs font-medium text-muted-foreground">
                    {campaign.channel === 'TELEGRAM' ? 'Telegram' : campaign.channel === 'VOICE' ? 'Voix' : campaign.channel === 'WEB' ? 'Web' : 'WhatsApp'}
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                {(campaign.status.toLowerCase() === 'draft') && (
                  <Button size="sm" onClick={handleStart} disabled={startMut.isPending}>
                    <Play className="h-4 w-4 mr-1" /> Démarrer
                  </Button>
                )}
                {campaign.status.toLowerCase() === 'paused' && (
                  <Button size="sm" onClick={handleResume} disabled={resumeMut.isPending}>
                    <Play className="h-4 w-4 mr-1" /> Reprendre
                  </Button>
                )}
                {campaign.status.toLowerCase() === 'running' && (
                  <Button size="sm" variant="outline" onClick={handlePause} disabled={pauseMut.isPending}>
                    <Pause className="h-4 w-4 mr-1" /> Pause
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => { setRenameValue(campaign.name); setRenameOpen(true); }}
                >
                  <Pencil className="h-4 w-4 mr-1" /> Renommer
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive"
                  disabled={campaign.status.toLowerCase() === 'running'}
                  title={campaign.status.toLowerCase() === 'running' ? 'Mettez en pause avant de supprimer' : undefined}
                  onClick={() => setDeleteOpen(true)}
                >
                  <Trash2 className="h-4 w-4 mr-1" /> Supprimer
                </Button>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
              <div className="rounded-lg bg-muted/40 p-3">
                <p className="text-xs text-muted-foreground">Total leads</p>
                <p className="text-2xl font-bold mt-0.5 tabular-nums">{campaign.total_leads}</p>
              </div>
              <div className="rounded-lg bg-muted/40 p-3">
                <p className="text-xs text-muted-foreground">Envoyés</p>
                <p className="text-2xl font-bold mt-0.5 tabular-nums">{campaign.sent}</p>
              </div>
              <div className="rounded-lg bg-muted/40 p-3">
                <p className="text-xs text-muted-foreground">Progression</p>
                <p className="text-2xl font-bold mt-0.5 tabular-nums">{progress} %</p>
              </div>
            </div>

            <Progress value={progress} className="mt-3 h-2" />
          </CardContent>
        </Card>

        {/* Analytics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="border shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Entonnoir de conversion</CardTitle>
            </CardHeader>
            <CardContent>
              {anlLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : funnelData.length === 0 ? (
                <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
                  Aucune donnée analytique
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <FunnelChart>
                    <Tooltip
                      contentStyle={{ fontSize: 12, borderRadius: 6 }}
                      formatter={(v, n) => [v, n]}
                    />
                    <Funnel
                      dataKey="value"
                      data={funnelData}
                      isAnimationActive
                    >
                      <LabelList position="center" fill="#fff" fontSize={12} dataKey="name" />
                    </Funnel>
                  </FunnelChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <Card className="border shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Taux clés</CardTitle>
            </CardHeader>
            <CardContent>
              {anlLoading ? (
                <div className="space-y-3">
                  {[1,2,3,4].map(i => <Skeleton key={i} className="h-12" />)}
                </div>
              ) : !analytics ? (
                <div className="text-sm text-muted-foreground">Aucune donnée</div>
              ) : (
                <div className="space-y-3">
                  {[
                    { label: 'Taux de réponse',       value: analytics.response_rate,      color: 'bg-blue-500' },
                    { label: 'Taux de qualification',  value: analytics.qualification_rate, color: 'bg-emerald-500' },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-muted-foreground">{label}</span>
                        {/* response_rate / qualification_rate arrive déjà en 0-100 depuis le
                            backend (application/campaign_service.py: `(replied / contacted * 100)`),
                            donc PAS de *100 ici - sinon on affiche 4520% au lieu de 45.2%. */}
                        <span className="font-semibold">{value.toFixed(1)} %</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${color}`}
                          style={{ width: `${Math.min(value, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}

                  <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                    {[
                      { label: 'Contactés',  value: analytics.contacted },
                      { label: 'Qualifiés',  value: analytics.qualified },
                      { label: 'Transferts', value: analytics.handoff },
                    ].map(({ label, value }) => (
                      <div key={label} className="rounded-lg bg-muted/40 p-2">
                        <p className="text-lg font-bold">{value}</p>
                        <p className="text-xs text-muted-foreground">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Leads table */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">
              Leads de cette campagne ({campData.leads_total})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {leads.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                Aucun lead dans cette campagne
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40">
                      <TableHead>Nom</TableHead>
                      <TableHead>Téléphone</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="hidden sm:table-cell">Région</TableHead>
                      <TableHead className="text-right">Modifié</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {leads.map((lead) => (
                      <TableRow key={lead.id} className="hover:bg-muted/30">
                        <TableCell>
                          <Link href={`/leads/${lead.id}`} className="font-medium hover:text-primary">
                            {leadName(lead)}
                          </Link>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {lead.phone ?? '—'}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={lead.status} />
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                          {lead.region ?? '—'}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {fmt(lead.updated_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Renommer la campagne</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <Label htmlFor="rename-campaign">Nom</Label>
            <Input
              id="rename-campaign"
              className="mt-1.5"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleRename()}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>Annuler</Button>
            <Button onClick={() => void handleRename()} disabled={!renameValue.trim() || updateMut.isPending}>
              {updateMut.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette campagne ?</AlertDialogTitle>
            <AlertDialogDescription>
              "{campaign.name}" sera définitivement supprimée. Les leads qui lui étaient
              assignés ne sont pas supprimés — ils redeviennent disponibles pour une autre
              campagne. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void handleDelete()}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? 'Suppression…' : 'Supprimer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
