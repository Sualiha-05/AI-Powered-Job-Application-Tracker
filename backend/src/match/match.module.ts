import { HttpModule } from '@nestjs/axios';
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ApplicationsModule } from '../applications/applications.module';
import { ResumesModule } from '../resumes/resumes.module';
import { MatchResult } from './match-result.entity';
import { MatchResultsController } from './match-results.controller';
import { MatchResultsService } from './match-results.service';
import { MatchController } from './match.controller';
import { MatchService } from './match.service';

@Module({
  imports: [TypeOrmModule.forFeature([MatchResult]), HttpModule, ResumesModule, ApplicationsModule],
  controllers: [MatchController, MatchResultsController],
  providers: [MatchService, MatchResultsService],
})
export class MatchModule {}
