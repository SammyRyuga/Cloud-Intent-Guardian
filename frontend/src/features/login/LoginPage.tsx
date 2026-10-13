import React from 'react';
import { useAuth } from '@/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ShieldCheck, Lock } from 'lucide-react';

export function LoginPage() {
  const { signIn } = useAuth();
  const [submitting, setSubmitting] = React.useState(false);

  const handleSignIn = async () => {
    setSubmitting(true);
    try {
      await signIn();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen w-screen items-center justify-center bg-film p-4">
      <Card className="w-full max-w-md p-8" padding="none">
        <div className="flex flex-col items-center text-center p-6">
          <div className="w-12 h-12 rounded-lg bg-prussian flex items-center justify-center text-white mb-4 shadow-none">
            <ShieldCheck className="w-6 h-6 stroke-[1.5]" />
          </div>

          <h1 className="font-title text-xl font-bold text-ink">Cloud Intent Guardian</h1>
          <p className="text-xs text-pencil mt-1 mb-6">
            Autonomous Cloud Architecture Conformance Engine
          </p>

          <div className="w-full space-y-4">
            <div className="p-3 bg-film rounded border border-rule text-xs text-graphite text-left flex items-start gap-2.5">
              <Lock className="w-4 h-4 text-graphite shrink-0 mt-0.5 stroke-[1.5]" />
              <span>
                Sign in with AWS Cognito Managed Login using your authorized enterprise credentials.
              </span>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              isLoading={submitting}
              onClick={handleSignIn}
            >
              Sign in with Cognito
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
