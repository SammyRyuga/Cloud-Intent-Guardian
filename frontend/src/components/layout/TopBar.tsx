import React from 'react';
import { ConnectionStatus } from './ConnectionStatus';
import { useAuth } from '@/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { env } from '@/config/env';
import { LogOut, User } from 'lucide-react';

export function TopBar() {
  const { user, signOut } = useAuth();

  return (
    <header className="h-[68px] border-b border-rule bg-sheet px-4 md:px-6 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <span className="lg:hidden font-title text-base font-semibold text-ink">Guardian</span><span className="hidden lg:inline text-xs text-graphite">Workspace</span><ConnectionStatus /><span className="hidden xl:inline border-l border-rule pl-3 text-xs text-graphite">{env.defaultRegion}</span>
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <div className="flex items-center gap-2 hidden sm:flex text-xs text-graphite pr-2 border-r border-rule">
            <User className="w-3.5 h-3.5 stroke-[1.5]" />
            <span className="font-medium text-ink">{user.name || user.username}</span>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={() => signOut()} title="Sign out">
          <LogOut className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
