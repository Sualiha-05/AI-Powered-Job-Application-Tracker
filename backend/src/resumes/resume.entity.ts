import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('resumes')
export class Resume {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index()
  @Column()
  userId: string;

  @Column()
  filename: string;

  // Plain text extracted at upload time. Line breaks are kept because the
  // matcher cites individual resume lines as evidence.
  @Column({ type: 'text' })
  text: string;

  @CreateDateColumn()
  createdAt: Date;
}
