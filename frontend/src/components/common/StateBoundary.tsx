import React from 'react';
import { Button } from '@/components/ui/Button';
import { CopyableId } from '@/components/common/CopyableId';
import { AlertCircle, FileQuestion, Ban } from 'lucide-react';

interface StateBoundaryProps {
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  isNotEnabled?: boolean;
  notEnabledMessage?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function StateBoundary({
  isLoading,
  isError,
  error,
  isEmpty,
  emptyTitle = 'No records found',
  emptyDescription = 'There are no items matching this criteria.',
  emptyAction,
  isNotEnabled,
  notEnabledMessage = 'This part of the product is not enabled in this environment.',
  onRetry,
  children,
}: StateBoundaryProps) {
  if (isNotEnabled) {
    return (
      <div className="flex flex-col items-start p-8 rounded-[12px] border border-rule bg-sheet text-ink max-w-xl">
        <div className="flex items-center gap-2 text-graphite mb-2">
          <Ban className="w-5 h-5 text-pencil" />
          <h3 className="font-title text-base font-semibold">Not enabled</h3>
        </div>
        <p className="text-sm text-pencil mb-4">{notEnabledMessage}</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4 w-full">
        <div className="h-8 w-1/3 bg-rule/50 rounded animate-pulse" />
        <div className="h-40 w-full bg-rule/30 rounded-[12px] border border-rule animate-pulse" />
        <div className="h-64 w-full bg-rule/20 rounded-[12px] border border-rule animate-pulse" />
      </div>
    );
  }

  if (isError) {
    const apiError = error as { requestId?: string; message?: string } | undefined;
    return (
      <div className="flex flex-col items-start p-6 rounded-[12px] border border-sev-critical/30 bg-sheet text-ink max-w-xl">
        <div className="flex items-center gap-2 text-sev-critical mb-2">
          <AlertCircle className="w-5 h-5" />
          <h3 className="font-title text-base font-semibold">Unable to load data</h3>
        </div>
        <p className="text-sm text-pencil mb-4">
          {error?.message || 'The server could not complete the request. Please check your connection and retry.'}
        </p>
        {apiError?.requestId && (
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs text-graphite font-mono">Request ID:</span>
            <CopyableId id={apiError.requestId} />
          </div>
        )}
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry request
          </Button>
        )}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="flex flex-col items-start p-8 rounded-[12px] border border-rule bg-sheet text-ink max-w-xl">
        <div className="flex items-center gap-2 text-graphite mb-2">
          <FileQuestion className="w-5 h-5 text-pencil" />
          <h3 className="font-title text-base font-semibold">{emptyTitle}</h3>
        </div>
        <p className="text-sm text-pencil mb-4">{emptyDescription}</p>
        {emptyAction}
      </div>
    );
  }

  return <>{children}</>;
}
