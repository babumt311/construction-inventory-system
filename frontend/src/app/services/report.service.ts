import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { saveAs } from 'file-saver';
import { ApiService } from './api.service';
import {
  ReportFilter,
  MaterialWiseReport,
  SupplierWiseReport,
  PeriodReport,
  SupplierSummaryReport,
  StockValuationReport
} from '../models/report.model';

@Injectable({
  providedIn: 'root'
})
export class ReportService {
  constructor(private api: ApiService) {}

  // Material Wise Report
  getMaterialWiseReport(filters: ReportFilter): Observable<MaterialWiseReport[]> {
    return this.api.get<MaterialWiseReport[]>('reports/material-wise', this.prepareFilters(filters));
  }

  // Supplier Wise Report
  getSupplierWiseReport(filters: ReportFilter): Observable<SupplierWiseReport[]> {
    return this.api.get<SupplierWiseReport[]>('reports/supplier-wise', this.prepareFilters(filters));
  }

  // Supplier Summary Report
  getSupplierSummaryReport(projectId?: number): Observable<SupplierSummaryReport[]> {
    const params = projectId ? { project_id: projectId } : undefined;
    return this.api.get<SupplierSummaryReport[]>('reports/supplier-summary', params);
  }

  // Period Report
  getPeriodReport(siteId: number, startDate: Date, endDate: Date, materialId?: number): Observable<PeriodReport[]> {
    const params: any = {
      site_id: siteId,
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0]
    };
    if (materialId) {
      params.material_id = materialId;
    }
    return this.api.get<PeriodReport[]>('reports/period', params);
  }

  // Stock Valuation Report
  getStockValuationReport(siteId?: number, projectId?: number): Observable<StockValuationReport[]> {
    const params: any = {};
    if (siteId) params.site_id = siteId;
    if (projectId) params.project_id = projectId;
    return this.api.get<StockValuationReport[]>('reports/stock-valuation', params);
  }

  // Custom Report
  getCustomReport(filters: ReportFilter): Observable<any[]> {
    return this.api.get<any[]>('reports/custom', this.prepareFilters(filters));
  }

  // Export to Excel
  exportReport(reportType: string, filters: ReportFilter): void {
    const params = this.prepareFilters(filters);
    params.format = 'excel';
    
    this.api.downloadFile(`reports/export/${reportType}`, params)
      .subscribe(blob => {
        const filename = `${reportType}_report_${new Date().toISOString().split('T')[0]}.xlsx`;
        saveAs(blob, filename);
      });
  }

  // Audit Logs
  getAuditLogs(params?: any): Observable<any[]> {
    return this.api.get<any[]>('audit/logs', params);
  }

  // Helper method to prepare filters
  private prepareFilters(filters: ReportFilter): any {
    const params: any = {};
    
    if (filters.start_date) {
      params.start_date = filters.start_date.toISOString().split('T')[0];
    }
    
    if (filters.end_date) {
      params.end_date = filters.end_date.toISOString().split('T')[0];
    }
    
    if (filters.project_id) params.project_id = filters.project_id;
    if (filters.site_id) params.site_id = filters.site_id;
    if (filters.material_id) params.material_id = filters.material_id;
    if (filters.supplier_name) params.supplier_name = filters.supplier_name;
    if (filters.category_id) params.category_id = filters.category_id;
    
    return params;
  }
}
