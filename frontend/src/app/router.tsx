import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { LoginPage } from '@/features/login/LoginPage';
import { OverviewPage } from '@/features/overview/OverviewPage';
import { ArchitectureExplorerPage } from '@/features/architecture/ArchitectureExplorerPage';
import { FindingsListPage } from '@/features/findings/FindingsListPage';
import { FindingDetailPage } from '@/features/findings/FindingDetailPage';
import { IntentsPage } from '@/features/intents/IntentsPage';
import { DriftEventsPage } from '@/features/drift-events/DriftEventsPage';
import { RemediationPage } from '@/features/remediation/RemediationPage';
import { AuditTrailPage } from '@/features/audit-trail/AuditTrailPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { NotFoundPage } from '@/features/not-found/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
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
        element: <OverviewPage />,
      },
      {
        path: 'architecture',
        element: <ArchitectureExplorerPage />,
      },
      {
        path: 'findings',
        element: <FindingsListPage />,
      },
      {
        path: 'findings/:findingId',
        element: <FindingDetailPage />,
      },
      {
        path: 'intents',
        element: <IntentsPage />,
      },
      {
        path: 'drift-events',
        element: <DriftEventsPage />,
      },
      {
        path: 'remediation',
        element: <RemediationPage />,
      },
      {
        path: 'audit-trail',
        element: <AuditTrailPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
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
