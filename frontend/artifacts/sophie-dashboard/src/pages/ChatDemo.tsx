import { useEffect, useRef, useState } from 'react';
import { Send, Leaf, Loader2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

/**
 * Live demo chat page — talks directly to the real conversation endpoints
 * (`POST /api/conversations`, `POST /api/conversations/{id}/messages`,
 * `GET /api/conversations/{id}/messages`) exactly as `channels/web.py`
 * exposes them. No mocked responses: every reply here is Sophie's real
 * pipeline (Intent Classifier -> Rules Engine -> State Machine -> LLM
 * Responder), the same one the Dashboard's KPIs are driven by.
 *
 * Not wired into the generated api-client-react hooks because these three
 * routes aren't declared in lib/api-spec/openapi.yaml (only the dashboard/
 * leads/campaigns routes are) — plain fetch keeps this page self-contained
 * for the demo instead of hand-editing the generated client.
 */

type Role = 'lead' | 'sophie' | 'system';

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  pending?: boolean;
}

function bubbleClasses(role: Role) {
  if (role === 'lead') {
    return 'bg-primary text-primary-foreground ml-auto rounded-br-sm';
  }
  if (role === 'system') {
    return 'bg-destructive/10 text-destructive text-xs mx-auto';
  }
  return 'bg-muted text-foreground mr-auto rounded-bl-sm';
}

// Backend MessageOut.role is "user" | "assistant" — map to our display roles.
function mapRole(role: string): Role {
  if (role === 'user') return 'lead';
  if (role === 'assistant') return 'sophie';
  return 'system';
}

export default function ChatDemo() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [starting, setStarting] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function startConversation() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setConversationId(data.conversation_id);
      setMessages([
        {
          id: 'welcome',
          role: 'sophie',
          content: "Bonjour 👋 Je suis Sophie, l'assistante d'Ecofix. Comment puis-je vous aider aujourd'hui ?",
        },
      ]);
    } catch {
      setError("Impossible de démarrer la conversation. Vérifiez que le backend tourne sur le port 8000 (et GROQ_API_KEY).");
    } finally {
      setStarting(false);
    }
  }

  async function sendMessage() {
    const text = draft.trim();
    if (!text || !conversationId || sending) return;

    const optimisticId = `local-${Date.now()}`;
    setMessages((prev) => [...prev, { id: optimisticId, role: 'lead', content: text }]);
    setDraft('');
    setSending(true);
    setError(null);

    try {
      const res = await fetch(`/api/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          id: `${optimisticId}-reply`,
          role: 'sophie',
          content: data.reply ?? '(pas de réponse)',
        },
      ]);
    } catch {
      setError('Le message n’est pas parti — le backend est peut-être hors ligne.');
    } finally {
      setSending(false);
    }
  }

  if (!conversationId) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <Card className="max-w-sm w-full p-8 text-center space-y-4">
          <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Leaf className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold text-lg">Chat démo — Sophie</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Démarre une vraie conversation via l'API (/api/conversations), exactement comme un prospect le ferait.
            </p>
          </div>
          <Button onClick={startConversation} disabled={starting} className="w-full">
            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Démarrer la conversation'}
          </Button>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="border-b px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center">
          <Leaf className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="font-semibold text-sm">Sophie</p>
          <p className="text-xs text-muted-foreground">Assistante commerciale Ecofix</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              'max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap',
              bubbleClasses(m.role),
            )}
          >
            {m.content}
          </div>
        ))}
        {sending && (
          <div className="max-w-[75%] rounded-2xl rounded-bl-sm px-4 py-2 text-sm bg-muted text-muted-foreground mr-auto flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Sophie écrit…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="px-6 text-xs text-destructive pb-1">{error}</p>}

      <div className="border-t p-4 flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder="Écrivez un message…"
          disabled={sending}
        />
        <Button onClick={sendMessage} disabled={sending || !draft.trim()} size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
