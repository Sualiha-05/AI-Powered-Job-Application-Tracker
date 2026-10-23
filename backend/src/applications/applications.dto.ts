import { IsEnum, IsOptional, IsString, IsUrl, MinLength } from 'class-validator';
import { ApplicationStatus } from './application.entity';

export class CreateApplicationDto {
  @IsString() @MinLength(1) company: string;
  @IsString() @MinLength(1) title: string;
  @IsOptional() @IsEnum(ApplicationStatus) status?: ApplicationStatus;
  @IsOptional() @IsString() jobDescription?: string;
  @IsOptional() @IsString() notes?: string;
  @IsOptional() @IsUrl() url?: string;
}

export class UpdateApplicationDto {
  @IsOptional() @IsString() @MinLength(1) company?: string;
  @IsOptional() @IsString() @MinLength(1) title?: string;
  @IsOptional() @IsEnum(ApplicationStatus) status?: ApplicationStatus;
  @IsOptional() @IsString() jobDescription?: string;
  @IsOptional() @IsString() notes?: string;
  @IsOptional() @IsUrl() url?: string;
}
