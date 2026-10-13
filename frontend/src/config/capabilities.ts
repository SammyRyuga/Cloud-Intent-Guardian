import { env } from './env';

/**
 * Capability flags per AGENTS.md §8
 * In mock mode or dev, all flags are supported/enabled.
 */
export function hasCapability(feature: string): boolean {
  if (env.useMocks) {
    return true;
  }
  return env.features.includes(feature) || env.features.includes('*');
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
