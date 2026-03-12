import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { POEntry, POEntryCreateRequest } from '../models/po.model';

@Injectable({
  providedIn: 'root'
})
export class PoService {
  constructor(private api: ApiService) {}

  // PO Entry Management
  getPOEntries(params?: any): Observable<POEntry[]> {
    return this.api.get<POEntry[]>('po/entries', params);
  }

  getPOEntry(id: number): Observable<POEntry> {
    return this.api.get<POEntry>(`po/entries/${id}`);
  }

  createPOEntry(entry: POEntryCreateRequest): Observable<POEntry> {
    return this.api.post<POEntry>('po/entries', entry);
  }

  updatePOEntry(id: number, entry: Partial<POEntry>): Observable<POEntry> {
    return this.api.put<POEntry>(`po/entries/${id}`, entry);
  }

  deletePOEntry(id: number): Observable<any> {
    return this.api.delete<any>(`po/entries/${id}`);
  }

  // Reports
  getPOStats(projectId: number): Observable<any> {
    return this.api.get<any>(`po/stats/${projectId}`);
  }

  // Supplier Management
  getSuppliers(projectId?: number): Observable<any[]> {
    const params = projectId ? { project_id: projectId } : undefined;
    return this.api.get<any[]>('po/suppliers', params);
  }

  getSupplierInvoices(supplierName: string, projectId?: number): Observable<any[]> {
    const params: any = { supplier_name: supplierName };
    if (projectId) {
      params.project_id = projectId;
    }
    return this.api.get<any[]>('po/supplier-invoices', params);
  }
}
