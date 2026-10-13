import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  ShieldAlert,
  FileCode2,
  GitCompare,
  Wrench,
  History,
  Settings,
} from 'lucide-react';

const navigation = [
  { name: 'Overview', to: '/overview', icon: LayoutDashboard },
  { name: 'Architecture Explorer', to: '/architecture', icon: Network },
  { name: 'Findings', to: '/findings', icon: ShieldAlert },
  { name: 'Intents', to: '/intents', icon: FileCode2 },
  { name: 'Drift Events', to: '/drift-events', icon: GitCompare },
  { name: 'Remediation', to: '/remediation', icon: Wrench },
  { name: 'Audit Trail', to: '/audit-trail', icon: History },
  { name: 'Settings', to: '/settings', icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-rule bg-sheet flex flex-col shrink-0 select-none">
      <div className="h-14 border-b border-rule flex items-center px-4 gap-2.5">
        {/* Custom SVG logomark per AGENTS.md §5.7 */}
        <div className="w-7 h-7 rounded bg-prussian flex items-center justify-center text-white font-title font-bold text-sm tracking-tighter">
          CI
        </div>
        <div>
          <span className="font-title font-bold text-sm text-ink block leading-none">Cloud Intent</span>
          <span className="text-[10px] text-graphite uppercase tracking-widest font-mono">Guardian</span>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-prussian text-white'
                    : 'text-ink/80 hover:bg-film hover:text-ink'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0 stroke-[1.5]" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-3 border-t border-rule text-[11px] text-pencil">
        <span>Region: </span>
        <span className="font-mono text-ink">us-east-1</span>
      </div>
    </aside>
  );
}
