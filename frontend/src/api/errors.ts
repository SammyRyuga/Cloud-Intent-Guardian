export class ApiError extends Error {
  readonly kind: 'network' | 'validation' | 'auth' | 'forbidden' | 'not_found' | 'conflict' | 'rate_limited' | 'server' | 'contract';
  readonly code: string;
  readonly requestId?: string;
  readonly status?: number;
  readonly details?: Record<string, string>;

  constructor(args: {
    message: string;
    kind: 'network' | 'validation' | 'auth' | 'forbidden' | 'not_found' | 'conflict' | 'rate_limited' | 'server' | 'contract';
    code: string;
    requestId?: string;
    status?: number;
    details?: Record<string, string>;
  }) {
    super(args.message);
    this.name = 'ApiError';
    this.kind = args.kind;
    this.code = args.code;
    this.requestId = args.requestId;
    this.status = args.status;
    this.details = args.details;
  }
}
