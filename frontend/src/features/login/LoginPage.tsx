import React from 'react';
import { useAuth } from '@/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ShieldCheck, Lock } from 'lucide-react';
import { Navigate } from 'react-router-dom';
import { env } from '@/config/env';

export function LoginPage() {
  const { signIn, user } = useAuth();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  if (user) return <Navigate to="/overview" replace />;

  const handleSignIn = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await signIn();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Sign-in failed. Try again.');
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
                {env.localApi ? 'Local API development uses no Cognito login. This mode is restricted to loopback and cannot be built for production.' : env.useMocks ? 'Mock mode uses development fixtures.' : 'Sign in with Cognito using your authorized account.'}
              </span>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              isLoading={submitting}
              onClick={handleSignIn}
            >
              {env.localApi ? 'Continue to local API' : env.useMocks ? 'Continue to mock preview' : 'Sign in with Cognito'}
            </Button>
            {error && <p role="alert" className="text-xs text-sev-critical">{error}</p>}
          </div>
        </div>
      </Card>
    </div>
  );
}
