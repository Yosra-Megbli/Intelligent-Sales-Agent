import React, { createContext, useContext, useState } from "react";
import { apiClient } from "@/api/client";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

interface AuthContextType {
  apiKey: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (key: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Deliberately no persistence (no localStorage/sessionStorage): every
  // fresh load of the console lands on the login screen, so a demo always
  // opens on it rather than silently resuming a prior visitor's session.
  // The key lives only in this state and in apiClient's in-memory field
  // (set below) - both reset to nothing on any reload. A leftover key from
  // before this change existed is purged once so old browsers don't stay
  // auto-logged-in via the API client's old localStorage read.
  React.useEffect(() => {
    localStorage.removeItem("sophie_api_key");
  }, []);

  const login = async (key: string): Promise<boolean> => {
    const trimmed = key.trim();
    if (!trimmed) return false;

    try {
      const valid = await apiClient.verifyApiKey(trimmed);
      if (valid) {
        apiClient.setApiKey(trimmed);
        setApiKey(trimmed);
        setIsAuthenticated(true);
        toast.success(t("toast.authSuccess"));
        return true;
      } else {
        return false;
      }
    } catch {
      return false;
    }
  };

  const logout = () => {
    apiClient.setApiKey(null);
    setApiKey(null);
    setIsAuthenticated(false);
    toast.info(t("toast.loggedOut"));
  };

  return (
    <AuthContext.Provider value={{ apiKey, isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
