import { useState } from 'react';
import { Link } from 'wouter';
import { useListLeads, listLeads } from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { Search, Download, Upload, UserPlus, ChevronLeft, ChevronRight } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingState';
import { ImportLeadsDialog } from '@/components/ImportLeadsDialog';
import { NewLeadDialog } from '@/components/NewLeadDialog';
import { toCsv, downloadTextFile } from '@/lib/csv';
import { REGIONS } from '@/lib/regions';
import { toast } from 'sonner';

const PAGE_SIZE = 50;
// Server caps a single page at 200 (see backend/api/dashboard_routes.py -
// Query(..., le=200)), so exporting more than that means paging through
// every page that matches the current filters.
const EXPORT_PAGE_SIZE = 200;

const ALL_STATUSES = ['new', 'contacted', 'replied', 'qualified', 'rejected', 'human_handoff'];

const STATUS_LABELS: Record<string, string> = {
  new: 'Nouveau',
  contacted: 'Contacté',
  replied: 'A répondu',
  qualified: 'Qualifié',
  rejected: 'Rejeté',
  human_handoff: 'Transfert',
};

const EXPORT_COLUMNS = [
  'id', 'first_name', 'last_name', 'phone', 'email', 'status', 'qualification_score',
  'region', 'city', 'campaign_name', 'source', 'provider', 'notes',
  'last_contact_date', 'created_at', 'updated_at',
];

function fmt(d: string) {
  return new Date(d).toLocaleDateString('fr-FR');
}

function leadName(lead: { first_name?: string | null; last_name?: string | null }) {
  return [lead.first_name, lead.last_name].filter(Boolean).join(' ') || '—';
}

