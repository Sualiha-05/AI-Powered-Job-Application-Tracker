import { IsIn, IsOptional, IsUUID } from 'class-validator';
import { MATCHERS, MatcherName } from './match.dto';

export class RunMatchDto {
  @IsUUID() resumeId: string;
  // 'keyword' (default, free), 'tfidf' (free) or 'llm' (AI provider; limited per day)
  @IsOptional() @IsIn(MATCHERS) matcher?: MatcherName;
}
