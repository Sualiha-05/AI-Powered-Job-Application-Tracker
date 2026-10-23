import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { AuthUser, CurrentUser } from '../auth/current-user.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { MatchByIdsDto, MatchDto } from './match.dto';
import { MatchService } from './match.service';

@UseGuards(JwtAuthGuard)
@Controller('match')
export class MatchController {
  constructor(private readonly service: MatchService) {}

  @Post()
  match(@Body() dto: MatchDto) {
    return this.service.match(dto);
  }

  @Post('by-ids')
  matchByIds(@CurrentUser() user: AuthUser, @Body() dto: MatchByIdsDto) {
    return this.service.matchByIds(user.userId, dto);
  }
}
