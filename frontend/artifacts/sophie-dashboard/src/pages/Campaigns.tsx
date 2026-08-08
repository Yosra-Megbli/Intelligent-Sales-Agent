import { useState } from 'react';
import { Link } from 'wouter';
import {
  useListCampaigns, useCreateCampaign, useStartCampaign, usePauseCampaign, useResumeCampaign,
} from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Play, Pause, RotateCcw, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState } from '@/components/ErrorState';
import { CardSkeleton } from '@/components/LoadingState';
import { toast } from 'sonner';

function fmt(d: string) {
  return new Date(d).toLocaleDateString('fr-FR');
}

export default function Campaigns() {
  const qc = useQueryClient();
  const [newName, setNewName] = useState('');
  const [targetRegion, setTargetRegion] = useState<string>('');
  const [channel, setChannel] = useState<string>('WHATSAPP');
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useListCampaigns({ limit: 50, offset: 0 });

  const createMut = useCreateCampaign();
  const startMut  = useStartCampaign();
  const pauseMut  = usePauseCampaign();
  const resumeMut = useResumeCampaign();

  const trimmedName = newName.trim();
  const nameError =
    trimmedName.length === 0 ? null :
    trimmedName.length < 3 ? 'Le nom doit contenir au moins 3 caractères.' :
    trimmedName.length > 120 ? 'Le nom ne peut pas dépasser 120 caractères.' : null;
  const canCreate = trimmedName.length >= 3 && trimmedName.length <= 120;

  function invalidate() {
    void qc.invalidateQueries({ queryKey: ['listCampaigns'] });
  }

  async function handleCreate() {
    if (!canCreate) return;
    try {
      await createMut.mutateAsync({
        data: {
          name: newName.trim(),
          target_rules: targetRegion ? { region: targetRegion } : null,
          channel,
        },
      });
      toast.success('Campagne créée');
      setDialogOpen(false);
      setNewName('');
      setTargetRegion('');
      setChannel('WHATSAPP');
      invalidate();
    } catch {
      toast.error('Erreur lors de la création');
    }
  }

  async function handleStart(id: string) {
    try {
      await startMut.mutateAsync({ campaignId: id });
      toast.success('Campagne démarrée');
      invalidate();
    } catch {
      toast.error('Impossible de démarrer la campagne');
    }
  }

  async function handlePause(id: string) {
    try {
      await pauseMut.mutateAsync({ campaignId: id });
      toast.success('Campagne mise en pause');
      invalidate();
    } catch {
      toast.error('Impossible de mettre en pause');
    }
  }

  async function handleResume(id: string) {
    try {
      await resumeMut.mutateAsync({ campaignId: id });
      toast.success('Campagne reprise');
      invalidate();
    } catch {
      toast.error('Impossible de reprendre la campagne');
    }
  }

  const campaigns = data?.items ?? [];

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Campagnes</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {campaigns.length > 0 ? `${data?.total ?? 0} campagnes` : 'Aucune campagne'}
            </p>
          </div>
          <Button onClick={() => setDialogOpen(true)} size="sm">
            <Plus className="h-4 w-4 mr-1.5" />
            Nouvelle campagne
          </Button>
        </div>

        {/* Content */}
        {isError ? (
          <ErrorState message="Impossible de charger les campagnes." onRetry={() => void refetch()} />
        ) : isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <div className="flex flex-col items-center py-20 text-muted-foreground gap-3">
            <div className="rounded-full bg-muted p-5">
              <Users className="h-8 w-8" />
            </div>
            <p className="text-lg font-medium text-foreground">Aucune campagne</p>
            <p className="text-sm">Créez votre première campagne pour commencer.</p>
            <Button onClick={() => setDialogOpen(true)} size="sm" className="mt-2">
              <Plus className="h-4 w-4 mr-1.5" />
              Nouvelle campagne
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {campaigns.map((camp) => {
              const sent = camp.sent ?? 0;
              const total = camp.total_leads ?? 0;
              const progress = total > 0 ? Math.round((sent / total) * 100) : 0;
              const status = camp.status.toLowerCase();
              const barColor =
                status === 'running' ? 'bg-emerald-500' :
                status === 'paused'  ? 'bg-amber-500' :
                status === 'draft'   ? 'bg-slate-300' : 'bg-slate-400';

              return (
                <Card
                  key={camp.id}
                  className="relative overflow-hidden border shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all flex flex-col"
                >
                  <div className={`absolute inset-x-0 top-0 h-0.5 ${barColor}`} />
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">
                        <Link href={`/campaigns/${camp.id}`} className="hover:text-primary transition-colors">
                          {camp.name}
                        </Link>
                      </CardTitle>
                      <StatusBadge status={camp.status} className="shrink-0" />
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <p className="text-xs text-muted-foreground">
                        Créée le {fmt(camp.created_at)}
                      </p>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs font-medium text-muted-foreground">
                        {camp.channel === 'TELEGRAM' ? 'Telegram' : camp.channel === 'VOICE' ? 'Voix' : camp.channel === 'WEB' ? 'Web' : 'WhatsApp'}
                      </span>
                    </div>
                  </CardHeader>

                  <CardContent className="flex-1 space-y-3">
                    {/* Stats */}
                    <div className="flex gap-4 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground">Leads</p>
                        <p className="font-semibold tabular-nums">{total}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Envoyés</p>
                        <p className="font-semibold tabular-nums">{sent}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Progression</p>
                        <p className="font-semibold tabular-nums">{progress} %</p>
                      </div>
                    </div>

                    <Progress value={progress} className="h-1.5" />

                    {/* Actions */}
                    <div className="flex gap-2 pt-1">
                      {(status === 'draft' || status === 'paused') && (
                        <Button
                          size="sm"
                          variant="default"
                          className="flex-1 h-8"
                          disabled={startMut.isPending}
                          onClick={() => handleStart(camp.id)}
                        >
                          <Play className="h-3.5 w-3.5 mr-1" />
                          {status === 'paused' ? 'Reprendre' : 'Démarrer'}
                        </Button>
                      )}
                      {status === 'running' && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1 h-8"
                          disabled={pauseMut.isPending}
                          onClick={() => handlePause(camp.id)}
                        >
                          <Pause className="h-3.5 w-3.5 mr-1" />
                          Pause
                        </Button>
                      )}
                      <Link href={`/campaigns/${camp.id}`} className="inline-flex">
                        <Button size="sm" variant="ghost" className="h-8 px-2" asChild>
                          <span><RotateCcw className="h-3.5 w-3.5" /></span>
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Create dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouvelle campagne</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <label className="text-sm font-medium text-foreground" htmlFor="camp-name">
              Nom de la campagne
            </label>
            <Input
              id="camp-name"
              className="mt-1.5"
              placeholder="Ex : Campagne Île-de-France Mai 2025"
              value={newName}
              maxLength={120}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              aria-invalid={Boolean(nameError)}
            />
            {nameError && <p className="text-xs text-destructive mt-1">{nameError}</p>}
          </div>
          <div className="py-2">
            <label className="text-sm font-medium text-foreground" htmlFor="camp-region">
              Région ciblée (optionnel)
            </label>
            <Select value={targetRegion} onValueChange={setTargetRegion}>
              <SelectTrigger id="camp-region" className="mt-1.5">
                <SelectValue placeholder="Toutes les régions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Wallonie">Wallonie</SelectItem>
                <SelectItem value="Flandre">Flandre</SelectItem>
                <SelectItem value="Bruxelles">Bruxelles</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="py-2">
            <label className="text-sm font-medium text-foreground" htmlFor="camp-channel">
              Canal
            </label>
            <Select value={channel} onValueChange={setChannel}>
              <SelectTrigger id="camp-channel" className="mt-1.5">
                <SelectValue placeholder="Choisir un canal" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="WHATSAPP">WhatsApp</SelectItem>
                <SelectItem value="TELEGRAM">Telegram</SelectItem>
              </SelectContent>
            </Select>
            {channel === 'TELEGRAM' && (
              <p className="text-xs text-muted-foreground mt-1.5">
                Telegram ne permet pas de contacter un lead à froid : seuls les leads
                ayant déjà démarré une conversation avec le bot recevront réellement le message.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setDialogOpen(false); setTargetRegion(''); setChannel('WHATSAPP'); }}
            >
              Annuler
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!canCreate || createMut.isPending}
            >
              {createMut.isPending ? 'Création…' : 'Créer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
