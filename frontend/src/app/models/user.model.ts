import { Project } from './project.model';

export enum UserRole {
  ADMIN = 'admin',
  OWNER = 'owner',
  USER = 'user'
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  created_at: Date;
  updated_at?: Date;
  projects?: Project[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  role?: UserRole;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}
