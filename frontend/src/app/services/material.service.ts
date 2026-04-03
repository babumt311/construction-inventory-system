import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Category, Material, MaterialCreateRequest } from '../models/material.model';

@Injectable({
  providedIn: 'root'
})
export class MaterialService {
  constructor(private api: ApiService) {}

  // ==========================================
  // CATEGORY MANAGEMENT
  // ==========================================
  
  getCategories(): Observable<Category[]> {
    return this.api.get<Category[]>('products/categories');
  }

  getCategory(id: number): Observable<Category> {
    return this.api.get<Category>(`products/categories/${id}`);
  }

  createCategory(category: Partial<Category>): Observable<Category> {
    return this.api.post<Category>('products/categories', category);
  }

  updateCategory(id: number, category: Partial<Category>): Observable<Category> {
    return this.api.put<Category>(`products/categories/${id}`, category);
  }

  deleteCategory(id: number): Observable<any> {
    return this.api.delete<any>(`products/categories/${id}`);
  }

  // ==========================================
  // MATERIAL MANAGEMENT
  // ==========================================
  
  getMaterials(params?: any): Observable<Material[]> {
    return this.api.get<Material[]>('products/materials', params);
  }

  getMaterial(id: number): Observable<Material> {
    return this.api.get<Material>(`products/materials/${id}`);
  }

  createMaterial(material: MaterialCreateRequest | any): Observable<Material> {
    return this.api.post<Material>('products/materials', material);
  }

  updateMaterial(id: number, material: Partial<Material>): Observable<Material> {
    return this.api.put<Material>(`products/materials/${id}`, material);
  }

  deleteMaterial(id: number): Observable<any> {
    return this.api.delete<any>(`products/materials/${id}`);
  }

  searchMaterials(searchTerm: string): Observable<Material[]> {
    return this.api.get<Material[]>('products/materials/search', { q: searchTerm });
  }

  // ==========================================
  // EXCEL UPLOAD & TEMPLATES
  // ==========================================
  
  uploadMaterials(file: File): Observable<any> {
    return this.api.uploadFile('products/upload/materials', file);
  }

  downloadTemplate(): Observable<Blob> {
    return this.api.downloadFile('products/template');
  }
}
