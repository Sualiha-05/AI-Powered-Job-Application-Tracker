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
  };
  const applications = {
    get: opts.appGet ?? jest.fn(async () => ({ id: 'a1', jobDescription: opts.jd === undefined ? 'Python, Kubernetes' : opts.jd })),
  };
  const resumes = { get: opts.resumeGet ?? jest.fn(async () => ({ id: 'r1', filename: 'cv.pdf', text: 'Python dev' })) };
  const matcher = { match: jest.fn(async () => ML) };
  const service = new MatchResultsService(repo as any, resumes as any, applications as any, matcher as any);
  return { service, repo, applications, resumes, matcher };
}

describe('MatchResultsService', () => {
  it('runs the matcher on the stored texts and saves the result with a filename snapshot', async () => {
    const { service, repo, matcher } = setup();
    const saved = await service.run('u1', 'a1', 'r1');

    expect(matcher.match).toHaveBeenCalledWith({ resumeText: 'Python dev', jobDescription: 'Python, Kubernetes' });
    expect(repo.save).toHaveBeenCalledWith(
      expect.objectContaining({
        userId: 'u1',
        applicationId: 'a1',
        resumeId: 'r1',
        resumeFilename: 'cv.pdf',
        matcher: 'keyword-baseline',
        score: 0.5,
        result: { requirements: ML.requirements, missing: ['Kubernetes'] },
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
});
