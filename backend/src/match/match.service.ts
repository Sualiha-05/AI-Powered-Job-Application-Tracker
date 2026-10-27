import { HttpService } from '@nestjs/axios';
import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
  UnprocessableEntityException,
} from '@nestjs/common';
import { firstValueFrom } from 'rxjs';
import { mlAuthHeaders, mlTimeoutMs } from '../common/ml-headers';
import { ApplicationsService } from '../applications/applications.service';
import { ResumesService } from '../resumes/resumes.service';
import { MatchByIdsDto, MatchDto } from './match.dto';

@Injectable()
export class MatchService {
  private readonly baseUrl = process.env.ML_SERVICE_URL ?? 'http://localhost:8000';

  constructor(
    private readonly http: HttpService,
    private readonly resumes: ResumesService,
    private readonly applications: ApplicationsService,
  ) {}

  // Week 2: move this into a BullMQ job so the request returns immediately.
  async match(dto: MatchDto) {
    try {
      const res = await firstValueFrom(
        this.http.post(
          `${this.baseUrl}/match`,
          { resume_text: dto.resumeText, job_description: dto.jobDescription, matcher: dto.matcher ?? 'keyword' },
          { headers: mlAuthHeaders(), timeout: mlTimeoutMs() },
        ),
      );
      return res.data;
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      // 503 from the ML service means the LLM key is not configured there. Do not leak setup details.
      if (status === 503) throw new ServiceUnavailableException('The AI matcher is not available on this server');
      if (status === 422 && typeof detail === 'string') throw new UnprocessableEntityException(detail);
      // The ML service describes provider failures safely, e.g. "LLM request failed (ClientError 429)" for a quota error.
      if (status === 502 && typeof detail === 'string' && detail.startsWith('LLM request failed')) {
        throw new BadGatewayException(`The AI provider returned an error: ${detail.replace('LLM request failed ', '')}`);
      }
      throw new BadGatewayException('ML service unavailable');
    }
  }

  async matchByIds(userId: string, dto: MatchByIdsDto) {
    // Both lookups are scoped to the user, so ids from other accounts return 404.
    const [resume, application] = await Promise.all([
      this.resumes.get(userId, dto.resumeId),
      this.applications.get(userId, dto.applicationId),
    ]);
    if (!application.jobDescription?.trim()) {
      throw new BadRequestException('Add a job description to this application first');
    }
    return this.match({ resumeText: resume.text, jobDescription: application.jobDescription });
  }
}
