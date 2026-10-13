import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';
import { env } from '@/config/env';

export const worker = setupWorker(...handlers);

export async function enableMocking(): Promise<void> {
  if (!env.useMocks) {
    return;
  }
  await worker.start();
}
