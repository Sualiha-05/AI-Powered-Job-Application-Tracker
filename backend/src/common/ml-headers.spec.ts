import { mlAuthHeaders } from './ml-headers';

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
