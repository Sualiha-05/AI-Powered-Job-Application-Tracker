import { IsString, IsUUID, MinLength } from 'class-validator';

export class MatchDto {
  @IsString() @MinLength(1) resumeText: string;
  @IsString() @MinLength(1) jobDescription: string;
}

export class MatchByIdsDto {
  @IsUUID() resumeId: string;
  @IsUUID() applicationId: string;
}
