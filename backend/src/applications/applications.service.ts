import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Application } from './application.entity';
import { CreateApplicationDto, UpdateApplicationDto } from './applications.dto';

@Injectable()
export class ApplicationsService {
  constructor(@InjectRepository(Application) private readonly repo: Repository<Application>) {}

  list(userId: string) {
    return this.repo.find({ where: { userId }, order: { updatedAt: 'DESC' } });
  }

  create(userId: string, dto: CreateApplicationDto) {
    return this.repo.save(this.repo.create({ ...dto, userId }));
  }

  async get(userId: string, id: string) {
    // Always scope by userId so users can never read each other's data.
    const app = await this.repo.findOne({ where: { id, userId } });
    if (!app) throw new NotFoundException('Application not found');
    return app;
  }

  async update(userId: string, id: string, dto: UpdateApplicationDto) {
    const app = await this.get(userId, id);
    Object.assign(app, dto);
    return this.repo.save(app);
  }

  async remove(userId: string, id: string) {
    const app = await this.get(userId, id);
    await this.repo.remove(app);
    return { deleted: true };
  }
}
