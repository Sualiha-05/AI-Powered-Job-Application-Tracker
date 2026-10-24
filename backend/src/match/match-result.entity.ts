import { Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn } from 'typeorm';
import { Application } from '../applications/application.entity';
import { Resume } from '../resumes/resume.entity';

export interface MatchEvidence {
  line: string;
  line_number: number;
}

export interface MatchRequirement {
  requirement: string;
  supported: boolean;
  evidence: MatchEvidence[];
}

@Entity('match_results')
export class MatchResult {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index()
  @Column({ type: 'uuid' })
  userId: string;

  // Deleting an application deletes its match history.
  @Index()
  @Column({ type: 'uuid' })
  applicationId: string;

  @ManyToOne(() => Application, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'applicationId' })
  application?: Application;

  // Deleting a resume keeps old results; the filename below remembers which resume was used.
  @Column({ type: 'uuid', nullable: true })
  resumeId: string | null;

  @ManyToOne(() => Resume, { onDelete: 'SET NULL', nullable: true })
  @JoinColumn({ name: 'resumeId' })
  resume?: Resume | null;

  @Column()
  resumeFilename: string;

  // Which matcher produced this result, e.g. "keyword-baseline". Lets you compare matchers later.
  @Column()
  matcher: string;

  @Column({ type: 'float' })
  score: number;

  @Column({ type: 'jsonb' })
  result: { requirements: MatchRequirement[]; missing: string[] };

  @CreateDateColumn()
  createdAt: Date;
}
