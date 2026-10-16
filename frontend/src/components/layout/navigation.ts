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

export const navigation = [
  { name: 'Overview', to: '/overview', icon: LayoutDashboard },
  { name: 'Architecture Explorer', to: '/architecture', icon: Network },
  { name: 'Findings', to: '/findings', icon: ShieldAlert },
  { name: 'Intents', to: '/intents', icon: FileCode2 },
  { name: 'Drift Events', to: '/drift-events', icon: GitCompare },
  { name: 'Remediation', to: '/remediation', icon: Wrench },
  { name: 'Audit Trail', to: '/audit-trail', icon: History },
  { name: 'Settings', to: '/settings', icon: Settings },
];

