import { useState } from 'react';
import { useImportLeads } from '@workspace/api-client-react';
import { UserPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '@/components/ui/dialog';
import { toCsv } from '@/lib/csv';
import { REGIONS } from '@/lib/regions';
import { isValidEmail, isValidPhone } from '@/lib/validation';
import { toast } from 'sonner';

interface NewLeadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

const EMPTY_FORM = {
  name: '',
  phone: '',
  email: '',
  region: '',
  provider: '',
  notes: '',
};

// Columns the backend's importer actually reads onto the Lead model - see
// LeadImportService._extract_fields in backend/application/lead_import_service.py.
// `source` is intentionally left out: it's accepted as a CSV column but never
// mapped onto the Lead (every imported lead gets source=CSV), so exposing a
// "source" field here would promise something the backend doesn't do.
const CSV_COLUMNS = ['name', 'phone', 'email', 'region', 'provider', 'notes'];

/**
 * "Nouveau Lead" - manual single-lead creation. There is no
 * POST /api/leads (single-create) endpoint in the backend, only bulk CSV
 * import (`POST /api/leads/import`, already wired via `useImportLeads` in
 * ImportLeadsDialog). Rather than adding a new backend route, this builds a
 * one-row CSV from the form and reuses that exact same, already-tested path -
 * so the same dedup/validation guarantees apply to a manually-entered lead
 * as to an imported one.
 */
export function NewLeadDialog({ open, onOpenChange, onCreated }: NewLeadDialogProps) {
  const [form, setForm] = useState(EMPTY_FORM);
  const importMut = useImportLeads();

  function set<K extends keyof typeof EMPTY_FORM>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function reset() {
    setForm(EMPTY_FORM);
  }

  function handleClose(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  const hasIdentifier = form.email.trim() !== '' || form.phone.trim() !== '';
  const emailError = form.email.trim() !== '' && !isValidEmail(form.email) ? 'Email invalide.' : null;
  const phoneError = form.phone.trim() !== '' && !isValidPhone(form.phone) ? 'Téléphone invalide.' : null;
  const canSubmit = hasIdentifier && !emailError && !phoneError;

  async function handleSubmit() {
    if (!canSubmit) {
      toast.error(hasIdentifier ? 'Corrigez les champs invalides.' : 'Un email ou un téléphone est requis.');
      return;
    }
    const csvText = toCsv([form], CSV_COLUMNS);
    try {
      const result = await importMut.mutateAsync({ data: { csv_text: csvText } });
      if (result.created > 0) {
        toast.success('Lead créé avec succès.');
      } else if (result.updated > 0 || result.duplicates > 0) {
        toast.info('Un lead avec cet email/téléphone existait déjà — informations mises à jour.');
      } else if (result.skipped > 0 || result.errors > 0) {
        toast.error("Le lead n'a pas pu être créé.");
        return;
      }
      onCreated();
      handleClose(false);
    } catch {
      toast.error('La création du lead a échoué.');
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-4 w-4" />
            Nouveau lead
          </DialogTitle>
          <DialogDescription>
            Un email ou un numéro de téléphone est requis pour identifier le lead.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5 col-span-2">
              <Label htmlFor="lead-name">Nom complet</Label>
              <Input
                id="lead-name"
                placeholder="Jean Dupont"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-phone">Téléphone</Label>
              <Input
                id="lead-phone"
                placeholder="+33 6 12 34 56 78"
                value={form.phone}
                onChange={(e) => set('phone', e.target.value)}
                aria-invalid={Boolean(phoneError)}
              />
              {phoneError && <p className="text-xs text-destructive">{phoneError}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-email">Email</Label>
              <Input
                id="lead-email"
                type="email"
                placeholder="jean@exemple.com"
                value={form.email}
                onChange={(e) => set('email', e.target.value)}
                aria-invalid={Boolean(emailError)}
              />
              {emailError && <p className="text-xs text-destructive">{emailError}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-region">Région</Label>
              <Select value={form.region || undefined} onValueChange={(val) => set('region', val)}>
                <SelectTrigger id="lead-region">
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
              <Label htmlFor="lead-provider">Fournisseur actuel</Label>
              <Input
                id="lead-provider"
                placeholder="—"
                value={form.provider}
                onChange={(e) => set('provider', e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="lead-notes">Notes</Label>
            <Textarea
              id="lead-notes"
              placeholder="Contexte, remarques…"
              value={form.notes}
              onChange={(e) => set('notes', e.target.value)}
              className="min-h-20"
            />
          </div>
          {!hasIdentifier && (form.name || form.region || form.notes) && (
            <p className="text-xs text-amber-600">
              Ajoutez un email ou un téléphone pour pouvoir enregistrer ce lead.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleClose(false)}>Annuler</Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || importMut.isPending}>
            {importMut.isPending ? 'Création…' : 'Créer le lead'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
