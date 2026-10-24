import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ApplicationsModule } from './applications/applications.module';
import { AuthModule } from './auth/auth.module';
import { HealthController } from './health/health.controller';
import { MatchResult } from './match/match-result.entity';
import { MatchModule } from './match/match.module';
import { Resume } from './resumes/resume.entity';
import { ResumesModule } from './resumes/resumes.module';
import { User } from './users/user.entity';
import { Application } from './applications/application.entity';
import { UsersModule } from './users/users.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      // Managed Postgres (e.g. Neon) requires SSL: set DB_SSL=true there.
      ssl: process.env.DB_SSL === 'true',
      // Serverless: every function instance opens its own connections, so keep the pool small
      // and release idle ones quickly. Use Neon's *pooled* connection string (host contains "-pooler").
      extra: {
        max: Number(process.env.DB_POOL_MAX ?? 3),
        idleTimeoutMillis: 10_000,
        connectionTimeoutMillis: 10_000,
      },
      entities: [User, Application, Resume, MatchResult],
      // Tables are auto-created in dev. In production set DB_SYNCHRONIZE=true for the
      // FIRST deploy only, then remove it and move to migrations before real users arrive.
      synchronize: process.env.DB_SYNCHRONIZE === 'true' || process.env.NODE_ENV !== 'production',
    }),
    UsersModule,
    AuthModule,
    ApplicationsModule,
    ResumesModule,
    MatchModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}
