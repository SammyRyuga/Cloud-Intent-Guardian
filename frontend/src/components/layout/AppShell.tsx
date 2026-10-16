import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { navigation } from './navigation';
import { TopBar } from './TopBar';
import { MockModeBanner } from './MockModeBanner';
import { env } from '@/config/env';

export function AppShell() {
  return (
    <div className="guardian-app flex flex-col h-dvh w-full bg-film text-ink overflow-hidden">
      <a href="#main-content" className="guardian-skip-link">Skip to content</a>
      <MockModeBanner />
      {env.localApi && <div role="status" className="bg-film border-b border-rule px-6 py-2 text-xs text-ink">Local API development - DynamoDB Local data; AWS discovery and Cognito are not verified.</div>}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <TopBar />
          <nav aria-label="Mobile navigation" className="guardian-mobile-nav lg:hidden flex gap-1 overflow-x-auto border-b border-rule bg-sheet px-3 py-2 text-sm shrink-0">
            {navigation.map(item => <NavLink key={item.to} to={item.to} className={({ isActive }) => `whitespace-nowrap px-3 py-2 rounded-lg ${isActive ? 'bg-prussian-tint text-prussian font-semibold' : 'text-graphite'}`}>{item.name}</NavLink>)}
          </nav>
          <main id="main-content" tabIndex={-1} className="guardian-main flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6 lg:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
