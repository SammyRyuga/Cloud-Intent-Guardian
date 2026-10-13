import React from 'react';
import { Copy, Check } from 'lucide-react';

export function CopyableId({ id, className = '' }: { id?: string; className?: string }) {
  const [copied, setCopied] = React.useState(false);

  if (!id) return <span className="text-pencil font-mono text-xs">—</span>;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <span className={`inline-flex items-center gap-1 font-mono text-xs text-ink/90 bg-film px-1.5 py-0.5 rounded border border-rule ${className}`}>
      <span className="truncate max-w-[200px]" title={id}>{id}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="text-graphite hover:text-ink transition-colors p-0.5"
        title="Copy ID"
        aria-label="Copy identifier"
      >
        {copied ? <Check className="w-3 h-3 text-survey" /> : <Copy className="w-3 h-3" />}
      </button>
    </span>
  );
}
