import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { toast } from "sonner";
import { apiClient } from "@/api/client";
import {
  UserCheck,
  Megaphone,
  MessageSquare,
  ShieldCheck,
  Send,
  Lock,
  CheckCircle,
  RotateCcw,
  AlertTriangle,
  PhoneCall,
} from "lucide-react";

export const HandoffsPage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center justify-between pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.handoffs")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            File d'attente des prospects nécessitant une intervention d'un conseiller humain Ecofix.
          </p>
        </div>
        <Badge variant="phase2">Phase 2 Connecté</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <PhoneCall className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>Transferts Téléphoniques & Voice</CardTitle>
            </div>
            <CardDescription>
              Demandes de rappel et prospects ayant sollicité explicitement un humain.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-4 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] text-xs text-[var(--ink-muted)]">
              File active : 0 appel en attente. Le système de bascule déterministe redirige les demandes selon les règles AGENTS.md.
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>Cas Complexes / Énergie Spécifique</CardTitle>
            </div>
            <CardDescription>
              Prospects professionnels ou configurations solaires/batteries hors périmètre automatisé.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-4 rounded-[0.5rem] bg-[var(--surface-hover)] border border-[var(--border)] text-xs text-[var(--ink-muted)]">
              Tous les dossiers complexes sont étiquetés avec le motif exact d'escalade.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export const CampaignsPage: React.FC = () => {
  const { t } = useTranslation();

  const handleCreateCampaign = () => {
    toast.info(t("toast.phase2Title"), {
      description: "Création et ordonnancement de campagnes : " + t("toast.phase2Desc"),
    });
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center justify-between pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.campaigns")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Gestion des campagnes d'engagement sortantes (Outbound Engine & Scheduler).
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={handleCreateCampaign}>
          <Megaphone className="w-3.5 h-3.5 mr-1" />
          <span>Nouvelle Campagne</span>
        </Button>
      </div>

      <Card>
        <CardContent className="p-8 text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] flex items-center justify-center text-[var(--color-teal-text)] mb-3">
            <Megaphone className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-sm text-[var(--ink)]">
            Ordonnanceur de Campagnes Sortantes
          </h3>
          <p className="text-xs text-[var(--ink-muted)] max-w-md mt-1 mb-4">
            Le moteur de campagnes respecte les créneaux légaux de prospection en Belgique (pas d'appels avant 9h ni après 19h, pas le dimanche).
          </p>
          <Badge variant="phase2">Sprint 2</Badge>
        </CardContent>
      </Card>
    </div>
  );
};

