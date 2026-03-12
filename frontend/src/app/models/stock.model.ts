import { Site } from './site.model'; 
import { Material } from './material.model';
import { User } from './user.model';

export enum StockEntryType {
  RECEIVED = 'received',
  USED = 'used',
  RETURNED_RECEIVED = 'returned_received',
  RETURNED_SUPPLIER = 'returned_supplier'
}

export interface StockEntry {
  id: number;
  site_id: number;
  material_id: number;
  entry_type: StockEntryType;
  quantity: number;
  supplier_name?: string;
  invoice_no?: string;
  reference?: string;
  remarks?: string;
  entry_date: Date;
  created_by: number;
  created_at: Date;
  site?: Site;
  material?: Material;
  user?: User;
}

export interface StockEntryCreateRequest {
  site_id: number;
  material_id: number;
  entry_type: StockEntryType;
  quantity: number;
  supplier_name?: string;
  invoice_no?: string;
  reference?: string;
  remarks?: string;
  entry_date?: Date;
}

export interface StockBalance {
  material_id: number;
  material_name: string;
  current_balance: number;
  opening_balance: number;
  total_received: number;
  total_used: number;
  total_returned_received: number;
  total_returned_supplier: number;
  has_negative_balance: boolean;
}

export interface DailyStockReport {
  id: number;
  site_id: number;
  material_id: number;
  report_date: Date;
  opening_stock: number;
  received: number;
  used: number;
  returned_received: number;
  returned_supplier: number;
  closing_stock: number;
  total_received: number;
  created_at: Date;
  site?: Site;
  material?: Material;
}
