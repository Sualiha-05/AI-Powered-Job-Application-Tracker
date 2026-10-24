import { IsUUID } from 'class-validator';

export class RunMatchDto {
  @IsUUID() resumeId: string;
}
