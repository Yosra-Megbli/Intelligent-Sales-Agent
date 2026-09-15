import React, { createContext, useContext, useEffect, useState } from "react";
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
  const [apiKey, setApiKey] = useState<string | null>(() => localStorage.getItem("sophie_api_key"));
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkAuth = async () => {
      const stored = localStorage.getItem("sophie_api_key");
      if (!stored) {
        setIsLoading(false);
        setIsAuthenticated(false);
        return;
      }
      try {
        const valid = await apiClient.verifyApiKey(stored);
        if (valid) {
          setApiKey(stored);
          setIsAuthenticated(true);
        } else {
          // If server is unreachable or key invalid
          setIsAuthenticated(false);
        }
      } catch {
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = async (key: string): Promise<boolean> => {
    const trimmed = key.trim();
    if (!trimmed) return false;

    try {
      const valid = await apiClient.verifyApiKey(trimmed);
      if (valid) {
        localStorage.setItem("sophie_api_key", trimmed);
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
    localStorage.removeItem("sophie_api_key");
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
