import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { NotFoundPage } from '@/features/not-found/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    lazy: async () => ({ Component: (await import('@/features/login/LoginPage')).LoginPage }),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/overview" replace />,
      },
      {
        path: 'overview',
        lazy: async () => ({ Component: (await import('@/features/overview/OverviewPage')).OverviewPage }),
      },
      {
        path: 'architecture',
        lazy: async () => ({ Component: (await import('@/features/architecture/ArchitectureExplorerPage')).ArchitectureExplorerPage }),
      },
      {
        path: 'findings',
        lazy: async () => ({ Component: (await import('@/features/findings/FindingsListPage')).FindingsListPage }),
      },
      {
        path: 'findings/:findingId',
        lazy: async () => ({ Component: (await import('@/features/findings/FindingDetailPage')).FindingDetailPage }),
      },
      {
        path: 'intents',
        lazy: async () => ({ Component: (await import('@/features/intents/IntentsPage')).IntentsPage }),
      },
      {
        path: 'drift-events',
        lazy: async () => ({ Component: (await import('@/features/drift-events/DriftEventsPage')).DriftEventsPage }),
      },
      {
        path: 'remediation',
        lazy: async () => ({ Component: (await import('@/features/remediation/RemediationPage')).RemediationPage }),
      },
      {
        path: 'audit-trail',
        lazy: async () => ({ Component: (await import('@/features/audit-trail/AuditTrailPage')).AuditTrailPage }),
      },
      {
        path: 'settings',
        lazy: async () => ({ Component: (await import('@/features/settings/SettingsPage')).SettingsPage }),
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);
