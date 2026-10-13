import React, { createContext, useContext, useEffect, useState } from 'react';
import { authClient, type UserProfile } from './authClient';
import { useQueryClient } from '@tanstack/react-query';

interface AuthContextValue {
  user: UserProfile | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => authClient.onSessionExpired(() => {setUser(null); queryClient.clear();}), [queryClient]);

  useEffect(() => {
    let mounted = true;
    authClient.getCurrentUser().then((profile) => {
      if (mounted) {
        setUser(profile);
        setLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleSignIn = async () => {
    await authClient.signIn();
    const profile = await authClient.getCurrentUser();
    setUser(profile);
  };

  const handleSignOut = async () => {
    await authClient.signOut();
    queryClient.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn: handleSignIn,
        signOut: handleSignOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
