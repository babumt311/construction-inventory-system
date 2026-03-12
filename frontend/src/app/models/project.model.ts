import { User } from './user.model';

export interface Project {
  id: number;
  name: string;
  code: string;
  description?: string;
  start_date?: Date;
  end_date?: Date;
  status: string;
  created_at: Date;
  updated_at?: Date;
  users?: User[];
  sites?: Site[];
  client?: string;
  budget?: number;
  progress?: number;
  team_members?: User[];
}

export interface Site {
  id: number;
  name: string;
  project_id: number;
  code?: string;
  location?: string;
  manager?: string;
  status: string;
  created_at: Date;
  updated_at?: Date;
  project?: Project;
}

export interface ProjectCreateRequest {
  name: string;
  code: string;
  description?: string;
  start_date?: Date;
  end_date?: Date;
  status?: string;
  user_ids?: number[];
}
