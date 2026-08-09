import { useEffect, useState } from 'react';
import { useUpdateLead } from '@workspace/api-client-react';
import type { Lead } from '@workspace/api-client-react';
import { Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { REGIONS } from '@/lib/regions';
import { isValidEmail, isValidPhone } from '@/lib/validation';
import { toast } from 'sonner';

interface EditLeadDialogProps {
  lead: Lead;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

function formFromLead(lead: Lead) {
  return {
    first_name: lead.first_name ?? '',
    last_name: lead.last_name ?? '',
    phone: lead.phone ?? '',
    email: lead.email ?? '',
    telegram_chat_id: lead.telegram_chat_id ?? '',
    region: lead.region ?? '',
    current_supplier: lead.current_supplier ?? '',
    notes: lead.notes ?? '',
  };
}

/**
 * "Modifier le lead" - CRM field correction only. Deliberately cannot touch
 * status/qualification_score/campaign_id - those are Engine-owned (see
 * backend/application/lead_service.py's _EDITABLE_FIELDS, enforced
 * server-side too, not just by this form omitting the fields).
 */
export function EditLeadDialog({ lead, open, onOpenChange, onSaved }: EditLeadDialogProps) {
  const [form, setForm] = useState(formFromLead(lead));
  const updateMut = useUpdateLead();

  // Re-sync when a different lead is opened, or its data refetches.
  useEffect(() => {
    if (open) setForm(formFromLead(lead));
  }, [open, lead]);

  function set<K extends keyof ReturnType<typeof formFromLead>>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  const emailError = form.email.trim() !== '' && !isValidEmail(form.email) ? 'Email invalide.' : null;
  const phoneError = form.phone.trim() !== '' && !isValidPhone(form.phone) ? 'Téléphone invalide.' : null;
  const canSubmit = !emailError && !phoneError;

  async function handleSave() {
    if (!canSubmit) {
      toast.error('Corrigez les champs invalides.');
      return;
    }
    try {
      await updateMut.mutateAsync({
        leadId: lead.id,
        data: {
          first_name: form.first_name.trim() || null,
          last_name: form.last_name.trim() || null,
          phone: form.phone.trim() || null,
          email: form.email.trim() || null,
          telegram_chat_id: form.telegram_chat_id.trim() || null,
          region: form.region.trim() || null,
          current_supplier: form.current_supplier.trim() || null,
          notes: form.notes.trim() || null,
        },
      });
      toast.success('Lead mis à jour.');
      onSaved();
      onOpenChange(false);
    } catch {
      toast.error('La mise à jour a échoué.');
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="h-4 w-4" />
            Modifier le lead
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="edit-first-name">Prénom</Label>
              <Input id="edit-first-name" value={form.first_name} onChange={(e) => set('first_name', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-last-name">Nom</Label>
              <Input id="edit-last-name" value={form.last_name} onChange={(e) => set('last_name', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-phone">Téléphone</Label>
              <Input
                id="edit-phone"
                value={form.phone}
                onChange={(e) => set('phone', e.target.value)}
                aria-invalid={Boolean(phoneError)}
              />
              {phoneError && <p className="text-xs text-destructive">{phoneError}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-email">Email</Label>
              <Input
                id="edit-email"
                type="email"
                value={form.email}
                onChange={(e) => set('email', e.target.value)}
                aria-invalid={Boolean(emailError)}
              />
              {emailError && <p className="text-xs text-destructive">{emailError}</p>}
            </div>
            <div className="space-y-1.5 col-span-2">
              <Label htmlFor="edit-telegram">Chat ID Telegram</Label>
              <Input
                id="edit-telegram"
                value={form.telegram_chat_id}
                onChange={(e) => set('telegram_chat_id', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-region">Région</Label>
              <Select value={form.region || undefined} onValueChange={(val) => set('region', val)}>
                <SelectTrigger id="edit-region">
                  <SelectValue placeholder="Non spécifiée" />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-supplier">Fournisseur actuel</Label>
              <Input
                id="edit-supplier"
                value={form.current_supplier}
                onChange={(e) => set('current_supplier', e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-notes">Notes</Label>
            <Textarea
              id="edit-notes"
              value={form.notes}
              onChange={(e) => set('notes', e.target.value)}
              className="min-h-20"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button onClick={handleSave} disabled={!canSubmit || updateMut.isPending}>
            {updateMut.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
