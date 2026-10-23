import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ApplicationsModule } from './applications/applications.module';
import { AuthModule } from './auth/auth.module';
import { HealthController } from './health/health.controller';
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
      entities: [User, Application, Resume],
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
