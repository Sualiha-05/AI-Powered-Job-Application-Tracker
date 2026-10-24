/** Headers the backend sends to the ML service. Adds the shared secret when ML_API_KEY is set. */
export function mlAuthHeaders(): Record<string, string> {
  const key = process.env.ML_API_KEY;
  return key ? { 'X-API-Key': key } : {};
}

/** Milliseconds to wait for the ML service before giving up (a clean 502 beats a platform timeout). */
export function mlTimeoutMs(): number {
  const n = Number(process.env.ML_TIMEOUT_MS);
  return Number.isFinite(n) && n > 0 ? n : 25_000;
}
