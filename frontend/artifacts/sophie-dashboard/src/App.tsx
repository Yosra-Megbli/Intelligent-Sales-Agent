import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { AppSidebar, MobileTopBar, MobileBottomNav } from '@/components/AppSidebar';
import Dashboard from '@/pages/Dashboard';
import Leads from '@/pages/Leads';
import LeadDetail from '@/pages/LeadDetail';
import Campaigns from '@/pages/Campaigns';
import CampaignDetail from '@/pages/CampaignDetail';
import ChatDemo from '@/pages/ChatDemo';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function Router() {
  return (
    <Switch>
      <Route path="/" component={Dashboard} />
      <Route path="/leads" component={Leads} />
      <Route path="/leads/:id">
        {(params) => <LeadDetail leadId={params.id!} />}
      </Route>
      <Route path="/campaigns" component={Campaigns} />
      <Route path="/campaigns/:id">
        {(params) => <CampaignDetail campaignId={params.id!} />}
      </Route>
      <Route path="/chat-demo" component={ChatDemo} />
      <Route>
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          Page introuvable
        </div>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <div className="flex h-screen overflow-hidden bg-background">
            <AppSidebar />
            <div className="flex flex-col flex-1 overflow-hidden">
              <MobileTopBar />
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden pb-16 md:pb-0">
                <Router />
              </div>
              <MobileBottomNav />
            </div>
          </div>
        </WouterRouter>
        <Toaster richColors position="top-right" />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
