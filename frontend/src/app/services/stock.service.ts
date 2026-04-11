import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import {
  StockEntry,
  StockEntryCreateRequest,
  StockBalance,
  DailyStockReport,
  StockEntryType
} from '../models/stock.model';

@Injectable({
  providedIn: 'root'
})
export class StockService {
  constructor(private api: ApiService) {}

  // Stock Entry Management
  getStockEntries(params?: any): Observable<StockEntry[]> {
    return this.api.get<StockEntry[]>('stock/entries', params);
  }

  getStockEntry(id: number): Observable<StockEntry> {
    return this.api.get<StockEntry>(`stock/entries/${id}`);
  }

  createStockEntry(entry: StockEntryCreateRequest): Observable<StockEntry> {
    return this.api.post<StockEntry>('stock/entries', entry);
  }

  updateStockEntry(id: number, entry: Partial<StockEntry>): Observable<StockEntry> {
    return this.api.put<StockEntry>(`stock/entries/${id}`, entry);
  }

  deleteStockEntry(id: number): Observable<any> {
    return this.api.delete<any>(`stock/entries/${id}`);
  }

  // Stock Calculations
  getStockBalance(siteId: number, materialId: number, asOfDate?: Date): Observable<StockBalance> {
    const params: any = { site_id: siteId, material_id: materialId };
    if (asOfDate) {
      params.as_of_date = asOfDate.toISOString();
    }
    return this.api.get<StockBalance>('stock/balance', params);
  }

  // --- RESTORED: Safely encode parameters to prevent API failure ---
  getSiteStockSummary(siteId: number, filters?: any) {
    let params = new HttpParams();
    
    if (filters) {
      if (filters.start_date) params = params.set('start_date', filters.start_date);
      if (filters.end_date) params = params.set('end_date', filters.end_date);
      if (filters.supplier_name) params = params.set('supplier_name', filters.supplier_name);
      if (filters.entry_type) params = params.set('entry_type', filters.entry_type);
    }
    
    return this.api.get(`stock/site-summary/${siteId}`, params);
  }

  // Daily Reports
  getDailyReports(siteId: number, params?: any): Observable<DailyStockReport[]> {
    return this.api.get<DailyStockReport[]>(`stock/daily-reports/${siteId}`, params);
  }

  generateDailyReport(siteId: number, reportDate?: Date): Observable<any> {
    let url = `stock/generate-daily-report/${siteId}`;

    if (reportDate) {
      const dateStr = reportDate.toISOString().split('T')[0];
      url += `?report_date=${dateStr}`;
    }

    return this.api.post<any>(url, {});
  }

  // Excel Upload for Stock Entries
  uploadStockEntries(file: File, siteId: number): Observable<any> {
    return this.api.uploadFile('uploads/stock', file, { site_id: siteId });
  }

  // CLI Methods
  calculateStock(siteId: number, materialId: number): Observable<any> {
    return this.api.get<any>(`stock/cli/calculate/${siteId}/${materialId}`);
  }
}
