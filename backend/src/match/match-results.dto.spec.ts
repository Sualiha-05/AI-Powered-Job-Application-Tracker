import { validate } from 'class-validator';
import { plainToInstance } from 'class-transformer';
import { RunMatchDto } from './match-results.dto';

const ID = '3f2b8c1e-5d4a-4c6e-9b7a-1a2b3c4d5e6f';
const errorsFor = async (body: object) => (await validate(plainToInstance(RunMatchDto, body))).map((e) => e.property);

describe('RunMatchDto', () => {
  it.each(['keyword', 'tfidf', 'llm'])('accepts matcher %s', async (matcher) => {
    expect(await errorsFor({ resumeId: ID, matcher })).toEqual([]);
  });

  it('matcher is optional', async () => {
    expect(await errorsFor({ resumeId: ID })).toEqual([]);
  });

  it('rejects unknown matchers and bad ids', async () => {
    expect(await errorsFor({ resumeId: ID, matcher: 'gpt' })).toEqual(['matcher']);
    expect(await errorsFor({ resumeId: 'nope' })).toEqual(['resumeId']);
  });
});
