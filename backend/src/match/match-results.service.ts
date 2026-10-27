import { BadRequestException, HttpException, HttpStatus, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Like, MoreThan, Repository } from 'typeorm';
import { ApplicationsService } from '../applications/applications.service';
import { ResumesService } from '../resumes/resumes.service';
import { MatchResult } from './match-result.entity';
import { MatcherName } from './match.dto';
import { MatchService } from './match.service';

const HISTORY_LIMIT = 20;
const DAY_MS = 24 * 60 * 60 * 1000;

function envInt(name: string, fallback: number) {
  const n = Number(process.env[name]);
  return Number.isInteger(n) && n >= 0 ? n : fallback;
}

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
  async run(userId: string, applicationId: string, resumeId: string, matcher: MatcherName = 'keyword') {
    // Both lookups are scoped to the user, so another account's ids return 404.
    const [application, resume] = await Promise.all([
      this.applications.get(userId, applicationId),
      this.resumes.get(userId, resumeId),
    ]);
    if (!application.jobDescription?.trim()) {
      throw new BadRequestException('Add a job description to this application first');
    }

    // Checked after validation so a bad request never uses up quota, and before the paid call.
    if (matcher === 'llm') await this.enforceLlmLimits(userId);

    const ml = await this.matcher.match({ resumeText: resume.text, jobDescription: application.jobDescription, matcher });

    return this.repo.save(
      this.repo.create({
        userId,
        applicationId: application.id,
        resumeId: resume.id,
        resumeFilename: resume.filename,
        matcher: ml.matcher,
        score: ml.score,
        result: { requirements: ml.requirements, missing: ml.missing, meta: { ungrounded: ml.ungrounded, usage: ml.usage, docSimilarity: ml.doc_similarity } },
      }),
    );
  }

  /**
   * LLM matches cost real money and anyone can register, so cap them per user and overall per rolling 24 h.
   * Counts saved results (no extra infrastructure). Small overshoot under concurrent requests is acceptable.
   */
  private async enforceLlmLimits(userId: string) {
    const since = MoreThan(new Date(Date.now() - DAY_MS));
    const llm = Like('llm:%');
    const userLimit = envInt('LLM_MATCH_DAILY_LIMIT', 10);
    const globalLimit = envInt('LLM_MATCH_GLOBAL_DAILY_LIMIT', 100);

    const [mine, everyone] = await Promise.all([
      this.repo.count({ where: { userId, matcher: llm, createdAt: since } }),
      this.repo.count({ where: { matcher: llm, createdAt: since } }),
    ]);
    if (mine >= userLimit) {
      throw new HttpException(
        `Daily AI match limit reached (${userLimit} per 24 hours). Use the keyword matcher or try again tomorrow.`,
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }
    if (everyone >= globalLimit) {
      throw new HttpException(
        'The AI matcher has reached its daily capacity. Use the keyword matcher or try again tomorrow.',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }
  }

  async list(userId: string, applicationId: string) {
    await this.applications.get(userId, applicationId); // 404 if it is not the user's application
    return this.repo.find({ where: { userId, applicationId }, order: { createdAt: 'DESC' }, take: HISTORY_LIMIT });
  }
}
