import { IsIn, IsOptional, IsString, IsUUID, MinLength } from 'class-validator';

export const MATCHERS = ['keyword', 'tfidf', 'llm'] as const;
export type MatcherName = (typeof MATCHERS)[number];

export class MatchDto {
  @IsString() @MinLength(1) resumeText: string;
  @IsString() @MinLength(1) jobDescription: string;
  @IsOptional() @IsIn(MATCHERS) matcher?: MatcherName;
}

export class MatchByIdsDto {
  @IsUUID() resumeId: string;
  @IsUUID() applicationId: string;
}
