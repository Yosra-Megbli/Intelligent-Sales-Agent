import { useState } from 'react';
import { Link, useLocation } from 'wouter';
import { useGetLeadDetail, useDeleteLead } from '@workspace/api-client-react';
import { ArrowLeft, Phone, Mail, Send, MapPin, Briefcase, Zap, Calendar, Clock, Pencil, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import { EditLeadDialog } from '@/components/EditLeadDialog';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

// Audit finding #8 (Conversation content): the dashboard used to show only
// conversation metadata (channel/state/timestamps), never what was actually
// said. `role` mirrors backend `MessageRole` (USER/ASSISTANT/SYSTEM).
function messageBubbleClasses(role: string) {
  if (role === 'USER') {
    return 'bg-primary text-primary-foreground ml-auto rounded-br-sm';
  }
  if (role === 'SYSTEM') {
    return 'bg-destructive/10 text-destructive text-xs mx-auto';
  }
  return 'bg-muted text-foreground mr-auto rounded-bl-sm';
}

function fmtTime(d: string) {
  return new Date(d).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function fmt(d?: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function ScoreBadge({ score }: { score?: number | null }) {
  if (score == null) return <span className="text-muted-foreground">—</span>;
  const color =
    score >= 70 ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' :
    score >= 40 ? 'bg-amber-50 text-amber-700 ring-amber-200' :
                  'bg-red-50 text-red-700 ring-red-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-bold ring-1 tabular-nums ${color}`}>
      {score}<span className="font-normal opacity-70">/100</span>
    </span>
  );
}

interface Props {
  leadId: string;
}

export default function LeadDetail({ leadId }: Props) {
  const { data, isLoading, isError, refetch } = useGetLeadDetail(leadId);
  const [, navigate] = useLocation();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteMut = useDeleteLead();

  async function handleDelete() {
    try {
      await deleteMut.mutateAsync({ leadId });
      toast.success('Lead supprimé.');
      navigate('/leads');
    } catch {
      toast.error('La suppression a échoué.');
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 overflow-auto">
        <div className="p-6 max-w-4xl mx-auto space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex-1 overflow-auto p-6">
        <Link href="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4 mr-1" /> Retour aux leads
        </Link>
        <ErrorState message="Impossible de charger ce lead." onRetry={() => void refetch()} />
      </div>
    );
  }

  const { lead, conversations, activities } = data;
  const fullName = [lead.first_name, lead.last_name].filter(Boolean).join(' ') || lead.phone || 'Lead';

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-4xl mx-auto space-y-5">
        {/* Back */}
        <Link href="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground gap-1">
          <ArrowLeft className="h-4 w-4" /> Retour aux leads
        </Link>

        {/* Lead card */}
        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-semibold shrink-0">
                  {fullName.slice(0, 1).toUpperCase()}
                </div>
                <div>
                  <CardTitle className="text-xl tracking-tight">{fullName}</CardTitle>
                  <p className="text-sm text-muted-foreground mt-0.5">ID: {lead.id}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <ScoreBadge score={lead.qualification_score} />
                <StatusBadge status={lead.status} />
                <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                  <Pencil className="h-3.5 w-3.5 mr-1.5" />
                  Modifier
                </Button>
                <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteOpen(true)}>
                  <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  Supprimer
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { icon: Phone,    label: 'Téléphone',       value: lead.phone },
                { icon: Mail,     label: 'Email',           value: lead.email },
                { icon: Send,     label: 'Chat ID Telegram', value: lead.telegram_chat_id },
                { icon: MapPin,   label: 'Région / Ville',  value: [lead.region, lead.city].filter(Boolean).join(', ') || null },
                { icon: Briefcase,label: 'Fournisseur',     value: lead.current_supplier },
                { icon: Zap,      label: 'Type client',     value: lead.customer_type },
                { icon: Clock,    label: 'Dernier contact', value: lead.last_contact_date ? fmt(lead.last_contact_date) : null },
                { icon: Calendar, label: 'Prochain RDV',    value: fmt(lead.next_follow_up_date) },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-start gap-3">
                  <div className="rounded-md bg-muted p-2 shrink-0">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-sm font-medium text-foreground">{value || '—'}</p>
                  </div>
                </div>
              ))}
            </div>

            {lead.notes && (
              <div className="mt-4 rounded-lg bg-muted/50 border p-3">
                <p className="text-xs font-medium text-muted-foreground mb-1">Notes</p>
                <p className="text-sm text-foreground whitespace-pre-wrap">{lead.notes}</p>
              </div>
            )}

            {lead.rejection_reason && (
              <div className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-xs font-medium text-red-600 mb-1">Motif de rejet</p>
                <p className="text-sm text-red-700">{lead.rejection_reason}</p>
              </div>
            )}

            <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs text-muted-foreground">
              <div><span className="font-medium">Source :</span> {lead.source}</div>
              <div><span className="font-medium">Canal :</span> {lead.provider ?? '—'}</div>
              <div><span className="font-medium">Campagne :</span> {lead.campaign_name ?? '—'}</div>
              <div><span className="font-medium">Créé :</span> {fmt(lead.created_at)}</div>
              <div><span className="font-medium">Modifié :</span> {fmt(lead.updated_at)}</div>
            </div>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs defaultValue="conversations">
          <TabsList>
            <TabsTrigger value="conversations">
              Conversations ({conversations.length})
            </TabsTrigger>
            <TabsTrigger value="activity">
              Activité ({activities.length})
            </TabsTrigger>
          </TabsList>

          {/* Conversations */}
          <TabsContent value="conversations" className="mt-4">
            {conversations.length === 0 ? (
              <div className="rounded-lg border bg-muted/20 py-10 text-center text-sm text-muted-foreground">
                Aucune conversation enregistrée
              </div>
            ) : (
              <div className="space-y-3">
                {conversations.map((conv) => (
                  <Card key={conv.id} className="border shadow-none">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="capitalize">{conv.channel}</Badge>
                          <Badge variant="outline" className="capitalize text-xs">
                            {conv.current_state}
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          Dernier msg : {fmt(conv.last_message_at)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        Démarré le {fmt(conv.started_at)}
                      </p>

                      {/* Real message content — not just metadata (audit #8) */}
                      {conv.messages.length === 0 ? (
                        <p className="text-xs text-muted-foreground italic mt-3">
                          Aucun message échangé pour l'instant.
                        </p>
                      ) : (
                        <div className="mt-3 space-y-2 max-h-96 overflow-y-auto rounded-lg bg-muted/20 border p-3">
                          {conv.messages.map((msg) => (
                            <div
                              key={msg.id}
                              className={cn(
                                'max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap',
                                messageBubbleClasses(msg.role),
                              )}
                            >
                              <p>{msg.content}</p>
                              <p className="text-[10px] opacity-70 mt-1 text-right">
                                {fmtTime(msg.timestamp)}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Activity */}
          <TabsContent value="activity" className="mt-4">
            {activities.length === 0 ? (
              <div className="rounded-lg border bg-muted/20 py-10 text-center text-sm text-muted-foreground">
                Aucune activité enregistrée
              </div>
            ) : (
              <div className="relative border-l-2 border-border ml-3 pl-5 space-y-4">
                {activities.map((act) => (
                  <div key={act.id} className="relative">
                    <div className="absolute -left-[1.6rem] top-1 w-3 h-3 rounded-full bg-primary border-2 border-background" />
                    <div className="bg-card border rounded-lg p-3">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="secondary" className="text-xs capitalize">
                          {act.type.replace(/_/g, ' ')}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{fmt(act.created_at)}</span>
                      </div>
                      {act.details && (
                        <p className="text-sm text-muted-foreground mt-1">{act.details}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <EditLeadDialog lead={lead} open={editOpen} onOpenChange={setEditOpen} onSaved={() => void refetch()} />

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce lead ?</AlertDialogTitle>
            <AlertDialogDescription>
              {fullName} sera définitivement supprimé, ainsi que ses conversations, messages et
              son historique d'activité. Cette action est irréversible.
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
