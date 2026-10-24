import { Body, Controller, Get, Param, ParseUUIDPipe, Post, UseGuards } from '@nestjs/common';
import { AuthUser, CurrentUser } from '../auth/current-user.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { RunMatchDto } from './match-results.dto';
import { MatchResultsService } from './match-results.service';

@UseGuards(JwtAuthGuard)
@Controller('applications/:applicationId/matches')
export class MatchResultsController {
  constructor(private readonly service: MatchResultsService) {}

  @Post()
  run(
    @CurrentUser() user: AuthUser,
    @Param('applicationId', ParseUUIDPipe) applicationId: string,
    @Body() dto: RunMatchDto,
  ) {
    return this.service.run(user.userId, applicationId, dto.resumeId);
  }

  @Get()
  list(@CurrentUser() user: AuthUser, @Param('applicationId', ParseUUIDPipe) applicationId: string) {
    return this.service.list(user.userId, applicationId);
  }
}
