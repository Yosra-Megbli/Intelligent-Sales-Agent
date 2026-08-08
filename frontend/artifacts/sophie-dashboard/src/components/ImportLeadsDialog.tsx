import { useRef, useState } from 'react';
import { usePreviewLeadImport, useImportLeads } from '@workspace/api-client-react';
import type { ImportPreview, ImportReport } from '@workspace/api-client-react';
import { Upload, FileText, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';

type Step = 'input' | 'preview' | 'done';

interface ImportLeadsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}

/**
 * Wires the existing backend CSV import flow (POST /api/leads/import/preview
 * then POST /api/leads/import - see backend/api/leads_routes.py) into the
 * React dashboard. Previously this endpoint had no UI at all in the new
 * dashboard even though the generated client already supported it - this
 * component just connects the two.
 */
export function ImportLeadsDialog({ open, onOpenChange, onImported }: ImportLeadsDialogProps) {
  const [step, setStep] = useState<Step>('input');
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const previewMut = usePreviewLeadImport();
  const importMut = useImportLeads();

  function reset() {
    setStep('input');
    setCsvText('');
    setPreview(null);
    setReport(null);
  }

  function handleClose(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function handleFileChosen(file: File) {
    const reader = new FileReader();
    reader.onload = () => setCsvText(String(reader.result ?? ''));
    reader.onerror = () => toast.error("Impossible de lire le fichier.");
    reader.readAsText(file);
  }

  async function handlePreview() {
    if (!csvText.trim()) return;
    try {
      const result = await previewMut.mutateAsync({ data: { csv_text: csvText } });
      setPreview(result);
      setStep('preview');
    } catch {
      toast.error("Impossible d'analyser le fichier CSV.");
    }
  }

  async function handleConfirmImport() {
    try {
      const result = await importMut.mutateAsync({ data: { csv_text: csvText } });
      setReport(result);
      setStep('done');
      onImported();
    } catch {
      toast.error("L'import a échoué.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Importer des leads (CSV)</DialogTitle>
        </DialogHeader>

        {step === 'input' && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Colonnes reconnues : <code>name, phone, email, region, source, provider, notes</code>.
              Chaque ligne doit avoir au moins un email ou un téléphone.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4 mr-1.5" />
                Choisir un fichier .csv
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileChosen(file);
                }}
              />
              {csvText && (
                <span className="text-xs text-muted-foreground self-center flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5" />
                  {csvText.split('\n').filter(Boolean).length - 1} lignes chargées
                </span>
              )}
            </div>
            <Textarea
              placeholder="Ou collez le contenu CSV ici…"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              className="min-h-40 font-mono text-xs"
            />
          </div>
        )}

        {step === 'preview' && preview && (
          <div className="space-y-3">
            <div className="flex gap-4 text-sm">
              <span><strong>{preview.total_rows}</strong> lignes</span>
              {preview.rows_missing_identifier > 0 && (
                <span className="text-amber-600 flex items-center gap-1">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {preview.rows_missing_identifier} sans email/téléphone (ignorées)
                </span>
              )}
            </div>
            <div className="rounded-lg border overflow-auto max-h-72">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    {preview.headers.map((h) => <TableHead key={h}>{h}</TableHead>)}
                    <TableHead>Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.rows.map((row) => (
                    <TableRow key={row.row_number}>
                      <TableCell className="text-xs text-muted-foreground">{row.row_number}</TableCell>
                      {preview.headers.map((h) => (
                        <TableCell key={h} className="text-xs">{String(row.data[h] ?? '')}</TableCell>
                      ))}
                      <TableCell className="text-xs">
                        {row.missing_identifier ? (
                          <span className="text-red-600">Ignorée</span>
                        ) : row.would_be_duplicate ? (
                          <span className="text-amber-600">Doublon → mise à jour</span>
                        ) : (
                          <span className="text-emerald-600">Nouveau</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {step === 'done' && report && (
          <div className="space-y-2 text-sm">
            <p className="flex items-center gap-1.5 text-emerald-600 font-medium">
              <CheckCircle2 className="h-4 w-4" />
              Import terminé
            </p>
            <ul className="text-muted-foreground space-y-1">
              <li>Lignes lues : {report.rows_read}</li>
              <li>Créés : {report.created}</li>
              <li>Mis à jour : {report.updated}</li>
              <li>Doublons : {report.duplicates}</li>
              <li>Ignorés : {report.skipped}</li>
              <li>Erreurs : {report.errors}</li>
            </ul>
          </div>
        )}

        <DialogFooter>
          {step === 'input' && (
            <>
              <Button variant="outline" onClick={() => handleClose(false)}>Annuler</Button>
              <Button onClick={handlePreview} disabled={!csvText.trim() || previewMut.isPending}>
                {previewMut.isPending ? 'Analyse…' : 'Prévisualiser'}
              </Button>
            </>
          )}
          {step === 'preview' && (
            <>
              <Button variant="outline" onClick={() => setStep('input')}>Retour</Button>
              <Button onClick={handleConfirmImport} disabled={importMut.isPending}>
                {importMut.isPending ? 'Import…' : `Importer ${preview?.total_rows ?? 0} lignes`}
              </Button>
            </>
          )}
          {step === 'done' && (
            <Button onClick={() => handleClose(false)}>Fermer</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
