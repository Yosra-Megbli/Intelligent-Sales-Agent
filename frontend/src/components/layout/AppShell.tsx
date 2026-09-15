import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppShellProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  children: React.ReactNode;
  onSearchChange?: (q: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({
  currentTab,
  onTabChange,
  children,
  onSearchChange,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)]">
      {/* Collapsible Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={onTabChange}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        <Topbar onSearchChange={onSearchChange} />
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
};
