import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

// MSW's worker is required by the local development server only. Public assets
// are copied by Vite, so remove the worker from deployable production output.
rmSync(resolve('dist/mockServiceWorker.js'), { force: true });