export const ChatSimulatorPage: React.FC = () => {
  const { t } = useTranslation();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentState, setCurrentState] = useState<string>("START");
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<
    Array<{
      role: "user" | "assistant";
      text: string;
      state?: string;
      action?: string | null;
      rate_limited?: boolean;
    }>
  >([
    {
      role: "assistant",
      text: "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment. Comment puis-je vous renseigner sur nos contrats d'énergie ?",
      state: "GREETING",
    },
  ]);

  const initConversation = async () => {
    try {
      const res = await apiClient.startConversation({
        first_name: "Simulateur",
        last_name: "Web",
      });
      setConversationId(res.conversation_id);
      setCurrentState("START");
      setLastAction(null);
    } catch (err) {
      console.warn("Could not pre-init conversation:", err);
    }
  };

  useEffect(() => {
    initConversation();
  }, []);

  const handleReset = async () => {
    setMessages([
      {
        role: "assistant",
        text: "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment. Comment puis-je vous renseigner sur nos contrats d'énergie ?",
        state: "GREETING",
      },
    ]);
    setCurrentState("START");
    setLastAction(null);
    await initConversation();
    toast.success("Nouvelle session de simulation démarrée.");
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isSending) return;

    const userText = inputMessage.trim();
    setInputMessage("");
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setIsSending(true);

    try {
      let activeConvId = conversationId;
      if (!activeConvId) {
        const startRes = await apiClient.startConversation({
          first_name: "Simulateur",
          last_name: "Web",
        });
        activeConvId = startRes.conversation_id;
        setConversationId(activeConvId);
      }

      const res = await apiClient.sendChatMessage(activeConvId, userText);
      setCurrentState(res.state);
      setLastAction(res.required_action);

      if (res.rate_limited) {
        toast.warning(
          "Quota de requêtes IA temporairement saturé : Sophie utilise les réponses certifiées de repli (Mode Haute Disponibilité).",
          { duration: 6000 }
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text:
            res.reply ||
            "Merci pour votre réponse. Un conseiller humain reste à votre disposition.",
          state: res.state,
          action: res.required_action,
          rate_limited: res.rate_limited,
        },
      ]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Erreur simulateur: ${msg}`);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Désolée, une erreur de communication avec le moteur Sophie s'est produite. Veuillez réessayer.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.chat")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Simulateur en direct connecté au moteur de vente déterministe (State Machine & Rules Engine).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleReset} className="text-xs">
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            <span>Réinitialiser la session</span>
          </Button>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-teal-text)] font-semibold bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] px-2.5 py-1 rounded-full">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Moteur Direct (Live API)</span>
          </div>
        </div>
      </div>

      <Card className="flex flex-col h-[560px]">
        <CardHeader className="py-3 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-[var(--color-teal-text)]" />
            <CardTitle className="text-sm">Session de Test Canal Web</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase text-[var(--ink-muted)]">
              État actuel :
            </span>
            <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[var(--color-teal-soft)] text-[var(--color-teal-text)] border border-[var(--color-teal-soft-border)]">
              {currentState}
            </span>
            {lastAction && (
              <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink-muted)]">
                {lastAction}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-[0.75rem] px-3.5 py-2.5 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "bg-lavender text-lavender-ink font-semibold shadow-xs"
                    : "bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)]"
                }`}
              >
                {m.text}
              </div>
              {m.state && m.role === "assistant" && (
                <div className="flex items-center gap-1.5 mt-1 px-1 text-[10px] font-mono text-[var(--ink-subtle)]">
                  <span>État : {m.state}</span>
                  {m.action && <span>• Action : {m.action}</span>}
                </div>
              )}
              {m.rate_limited && (
                <div className="flex items-center gap-1.5 mt-1 px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-[10px] text-amber-800 dark:text-amber-200 font-medium">
                  <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                  <span>Mode Haute Disponibilité actif (Quota IA saturé)</span>
                </div>
              )}
            </div>
          ))}
          {isSending && (
            <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)] italic px-2 py-1">
              <div className="w-2 h-2 rounded-full bg-[var(--color-teal)] animate-ping" />
              <span>Sophie analyse et répond...</span>
            </div>
          )}
        </CardContent>
        <form onSubmit={handleSend} className="p-3 border-t border-[var(--border)] flex gap-2">
          <input
            type="text"
            placeholder="Tapez un message pour Sophie (ex: 'bonjour', 'flandre', 'Namur', 'STOP')..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={isSending}
            className="flex-1 px-3.5 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-teal)]/40 focus:border-[var(--color-teal)]"
          />
          <Button type="submit" size="sm" disabled={isSending || !inputMessage.trim()}>
            <Send className="w-3.5 h-3.5 mr-1" />
            <span>Envoyer</span>
          </Button>
        </form>
      </Card>
    </div>
  );
};

export const CompliancePage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center justify-between pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.compliance")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Conformité RGPD et cadre réglementaire de l'énergie en Belgique.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-[var(--color-teal-text)] font-semibold bg-[var(--color-teal-soft)] border border-[var(--color-teal-soft-border)] px-2.5 py-1 rounded-full">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>RGPD / GDPR Strict</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>Mécanisme STOP & Déréférencement</CardTitle>
            </div>
            <CardDescription>Purge irréversible des Données à Caractère Personnel</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-xs text-[var(--ink-muted)] leading-relaxed">
            <p>
              Dès réception du mot-clé <strong>STOP</strong>, <strong>STOPT</strong> ou <strong>ARRÊT</strong> :
            </p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Suppression immédiate du nom, prénom, email et téléphone.</li>
              <li>Maintien d'une clé de suppression anonymisée pour éviter toute sollicitation future.</li>
              <li>Arrêt instantané des séquences de relance (follow-ups).</li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[var(--color-teal-text)]" />
              <CardTitle>Règles Marché de l'Énergie Belge</CardTitle>
            </div>
            <CardDescription>Protection des consommateurs & Régions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-xs text-[var(--ink-muted)] leading-relaxed">
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><strong>Flandre :</strong> Fluvius exclusivement.</li>
              <li><strong>Wallonie :</strong> ORES et RESA exclusivement.</li>
              <li><strong>Bruxelles :</strong> Non desservi (fournisseur absent).</li>
              <li><strong>Zéro frais de résiliation :</strong> Droit belge applicable à tous les contrats résidentiels.</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
