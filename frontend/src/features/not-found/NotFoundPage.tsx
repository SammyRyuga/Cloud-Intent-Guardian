import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Compass } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card className="w-full max-w-md p-6 text-center">
        <div className="flex flex-col items-center">
          <Compass className="w-10 h-10 text-graphite mb-3 stroke-[1.5]" />
          <h1 className="font-title text-lg font-bold text-ink">Page Not Found</h1>
          <p className="text-xs text-pencil mt-1 mb-6">
            The resource or route you requested does not exist or has been relocated.
          </p>
          <Link to="/overview">
            <Button variant="primary" size="sm">
              Return to overview
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
