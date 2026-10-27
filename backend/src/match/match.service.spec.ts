import { BadGatewayException, ServiceUnavailableException, UnprocessableEntityException } from '@nestjs/common';
import { of, throwError } from 'rxjs';
import { MatchService } from './match.service';

const dto = { resumeText: 'r', jobDescription: 'j' };
const svc = (post: jest.Mock) => new MatchService({ post } as any, {} as any, {} as any);

describe('MatchService', () => {
  it("sends matcher 'keyword' by default and 'llm' when asked", async () => {
    const post = jest.fn(() => of({ data: { ok: true } }));
    await svc(post).match(dto);
    await svc(post).match({ ...dto, matcher: 'llm' });
    expect((post.mock.calls[0] as any[])[1]).toMatchObject({ matcher: 'keyword', resume_text: 'r', job_description: 'j' });
    expect((post.mock.calls[1] as any[])[1]).toMatchObject({ matcher: 'llm' });
  });

  it("passes the 'tfidf' matcher through to the ML service", async () => {
    const post = jest.fn(() => of({ data: { ok: true } }));
    await svc(post).match({ ...dto, matcher: 'tfidf' });
    expect((post.mock.calls[0] as any[])[1]).toMatchObject({ matcher: 'tfidf' });
  });

  it('maps ML 503 to a neutral 503 that does not leak setup details', async () => {
    const post = jest.fn(() => throwError(() => ({ response: { status: 503, data: { detail: 'set ANTHROPIC_API_KEY' } } })));
    const err: any = await svc(post).match(dto).catch((e) => e);
    expect(err).toBeInstanceOf(ServiceUnavailableException);
    expect(JSON.stringify(err.getResponse())).not.toContain('ANTHROPIC');
  });

  it('passes through ML 422 messages such as "text too long"', async () => {
    const post = jest.fn(() => throwError(() => ({ response: { status: 422, data: { detail: 'Text too long' } } })));
    await expect(svc(post).match(dto)).rejects.toBeInstanceOf(UnprocessableEntityException);
  });

  it('shows safe AI-provider failure details (for example a quota error) instead of a generic message', async () => {
    const post = jest.fn(() => throwError(() => ({ response: { status: 502, data: { detail: 'LLM request failed (ClientError 429)' } } })));
    const err: any = await svc(post).match(dto).catch((e) => e);
    expect(err).toBeInstanceOf(BadGatewayException);
    expect(err.message).toBe('The AI provider returned an error: (ClientError 429)');
  });

  it('keeps other 502 details from the ML service private', async () => {
    const post = jest.fn(() => throwError(() => ({ response: { status: 502, data: { detail: 'something internal' } } })));
    const err: any = await svc(post).match(dto).catch((e) => e);
    expect(err.message).toBe('ML service unavailable');
  });

  it('turns anything else into a 502', async () => {
    const post = jest.fn(() => throwError(() => new Error('boom')));
    await expect(svc(post).match(dto)).rejects.toBeInstanceOf(BadGatewayException);
  });
});
