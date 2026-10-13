import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { MockModeBanner } from './MockModeBanner';
import { env } from '@/config/env';

export function AppShell() {
  return (
    <div className="flex flex-col h-screen w-screen bg-film text-ink overflow-hidden">
      <MockModeBanner />
      {env.localApi && <div role="status" className="bg-film border-b border-rule px-6 py-2 text-xs text-ink">Local API development - DynamoDB Local data; AWS discovery and Cognito are not verified.</div>}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <TopBar />
          <nav aria-label="Mobile navigation" className="md:hidden flex gap-4 overflow-x-auto border-b border-rule bg-sheet px-4 py-2 text-sm shrink-0">
            <NavLink to="/overview">Overview</NavLink><NavLink to="/intents">Intents</NavLink><NavLink to="/findings">Findings</NavLink><NavLink to="/settings">Settings</NavLink>
          </nav>
          <main className="flex-1 overflow-y-auto p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
