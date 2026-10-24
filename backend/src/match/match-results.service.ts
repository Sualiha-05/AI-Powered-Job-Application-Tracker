import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ApplicationsService } from '../applications/applications.service';
import { ResumesService } from '../resumes/resumes.service';
import { MatchResult } from './match-result.entity';
import { MatchService } from './match.service';

const HISTORY_LIMIT = 20;

@Injectable()
export class MatchResultsService {
  constructor(
    @InjectRepository(MatchResult) private readonly repo: Repository<MatchResult>,
    private readonly resumes: ResumesService,
    private readonly applications: ApplicationsService,
    private readonly matcher: MatchService,
  ) {}

  /**
   * Runs the match inside this request and saves the result. Serverless functions cannot keep
   * working after the response is sent, so there is no "pending" state: the caller waits.
   */
  async run(userId: string, applicationId: string, resumeId: string) {
    // Both lookups are scoped to the user, so another account's ids return 404.
    const [application, resume] = await Promise.all([
      this.applications.get(userId, applicationId),
      this.resumes.get(userId, resumeId),
    ]);
    if (!application.jobDescription?.trim()) {
      throw new BadRequestException('Add a job description to this application first');
    }

    const ml = await this.matcher.match({ resumeText: resume.text, jobDescription: application.jobDescription });

    return this.repo.save(
      this.repo.create({
        userId,
        applicationId: application.id,
        resumeId: resume.id,
        resumeFilename: resume.filename,
        matcher: ml.matcher,
        score: ml.score,
        result: { requirements: ml.requirements, missing: ml.missing },
      }),
    );
  }

  async list(userId: string, applicationId: string) {
    await this.applications.get(userId, applicationId); // 404 if it is not the user's application
    return this.repo.find({ where: { userId, applicationId }, order: { createdAt: 'DESC' }, take: HISTORY_LIMIT });
  }
}
