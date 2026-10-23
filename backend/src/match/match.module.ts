import { HttpModule } from '@nestjs/axios';
import { Module } from '@nestjs/common';
import { ApplicationsModule } from '../applications/applications.module';
import { ResumesModule } from '../resumes/resumes.module';
import { MatchController } from './match.controller';
import { MatchService } from './match.service';

@Module({
  imports: [HttpModule, ResumesModule, ApplicationsModule],
  controllers: [MatchController],
  providers: [MatchService],
})
export class MatchModule {}
