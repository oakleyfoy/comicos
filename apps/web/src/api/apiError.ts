export class ApiError extends Error {
  status: number;
  /** Structured API error payload (e.g. Midtown HTML import diagnostics). */
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// Render redeploy marker: harmless no-op change.
