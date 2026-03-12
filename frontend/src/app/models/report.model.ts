export interface ReportFilter {
  start_date?: Date;
  end_date?: Date;
  project_id?: number;
  site_id?: number;
  material_id?: number;
  supplier_name?: string;
  category_id?: number;
}

export interface MaterialWiseReport {
  category: string;
  material: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  total_cost: number;
}

export interface SupplierWiseReport {
  supplier_name: string;
  material: string;
  quantity: number;
  unit: string;
  total_cost: number;
  invoice_no: string;
  purchase_date: Date;
}

export interface PeriodReport {
  material: string;
  unit: string;
  opening_stock: number;
  received: number;
  total_issued: number;
  returned: number;
  closing_stock: number;
  remarks?: string;
}

export interface SupplierSummaryReport {
  supplier: string;
  total_cost: number;
  invoice_count: number;
  last_purchase_date: Date;
}

export interface StockValuationReport {
  material: string;
  category: string;
  unit: string;
  current_stock: number;
  unit_cost: number;
  total_value: number;
}
