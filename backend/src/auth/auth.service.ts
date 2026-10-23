import { ConflictException, Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { UsersService } from '../users/users.service';
import { CredentialsDto } from './auth.dto';

@Injectable()
export class AuthService {
  constructor(
    private readonly users: UsersService,
    private readonly jwt: JwtService,
  ) {}

  async register({ email, password }: CredentialsDto) {
    if (await this.users.findByEmail(email)) {
      throw new ConflictException('Email already registered');
    }
    const user = await this.users.create(email, await bcrypt.hash(password, 10));
    return this.token(user.id, user.email);
  }

  async login({ email, password }: CredentialsDto) {
    const user = await this.users.findByEmail(email);
    if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
      throw new UnauthorizedException('Invalid email or password');
    }
    return this.token(user.id, user.email);
  }

  private token(id: string, email: string) {
    return { accessToken: this.jwt.sign({ sub: id, email }) };
  }
}
