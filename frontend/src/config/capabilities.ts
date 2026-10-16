import { env } from './env';
import type { SystemStatus } from '@/types/domain';

/**
 * Capability flags per AGENTS.md §8
 * Mock mode supports fixtures; the local API uses only advertised server features.
 */
export function hasCapability(feature: string, status?: SystemStatus): boolean {
  if (env.useMocks) {
    return true;
  }
  if (feature === 'driftEvents') return status?.features?.driftEvents === true;
  // Live controls are exposed only for handlers wired in this API version.
  // Role and scope authorization remains authoritative on the backend.
  const implementedLive = [
    'architecture', 'evaluations', 'auditTrail', 'remediation', 'remediation.detail',
    'remediation.approve', 'remediation.execute', 'findings.update', 'findings.suppress', 'findings.reopen', 'intents.approve', 'intents.diff',
  ];
  if (!env.localApi) return feature === 'intents' || implementedLive.includes(feature);
  if (feature === 'intents' || feature === 'auditTrail' || ['findings.update', 'findings.suppress', 'findings.reopen'].includes(feature)) return true;
  if (['intents.approve', 'intents.diff'].includes(feature)) return status?.features?.fixtureInventory === true;
  if (feature === 'architecture') return status?.features?.topology === true;
  if (['remediation', 'remediation.detail', 'remediation.approve', 'remediation.execute'].includes(feature)) {
    return status?.features?.remediationProposals === true;
  }
  // Local evaluation remains unavailable until the backend exposes an explicit capability.
  return feature === 'evaluations' && status?.features?.evaluations === true;
}

export const CAPABILITIES = {
  evaluations: 'evaluations',
  architecture: 'architecture',
  findingsUpdate: 'findings.update',
  findingsSuppress: 'findings.suppress',
  findingsReopen: 'findings.reopen',
  findingsQuery: 'findings.query',
  intents: 'intents',
  intentsUpload: 'intents.upload',
  intentsApprove: 'intents.approve',
  intentsDiff: 'intents.diff',
  driftEvents: 'driftEvents',
  explanationsGenerate: 'explanations.generate',
  remediation: 'remediation',
  remediationDetail: 'remediation.detail',
  remediationCancel: 'remediation.cancel',
  auditTrail: 'auditTrail',
} as const;
