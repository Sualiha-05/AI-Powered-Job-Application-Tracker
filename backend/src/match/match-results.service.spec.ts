import { BadRequestException, NotFoundException } from '@nestjs/common';
import { MatchResultsService } from './match-results.service';

const ML = {
  matcher: 'keyword-baseline',
  score: 0.5,
  requirements: [{ requirement: 'Python', supported: true, evidence: [{ line: 'Python dev', line_number: 1 }] }],
  missing: ['Kubernetes'],
};

function setup(opts: { jd?: string | null; appGet?: jest.Mock; resumeGet?: jest.Mock } = {}) {
  const repo = {
    create: jest.fn((x) => x),
    save: jest.fn(async (x) => ({ id: 'm1', createdAt: new Date(), ...x })),
    find: jest.fn(async () => []),
    count: jest.fn(async (_arg?: any): Promise<number> => 0),
  };
  const applications = {
    get: opts.appGet ?? jest.fn(async () => ({ id: 'a1', jobDescription: opts.jd === undefined ? 'Python, Kubernetes' : opts.jd })),
  };
  const resumes = { get: opts.resumeGet ?? jest.fn(async () => ({ id: 'r1', filename: 'cv.pdf', text: 'Python dev' })) };
  const matcher = { match: jest.fn(async (_dto?: any): Promise<any> => ML) };
  const service = new MatchResultsService(repo as any, resumes as any, applications as any, matcher as any);
  return { service, repo, applications, resumes, matcher };
}

describe('MatchResultsService', () => {
  it('runs the matcher on the stored texts and saves the result with a filename snapshot', async () => {
    const { service, repo, matcher } = setup();
    const saved = await service.run('u1', 'a1', 'r1');

    expect(matcher.match).toHaveBeenCalledWith({ resumeText: 'Python dev', jobDescription: 'Python, Kubernetes', matcher: 'keyword' });
    expect(repo.save).toHaveBeenCalledWith(
      expect.objectContaining({
        userId: 'u1',
        applicationId: 'a1',
        resumeId: 'r1',
        resumeFilename: 'cv.pdf',
        matcher: 'keyword-baseline',
        score: 0.5,
        result: expect.objectContaining({ requirements: ML.requirements, missing: ['Kubernetes'] }),
      }),
    );
    expect(saved.id).toBe('m1');
  });

  it('rejects an application without a job description and does not call the matcher', async () => {
    for (const jd of [null, '', '   ']) {
      const { service, matcher, repo } = setup({ jd });
      await expect(service.run('u1', 'a1', 'r1')).rejects.toBeInstanceOf(BadRequestException);
      expect(matcher.match).not.toHaveBeenCalled();
      expect(repo.save).not.toHaveBeenCalled();
    }
  });

  it("looks everything up scoped to the user (another user's ids give 404 before any ML call)", async () => {
    const appGet = jest.fn(async () => {
      throw new NotFoundException();
    });
    const { service, matcher } = setup({ appGet });
    await expect(service.run('u2', 'a1', 'r1')).rejects.toBeInstanceOf(NotFoundException);
    expect(appGet).toHaveBeenCalledWith('u2', 'a1');
    expect(matcher.match).not.toHaveBeenCalled();
  });

  it('lists history only after confirming the application belongs to the user', async () => {
    const { service, repo, applications } = setup();
    await service.list('u1', 'a1');
    expect(applications.get).toHaveBeenCalledWith('u1', 'a1');
    expect(repo.find).toHaveBeenCalledWith(expect.objectContaining({ where: { userId: 'u1', applicationId: 'a1' }, take: 20 }));
  });

  describe('LLM matcher', () => {
    afterEach(() => {
      delete process.env.LLM_MATCH_DAILY_LIMIT;
      delete process.env.LLM_MATCH_GLOBAL_DAILY_LIMIT;
    });

    it('passes the matcher through and saves its name and meta', async () => {
      const { service, matcher, repo } = setup();
      matcher.match.mockResolvedValueOnce({ ...ML, matcher: 'llm:claude-haiku-5-5', ungrounded: 1, usage: { input_tokens: 5, output_tokens: 2 } });
      await service.run('u1', 'a1', 'r1', 'llm');
      expect(matcher.match).toHaveBeenCalledWith(expect.objectContaining({ matcher: 'llm' }));
      expect(repo.save).toHaveBeenCalledWith(
        expect.objectContaining({
          matcher: 'llm:claude-haiku-5-5',
          result: expect.objectContaining({ meta: { ungrounded: 1, usage: { input_tokens: 5, output_tokens: 2 } } }),
        }),
      );
    });

    it('rejects with 429 once the per-user daily limit is reached, before any paid call', async () => {
      process.env.LLM_MATCH_DAILY_LIMIT = '2';
      const { service, repo, matcher } = setup();
      repo.count.mockImplementation(async (arg: any) => (arg.where.userId ? 2 : 2));
      await expect(service.run('u1', 'a1', 'r1', 'llm')).rejects.toMatchObject({ status: 429 });
      expect(matcher.match).not.toHaveBeenCalled();
      expect(repo.save).not.toHaveBeenCalled();
    });

    it('rejects with 429 when the global daily capacity is reached', async () => {
      process.env.LLM_MATCH_GLOBAL_DAILY_LIMIT = '5';
      const { service, repo, matcher } = setup();
      repo.count.mockImplementation(async (arg: any) => (arg.where.userId ? 0 : 5));
      await expect(service.run('u1', 'a1', 'r1', 'llm')).rejects.toMatchObject({ status: 429 });
      expect(matcher.match).not.toHaveBeenCalled();
    });

    it('allows a match just under the limit', async () => {
      process.env.LLM_MATCH_DAILY_LIMIT = '2';
      const { service, repo } = setup();
      repo.count.mockResolvedValue(1);
      await expect(service.run('u1', 'a1', 'r1', 'llm')).resolves.toBeDefined();
    });

    it('never counts or limits keyword matches', async () => {
      const { service, repo } = setup();
      await service.run('u1', 'a1', 'r1', 'keyword');
      expect(repo.count).not.toHaveBeenCalled();
    });

    it('does not use up quota when the request itself is invalid (no job description)', async () => {
      const { service, repo } = setup({ jd: null });
      await expect(service.run('u1', 'a1', 'r1', 'llm')).rejects.toBeInstanceOf(BadRequestException);
      expect(repo.count).not.toHaveBeenCalled();
    });
  });

  describe('TF-IDF matcher', () => {
    it('passes the matcher through, stores the document similarity, and is never rate limited', async () => {
      process.env.LLM_MATCH_DAILY_LIMIT = '0';
      try {
        const { service, matcher, repo } = setup();
        matcher.match.mockResolvedValueOnce({ ...ML, matcher: 'tfidf-overlap', doc_similarity: 0.42 });
        await service.run('u1', 'a1', 'r1', 'tfidf');
        expect(matcher.match).toHaveBeenCalledWith(expect.objectContaining({ matcher: 'tfidf' }));
        expect(repo.count).not.toHaveBeenCalled();
        expect(repo.save).toHaveBeenCalledWith(
          expect.objectContaining({
            matcher: 'tfidf-overlap',
            result: expect.objectContaining({ meta: expect.objectContaining({ docSimilarity: 0.42 }) }),
          }),
        );
      } finally {
        delete process.env.LLM_MATCH_DAILY_LIMIT;
      }
    });
  });
});
