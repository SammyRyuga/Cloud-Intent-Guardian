import { hasCapability } from '@/config/capabilities';
import { useSystemStatus } from '@/hooks/apiHooks';

export function useCapability(feature: string): boolean {
  const { data: status } = useSystemStatus();
  return hasCapability(feature, status);
}
