import React from 'react';
import { env } from '@/config/env';
import { NavLink } from 'react-router-dom';
import { navigation } from './navigation';

export function Sidebar() {
  return (
    <aside className="guardian-sidebar hidden lg:flex w-[248px] border-r border-rule bg-sheet flex-col shrink-0 select-none">
      <div className="h-[68px] border-b border-rule flex items-center px-6 gap-3">
        <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true" className="text-prussian shrink-0">
          <rect x="3" y="3" width="19" height="19" rx="2" stroke="currentColor" strokeWidth="1.5" />
          <rect x="8" y="8" width="19" height="19" rx="2" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" />
        </svg>
        <span className="font-title font-semibold text-base leading-tight">Cloud Intent<br />Guardian</span>
      </div>
      <div className="px-6 pt-7 pb-3 text-xs text-graphite">Architecture review</div>
      <nav aria-label="Primary navigation" className="flex-1 px-3 pb-3 overflow-y-auto">
        {navigation.map((item, index) => {
          const Icon = item.icon;
          return (
            <NavLink key={item.to} to={item.to} className={({ isActive }) =>
              `guardian-nav-link flex items-center gap-3 px-3 min-h-10 rounded-lg text-sm font-medium transition-colors ${index === 4 || index === 7 ? 'mt-5' : 'mt-1'} ${isActive ? 'bg-prussian-tint text-prussian guardian-nav-active' : 'text-graphite hover:bg-film hover:text-ink'}`
            }>
              <Icon className="w-[18px] h-[18px] shrink-0 stroke-[1.5]" /><span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="p-6 border-t border-rule text-xs space-y-1">
        <p className="text-graphite">Configured AWS region</p>
        <p className="font-mono text-ink">{env.defaultRegion}</p>
      </div>
    </aside>
  );
}
