import { Project } from './project.model';
import { Material } from './material.model';
import { User } from './user.model';


export interface POEntry {
  id: number;
  project_id: number;
  material_id: number;
  supplier_name: string;
  invoice_no: string;
  quantity: number;
  unit_price: number;
  total_cost: number;
  po_date: Date;
  delivery_date?: Date;
  remarks?: string;
  created_by: number;
  created_at: Date;
  project?: Project;
  material?: Material;
  user?: User;
}

export interface POEntryCreateRequest {
  project_id: number;
  material_id: number;
  supplier_name: string;
  invoice_no: string;
  quantity: number;
  unit_price: number;
  total_cost: number;
  po_date?: Date;
  delivery_date?: Date;
  remarks?: string;
}
