import { HttpService } from '@nestjs/axios';
import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  NotFoundException,
  UnprocessableEntityException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { firstValueFrom } from 'rxjs';
import { Repository } from 'typeorm';
import { mlAuthHeaders, mlTimeoutMs } from '../common/ml-headers';
import { Resume } from './resume.entity';

// Vercel Functions document a 4.5 MB request-body limit, so stay under it.
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const MAX_TEXT_CHARS = 100_000;

export interface UploadedFile {
  originalname: string;
  mimetype: string;
  buffer: Buffer;
}

@Injectable()
export class ResumesService {
  private readonly mlUrl = process.env.ML_SERVICE_URL ?? 'http://localhost:8000';

  constructor(
    @InjectRepository(Resume) private readonly repo: Repository<Resume>,
    private readonly http: HttpService,
  ) {}

  async createFromUpload(userId: string, file: UploadedFile | undefined) {
    if (!file || file.buffer.length === 0) {
      throw new BadRequestException('Attach a non-empty file in the "file" field');
    }

    const text = this.normalize(await this.extractText(file));
    if (!text) throw new UnprocessableEntityException('The file contains no text');

    const saved = await this.repo.save(
      this.repo.create({ userId, filename: file.originalname.slice(0, 200), text: text.slice(0, MAX_TEXT_CHARS) }),
    );
    return this.summary(saved);
  }

  async list(userId: string) {
    const rows = await this.repo.find({ where: { userId }, order: { createdAt: 'DESC' } });
    return rows.map((r) => this.summary(r));
  }

  async get(userId: string, id: string) {
    // Always scope by userId so users can never read each other's resumes.
    const row = await this.repo.findOne({ where: { id, userId } });
    if (!row) throw new NotFoundException('Resume not found');
    return row;
  }

  async remove(userId: string, id: string) {
    await this.repo.remove(await this.get(userId, id));
    return { deleted: true };
  }

  private summary(r: Resume) {
    return {
      id: r.id,
      filename: r.filename,
      charCount: r.text.length,
      preview: r.text.slice(0, 240),
      createdAt: r.createdAt,
    };
  }

  // private normalize(text: string) {
  //   return text.replace(/\r\n?/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  // }

  private normalize(text: string | undefined | null): string {
  if (typeof text !== 'string') {
    throw new UnprocessableEntityException(
      'Could not extract text from this resume. Please try another PDF or TXT file.',
    );
  }

  return text
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

  private async extractText(file: UploadedFile): Promise<string> {
    // Decide by content, not by the filename or the browser-supplied MIME type.
    if (file.buffer.subarray(0, 5).toString('latin1') === '%PDF-') {
      return this.parsePdf(file.buffer);
    }
    const looksLikeText = file.mimetype === 'text/plain' || file.originalname.toLowerCase().endsWith('.txt');
    if (looksLikeText && !file.buffer.includes(0)) {
      return file.buffer.toString('utf8');
    }
    throw new BadRequestException('Only PDF or plain-text (.txt) resumes are supported');
  }

//   private async parsePdf(buffer: Buffer): Promise<string> {
//     try {
//       const res = await firstValueFrom(
//         this.http.post<{ text: string }>(`${this.mlUrl}/parse/pdf`, buffer, {
//           headers: { 'Content-Type': 'application/pdf', ...mlAuthHeaders() },
//           maxBodyLength: MAX_UPLOAD_BYTES * 2,
//           timeout: mlTimeoutMs(),
//         }),
//       );
//       return res.data.text;
//     } catch (err: any) {
//       const status = err?.response?.status;
//       const detail = err?.response?.data?.detail;
//       if ((status === 400 || status === 422) && typeof detail === 'string') {
//         throw new UnprocessableEntityException(detail);
//       }
//       throw new BadGatewayException('PDF parsing service unavailable');
//     }
//   }
// }

private async parsePdf(buffer: Buffer): Promise<string> {
  try {
    const res = await firstValueFrom(
      this.http.post<{ text: string }>(
        `${this.mlUrl}/parse/pdf`,
        buffer,
        {
          headers: {
            'Content-Type': 'application/pdf',
            ...mlAuthHeaders(),
          },
          maxBodyLength: MAX_UPLOAD_BYTES * 2,
          timeout: mlTimeoutMs(),
        },
      ),
    );

    const text = res.data?.text;

    if (typeof text !== 'string') {
      throw new BadGatewayException(
        'PDF parsing service returned an invalid response',
      );
    }

    return text;
  } catch (err: any) {
    if (err instanceof BadGatewayException) {
      throw err;
    }

    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;

    if ((status === 400 || status === 422) && typeof detail === 'string') {
      throw new UnprocessableEntityException(detail);
    }

    throw new BadGatewayException('PDF parsing service unavailable');
  }
}
}
