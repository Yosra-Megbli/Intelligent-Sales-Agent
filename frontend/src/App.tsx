import React, { useState } from "react";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { AppShell } from "@/components/layout/AppShell";
import { LoginScreen } from "@/components/auth/LoginScreen";
import { OverviewPage } from "@/pages/OverviewPage";
import { LeadsPage } from "@/pages/LeadsPage";
import { ConversationsPage } from "@/pages/ConversationsPage";
import { CampaignsPage } from "@/pages/CampaignsPage";
import { CompliancePage } from "@/pages/CompliancePage";
import { SettingsPage } from "@/pages/SettingsPage";
import { HandoffsPage } from "@/pages/Placeholders";
import { Toaster } from "sonner";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const DashboardContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>("overview");

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[var(--bg-app)]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--border)] border-t-[var(--color-teal)] animate-spin" />
          <span className="text-xs text-[var(--ink-muted)] font-medium">
            Initialisation de la console Sophie...
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return (
    <AppShell currentTab={currentTab} onTabChange={setCurrentTab}>
      {currentTab === "overview" && <OverviewPage />}
      {currentTab === "leads" && <LeadsPage />}
      {(currentTab === "conversations" || currentTab === "chat") && <ConversationsPage />}
      {currentTab === "handoffs" && <HandoffsPage />}
      {currentTab === "campaigns" && <CampaignsPage />}
      {currentTab === "compliance" && <CompliancePage />}
      {currentTab === "settings" && <SettingsPage />}
    </AppShell>
  );
};



export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <DashboardContent />
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "var(--surface)",
                color: "var(--ink)",
                border: "1px solid var(--border)",
                borderRadius: "0.75rem",
                fontSize: "12px",
              },
            }}
          />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