export default function Leads() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [region, setRegion] = useState<string>('all');
  const [offset, setOffset] = useState(0);
  const [importOpen, setImportOpen] = useState(false);
  const [newLeadOpen, setNewLeadOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const hasActiveFilters = Boolean(search || (status && status !== 'all') || (region && region !== 'all'));
  const activeFilterBadges = [
    search ? `Recherche : ${search}` : null,
    status && status !== 'all' ? `Statut : ${STATUS_LABELS[status] ?? status}` : null,
    region && region !== 'all' ? `Région : ${region}` : null,
  ].filter(Boolean) as string[];

  const params = {
    limit: PAGE_SIZE,
    offset,
    ...(search ? { search } : {}),
    ...(status && status !== 'all' ? { status } : {}),
    ...(region && region !== 'all' ? { region } : {}),
  };

  const { data, isLoading, isError, refetch } = useListLeads(params);

  const leads = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  function handleSearch(val: string) {
    setSearch(val);
    setOffset(0);
  }

  // Exports every lead matching the *current filters* (not just the visible
  // page): pages through the same /api/dashboard/leads endpoint at the
  // server's max page size (200) until every matching row is collected, then
  // builds and downloads a CSV client-side. No new backend endpoint needed.
  async function handleExport() {
    setExporting(true);
    try {
      const exportParams = {
        limit: EXPORT_PAGE_SIZE,
        offset: 0,
        ...(search ? { search } : {}),
        ...(status && status !== 'all' ? { status } : {}),
        ...(region && region !== 'all' ? { region } : {}),
      };
      const allLeads: typeof leads = [];
      let fetchOffset = 0;
      // Safety cap: 50 pages * 200 = 10,000 leads is far beyond any
      // realistic export size and keeps a bug from looping forever.
      for (let page = 0; page < 50; page += 1) {
        const result = await listLeads({ ...exportParams, offset: fetchOffset });
        allLeads.push(...result.items);
        if (allLeads.length >= result.total || result.items.length === 0) break;
        fetchOffset += EXPORT_PAGE_SIZE;
      }
      if (allLeads.length === 0) {
        toast.info('Aucun lead à exporter.');
        return;
      }
      const csvText = toCsv(allLeads, EXPORT_COLUMNS);
      const timestamp = new Date().toISOString().slice(0, 10);
      downloadTextFile(`leads-${timestamp}.csv`, csvText);
      toast.success(`${allLeads.length} lead(s) exporté(s).`);
    } catch {
      toast.error("L'export a échoué.");
    } finally {
      setExporting(false);
    }
  }

  function handleStatus(val: string) {
    setStatus(val);
    setOffset(0);
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-7xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Leads</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {total > 0 ? `${total} leads au total` : 'Aucun lead'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => setNewLeadOpen(true)}
            >
              <UserPlus className="h-4 w-4 mr-1.5" />
              Nouveau lead
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setImportOpen(true)}
            >
              <Upload className="h-4 w-4 mr-1.5" />
              Importer
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleExport()}
              disabled={exporting}
            >
              <Download className="h-4 w-4 mr-1.5" />
              {exporting ? 'Export…' : 'Exporter'}
            </Button>
          </div>
        </div>

        <ImportLeadsDialog
          open={importOpen}
          onOpenChange={setImportOpen}
          onImported={() => void qc.invalidateQueries({ queryKey: ['listLeads'] })}
        />
        <NewLeadDialog
          open={newLeadOpen}
          onOpenChange={setNewLeadOpen}
          onCreated={() => void qc.invalidateQueries({ queryKey: ['listLeads'] })}
        />

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-48 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher…"
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <Select value={status} onValueChange={handleStatus}>
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les statuts</SelectItem>
              {ALL_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  <StatusBadge status={s} />
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={region} onValueChange={(val) => { setRegion(val); setOffset(0); }}>
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Région" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les régions</SelectItem>
              {REGIONS.map((r) => (
                <SelectItem key={r} value={r}>{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-3">
            {activeFilterBadges.map((badge) => (
              <Badge key={badge} variant="outline" className="rounded-full px-2.5 py-1 text-xs">
                {badge}
              </Badge>
            ))}
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              onClick={() => {
                setSearch('');
                setStatus('all');
                setRegion('all');
                setOffset(0);
              }}
            >
              Effacer
            </Button>
          </div>
        )}

        {/* Table */}
        {isError ? (
          <ErrorState message="Impossible de charger les leads." onRetry={() => void refetch()} />
        ) : isLoading ? (
          <TableSkeleton rows={10} cols={7} />
        ) : leads.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-center rounded-lg border border-dashed">
            <Search className="h-8 w-8 text-muted-foreground/40" />
            <p className="mt-3 text-base font-medium text-foreground">Aucun lead trouvé</p>
            <p className="text-sm mt-1 text-muted-foreground">
              {search || (status !== 'all') || (region !== 'all')
                ? 'Modifiez vos filtres ou réinitialisez-les pour retrouver des leads.'
                : 'Importez ou ajoutez un lead pour commencer.'}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {hasActiveFilters ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch('');
                    setStatus('all');
                    setRegion('all');
                    setOffset(0);
                  }}
                >
                  Réinitialiser les filtres
                </Button>
              ) : (
                <>
                  <Button variant="default" size="sm" onClick={() => setNewLeadOpen(true)}>
                    Ajouter un lead
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
                    Importer
                  </Button>
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead>Nom</TableHead>
                    <TableHead>Téléphone</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="hidden md:table-cell">Score</TableHead>
                    <TableHead className="hidden lg:table-cell">Région</TableHead>
                    <TableHead className="hidden lg:table-cell">Campagne</TableHead>
                    <TableHead className="hidden md:table-cell">Source</TableHead>
                    <TableHead className="hidden lg:table-cell">Dernier contact</TableHead>
                    <TableHead className="text-right">Modifié</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead) => (
                    <TableRow
                      key={lead.id}
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                    >
                      <TableCell>
                        <Link
                          href={`/leads/${lead.id}`}
                          className="font-medium text-foreground hover:text-primary"
                        >
                          {leadName(lead)}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {lead.phone ?? '—'}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={lead.status} />
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {lead.qualification_score != null ? (
                          <span
                            className={
                              'inline-flex items-center justify-center min-w-8 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ' +
                              (lead.qualification_score >= 70
                                ? 'bg-emerald-50 text-emerald-700'
                                : lead.qualification_score >= 40
                                ? 'bg-amber-50 text-amber-700'
                                : 'bg-red-50 text-red-700')
                            }
                          >
                            {lead.qualification_score}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                        {lead.region ?? '—'}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                        {lead.campaign_name ?? '—'}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                        {lead.source ?? '—'}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                        {lead.last_contact_date ? fmt(lead.last_contact_date) : '—'}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {fmt(lead.updated_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Affichage {pageStart}–{pageEnd} sur {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
