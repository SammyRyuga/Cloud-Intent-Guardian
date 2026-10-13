import React from 'react';
import { env } from '@/config/env';
import { AlertTriangle } from 'lucide-react';

export function MockModeBanner() {
  if (!env.useMocks) return null;

  return (
    <div
      role="banner"
      className="bg-sev-medium/10 border-b border-sev-medium/30 px-4 py-1.5 flex items-center justify-between text-xs text-sev-medium"
    >
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
        <span>MOCK MODE ACTIVE — Connected to local simulated fixture services. Live AWS mutating calls are disabled.</span>
      </div>
      <span className="font-mono text-[11px] uppercase tracking-wider bg-sev-medium/20 px-1.5 py-0.5 rounded">
        DEMO
      </span>
    </div>
  );
}
