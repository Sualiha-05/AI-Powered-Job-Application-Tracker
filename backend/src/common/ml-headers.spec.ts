import { mlAuthHeaders, mlTimeoutMs } from './ml-headers';

describe('mlAuthHeaders', () => {
  const original = process.env.ML_API_KEY;
  afterEach(() => {
    if (original === undefined) delete process.env.ML_API_KEY;
    else process.env.ML_API_KEY = original;
  });

  it('adds X-API-Key when ML_API_KEY is set', () => {
    process.env.ML_API_KEY = 'abc';
    expect(mlAuthHeaders()).toEqual({ 'X-API-Key': 'abc' });
  });

  it('adds nothing when it is not set', () => {
    delete process.env.ML_API_KEY;
    expect(mlAuthHeaders()).toEqual({});
  });
});

describe('mlTimeoutMs', () => {
  afterEach(() => delete process.env.ML_TIMEOUT_MS);

  it('defaults to 25 s and accepts an override', () => {
    expect(mlTimeoutMs()).toBe(25_000);
    process.env.ML_TIMEOUT_MS = '8000';
    expect(mlTimeoutMs()).toBe(8000);
  });

  it('ignores invalid values', () => {
    process.env.ML_TIMEOUT_MS = 'abc';
    expect(mlTimeoutMs()).toBe(25_000);
  });
});
