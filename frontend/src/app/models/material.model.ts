export interface Category {
  id: number;
  name: string;
  description?: string;
  created_at: Date;
}

export interface Material {
  id: number;
  name: string;
  category_id: number;
  unit?: string;
  description?: string;
  standard_cost?: number;
  created_at: Date;
  updated_at?: Date;
  category?: Category;
}

export interface MaterialCreateRequest {
  name: string;
  category_id: number;
  unit?: string;
  description?: string;
  standard_cost?: number;
}
