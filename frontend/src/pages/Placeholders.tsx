import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { toast } from "sonner";
import {
  UserCheck,
  Megaphone,
  MessageSquare,
  ShieldCheck,
  Send,
  Lock,
  PhoneCall,
  CheckCircle,
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
              <PhoneCall className="w-4 h-4 text-[var(--brand-green)]" />
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
              <UserCheck className="w-4 h-4 text-[var(--brand-green)]" />
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
          <div className="w-12 h-12 rounded-full bg-[var(--brand-soft)] border border-[var(--brand-soft-border)] flex items-center justify-center text-[var(--brand-green)] mb-3">
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
  const [messages, setMessages] = useState<Array<{ role: "assistant" | "user"; text: string }>>([
    {
      role: "assistant",
      text: "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — un conseiller humain reste disponible à tout moment. Comment puis-je vous renseigner sur nos contrats d'énergie ?",
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const userText = inputMessage;
    setInputMessage("");
    setMessages((prev) => [...prev, { role: "user", text: userText }]);

    // Instant simulated response honoring Sophie's golden rules
    setTimeout(() => {
      if (userText.toUpperCase().includes("STOP") || userText.toUpperCase().includes("ARRÊT")) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: "C'est bien noté. Votre demande d'arrêt a été prise en compte immédiatement. Vos données sont supprimées de nos listes de contact conformément au RGPD.",
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: "Chez Ecofix, nous ne proposons aucun contrat fixe mais uniquement nos offres Flexy (variable mensuel transparent) et Motion (dynamique horaire). Quel est votre gestionnaire de réseau (Fluvius en Flandre, ou ORES/RESA en Wallonie) ?",
          },
        ]);
      }
    }, 400);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center justify-between pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--ink)]">
            {t("nav.chat")}
          </h1>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Simulateur d'échange direct avec Sophie (vérification des règles de divulgation IA et opt-out).
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-[var(--brand-green)] font-semibold bg-[var(--brand-soft)] px-2.5 py-1 rounded-full">
          <CheckCircle className="w-3.5 h-3.5" />
          <span>Divulgation IA Active</span>
        </div>
      </div>

      <Card className="flex flex-col h-[520px]">
        <CardHeader className="py-3 px-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-[var(--brand-green)]" />
            <CardTitle className="text-sm">Session de Test Canal Web</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-[0.75rem] px-3.5 py-2.5 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "bg-[var(--brand-green)] text-white font-medium"
                    : "bg-[var(--surface-hover)] border border-[var(--border)] text-[var(--ink)]"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
        </CardContent>
        <form onSubmit={handleSend} className="p-3 border-t border-[var(--border)] flex gap-2">
          <input
            type="text"
            placeholder="Tapez un message pour Sophie (ex: 'Quel tarif ?', 'STOP')..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            className="flex-1 px-3.5 py-2 text-xs rounded-[0.5rem] border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-green)]"
          />
          <Button type="submit" size="sm">
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
        <div className="flex items-center gap-1.5 text-xs text-[var(--brand-green)] font-semibold bg-[var(--brand-soft)] px-2.5 py-1 rounded-full">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>RGPD / GDPR Strict</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-[var(--brand-green)]" />
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
              <ShieldCheck className="w-4 h-4 text-[var(--brand-green)]" />
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
