import { NotFoundException } from '@nestjs/common';
import { ApplicationsService } from './applications.service';

describe('ApplicationsService', () => {
  it('scopes lookups by userId and throws when not found', async () => {
    const findOne = jest.fn().mockResolvedValue(null);
    const service = new ApplicationsService({ findOne } as any);

    await expect(service.get('user-1', 'app-1')).rejects.toBeInstanceOf(NotFoundException);
    expect(findOne).toHaveBeenCalledWith({ where: { id: 'app-1', userId: 'user-1' } });
  });
});
