import { BadRequestException, UnprocessableEntityException } from '@nestjs/common';
import { of, throwError } from 'rxjs';
import { ResumesService } from './resumes.service';

function setup(http: any = {}) {
  const repo = {
    create: jest.fn((x) => x),
    save: jest.fn(async (x) => ({ id: 'r1', createdAt: new Date(), ...x })),
  };
  return { repo, service: new ResumesService(repo as any, http) };
}

const file = (name: string, mimetype: string, content: Buffer | string) => ({
  originalname: name,
  mimetype,
  buffer: Buffer.isBuffer(content) ? content : Buffer.from(content),
});

describe('ResumesService', () => {
  it('stores plain-text resumes with line breaks normalized', async () => {
    const { repo, service } = setup();
    const out = await service.createFromUpload('u1', file('cv.txt', 'text/plain', 'Jane\r\n\r\n\r\n\r\nPython  \nDocker'));
    expect(repo.save).toHaveBeenCalledWith(expect.objectContaining({ userId: 'u1', text: 'Jane\n\nPython\nDocker' }));
    expect(out.filename).toBe('cv.txt');
  });

  it('rejects unsupported and binary files', async () => {
    const { service } = setup();
    await expect(service.createFromUpload('u1', file('a.docx', 'application/zip', Buffer.from([0x50, 0x4b, 0, 3])))).rejects.toBeInstanceOf(BadRequestException);
    await expect(service.createFromUpload('u1', undefined)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('detects PDFs by content, not by filename', async () => {
    const post = jest.fn(() => of({ data: { text: 'Parsed text' } }));
    const { repo, service } = setup({ post });
    await service.createFromUpload('u1', file('resume.bin', 'application/octet-stream', '%PDF-1.4 fake'));
    expect(post).toHaveBeenCalled();
    expect(repo.save).toHaveBeenCalledWith(expect.objectContaining({ text: 'Parsed text' }));
  });

  it('turns ML 422 errors into a readable 422', async () => {
    const post = jest.fn(() => throwError(() => ({ response: { status: 422, data: { detail: 'No extractable text found' } } })));
    const { service } = setup({ post });
    await expect(service.createFromUpload('u1', file('s.pdf', 'application/pdf', '%PDF-1.4'))).rejects.toBeInstanceOf(UnprocessableEntityException);
  });

  it('sends the shared secret to the ML service when configured', async () => {
    process.env.ML_API_KEY = 'k1';
    try {
      const post = jest.fn(() => of({ data: { text: 'Parsed text' } }));
      const { service } = setup({ post });
      await service.createFromUpload('u1', file('r.pdf', 'application/pdf', '%PDF-1.4'));
      expect(post).toHaveBeenCalledWith(
        expect.stringContaining('/parse/pdf'),
        expect.any(Buffer),
        expect.objectContaining({ headers: expect.objectContaining({ 'X-API-Key': 'k1', 'Content-Type': 'application/pdf' }) }),
      );
    } finally {
      delete process.env.ML_API_KEY;
    }
  });
});
