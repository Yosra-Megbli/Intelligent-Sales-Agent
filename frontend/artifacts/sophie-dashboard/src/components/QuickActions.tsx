import { useState } from 'react';
import { useLocation } from 'wouter';
import { Upload, UserPlus, Megaphone } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ImportLeadsDialog } from '@/components/ImportLeadsDialog';
import { NewLeadDialog } from '@/components/NewLeadDialog';

interface QuickActionsProps {
  onDataChanged: () => void;
}

/**
 * Priority 2's "Quick Actions" gap: Importer CSV and Nouvelle Campagne
 * already existed, just scattered across the Leads/Campaigns pages with no
 * single entry point on the main dashboard. This groups them (plus the new
 * manual "Nouveau Lead" form) in one place, importing the same dialogs
 * already used elsewhere rather than duplicating their logic.
 */
export function QuickActions({ onDataChanged }: QuickActionsProps) {
  const [, navigate] = useLocation();
  const [importOpen, setImportOpen] = useState(false);
  const [newLeadOpen, setNewLeadOpen] = useState(false);

  return (
    <Card className="border shadow-sm">
      <CardContent className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mr-1">
            Actions rapides
          </span>
          <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4 mr-1.5" />
            Importer CSV
          </Button>
          <Button variant="default" size="sm" onClick={() => setNewLeadOpen(true)}>
            <UserPlus className="h-4 w-4 mr-1.5" />
            Nouveau lead
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/campaigns')}>
            <Megaphone className="h-4 w-4 mr-1.5" />
            Nouvelle campagne
          </Button>
        </div>
      </CardContent>

      <ImportLeadsDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={onDataChanged}
      />
      <NewLeadDialog
        open={newLeadOpen}
        onOpenChange={setNewLeadOpen}
        onCreated={onDataChanged}
      />
    </Card>
  );
}
