/** Headers the backend sends to the ML service. Adds the shared secret when ML_API_KEY is set. */
export function mlAuthHeaders(): Record<string, string> {
  const key = process.env.ML_API_KEY;
  return key ? { 'X-API-Key': key } : {};
}
