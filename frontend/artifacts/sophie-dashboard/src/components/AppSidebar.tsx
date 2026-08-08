import { Link, useLocation } from 'wouter';
import { cn } from '@/lib/utils';
import { EcofixMark } from '@/components/EcofixLogo';
import {
  LayoutDashboard,
  Users,
  Megaphone,
  ChevronRight,
  MessageCircle,
} from 'lucide-react';

// wouter v3 Link renders an <a> directly — never wrap it in another <a>.

const NAV_ITEMS = [
  { href: '/',           label: 'Dashboard',   icon: LayoutDashboard },
  { href: '/leads',      label: 'Leads',        icon: Users },
  { href: '/campaigns',  label: 'Campagnes',    icon: Megaphone },
  { href: '/chat-demo',  label: 'Chat démo',    icon: MessageCircle },
];

export function AppSidebar() {
  const [location] = useLocation();

  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 h-screen sticky top-0 bg-sidebar text-sidebar-foreground">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/15">
        <div className="rounded-lg bg-white/15 p-1.5">
          <EcofixMark className="h-5 w-5" />
        </div>
        <div>
          <p className="font-bold text-sm tracking-tight">Sophie</p>
          <p className="text-[10px] text-white/60 leading-none mt-0.5">Ecofix AI Agent</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? location === '/' : location.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                active
                  ? 'bg-white/15 text-white'
                  : 'text-white/70 hover:bg-white/10 hover:text-white',
              )}
            >
              {active && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />
              )}
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="h-3 w-3 opacity-60" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/15">
        <p className="text-[10px] text-white/40 leading-relaxed">
          Sophie v1.0 · Phase Pilote<br />
          © 2026 Ecofix
        </p>
      </div>
    </aside>
  );
}

/* Mobile top bar */
export function MobileTopBar() {
  const [location] = useLocation();
  const current = NAV_ITEMS.find(
    ({ href }) => href === '/' ? location === '/' : location.startsWith(href),
  );

  return (
    <header className="md:hidden sticky top-0 z-50 bg-sidebar text-sidebar-foreground flex items-center justify-between px-4 h-14 shadow-md">
      <div className="flex items-center gap-2">
        <EcofixMark className="h-5 w-5" />
        <span className="font-bold text-sm">Sophie</span>
      </div>
      <span className="text-sm font-medium text-white/80">{current?.label}</span>
    </header>
  );
}

/* Mobile bottom nav — the top bar only showed the current page name with no
   way to navigate; on small screens this was the only chrome, so there was
   no way to switch pages at all. This closes that gap. */
export function MobileBottomNav() {
  const [location] = useLocation();

  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-sidebar border-t border-white/15 flex items-stretch h-16 pb-[env(safe-area-inset-bottom)]">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = href === '/' ? location === '/' : location.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors',
              active ? 'text-white' : 'text-white/60',
            )}
          >
            <Icon className="h-5 w-5" strokeWidth={active ? 2.5 : 2} />
            <span>{label}</span>
            {active && <span className="absolute bottom-0 h-0.5 w-8 rounded-full bg-accent" />}
          </Link>
        );
      })}
    </nav>
  );
}
