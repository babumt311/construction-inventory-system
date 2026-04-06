import { Component, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { ToastrService } from 'ngx-toastr';
import { forkJoin } from 'rxjs';

import { StockService } from '../../services/stock.service';
import { MaterialService } from '../../services/material.service';
import { ProjectService } from '../../services/project.service';

@Component({
  selector: 'app-stock-management',
  templateUrl: './stock-management.component.html'
})
export class StockManagementComponent implements OnInit {
  
  activeTab: 'stock' | 'category' | 'material' = 'stock';
  stockForm: FormGroup;
  categoryForm: FormGroup;
  materialForm: FormGroup;

  projects: any[] = [];
  sites: any[] = [];
  categories: any[] = [];
  materials: any[] = [];
  filteredMaterialsForStock: any[] = [];

  stockColumns: string[] = ['entry_date', 'material_name', 'entry_type', 'quantity', 'reference_no', 'actions'];
  stockDataSource = new MatTableDataSource<any>();
  @ViewChild('stockPaginator') stockPaginator!: MatPaginator;
  @ViewChild('stockSort') stockSort!: MatSort;
  selectedSiteId: number | null = null;
  loadingStockEntries = false;
  submittingStock = false;

  categoryColumns: string[] = ['name', 'description', 'actions'];
  categoryDataSource = new MatTableDataSource<any>();
  @ViewChild('categoryPaginator') categoryPaginator!: MatPaginator;
  @ViewChild('categorySort') categorySort!: MatSort;
  isEditingCategory = false;
  editingCategoryId: number | null = null;
  submittingCategory = false;

  materialColumns: string[] = ['name', 'category', 'unit', 'standard_cost', 'actions'];
  materialDataSource = new MatTableDataSource<any>();
  @ViewChild('materialPaginator') materialPaginator!: MatPaginator;
  @ViewChild('materialSort') materialSort!: MatSort;
  isEditingMaterial = false;
  editingMaterialId: number | null = null;
  submittingMaterial = false;
  materialSearchTerm = '';

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private materialService: MaterialService,
    private projectService: ProjectService,
    private toastr: ToastrService
  ) {
    this.stockForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      from_site_id: [''],
      to_site_id: [''],
      category_filter: [''], 
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference_no: [''],
      remarks: ['']
    });

    this.stockForm.get('entry_type')?.valueChanges.subscribe(type => {
      const siteCtrl = this.stockForm.get('site_id');
      const fromCtrl = this.stockForm.get('from_site_id');
      const toCtrl = this.stockForm.get('to_site_id');

      if (type === 'transfer') {
        siteCtrl?.clearValidators();
        fromCtrl?.setValidators(Validators.required);
        toCtrl?.setValidators(Validators.required);
      } else {
        siteCtrl?.setValidators(Validators.required);
        fromCtrl?.clearValidators();
        toCtrl?.clearValidators();
      }
      siteCtrl?.updateValueAndValidity();
      fromCtrl?.updateValueAndValidity();
      toCtrl?.updateValueAndValidity();
    });

    this.categoryForm = this.fb.group({ name: ['', Validators.required], description: [''] });
    this.materialForm = this.fb.group({ name: ['', Validators.required], category_id: ['', Validators.required], unit: ['Bags'], standard_cost: [0, Validators.min(0)], description: [''] });
  }

  ngOnInit(): void {
    this.loadProjects(); this.loadCategories(); this.loadMaterials();
    const savedTab = sessionStorage.getItem('activeInventoryTab');
    if (savedTab && ['stock', 'category', 'material'].includes(savedTab)) this.switchTab(savedTab as 'stock' | 'category' | 'material');
  }

  switchTab(tab: 'stock' | 'category' | 'material'): void {
    this.activeTab = tab;
    sessionStorage.setItem('activeInventoryTab', tab);
    setTimeout(() => {
      if (tab === 'stock') { this.stockDataSource.paginator = this.stockPaginator; this.stockDataSource.sort = this.stockSort; }
      else if (tab === 'category') { this.categoryDataSource.paginator = this.categoryPaginator; this.categoryDataSource.sort = this.categorySort; }
      else if (tab === 'material') { this.materialDataSource.paginator = this.materialPaginator; this.materialDataSource.sort = this.materialSort; }
    });
  }

  loadProjects(): void { this.projectService.getProjects().subscribe(res => this.projects = res); }
  loadCategories(): void { this.materialService.getCategories().subscribe(res => { this.categories = res; this.categoryDataSource.data = res; if (this.activeTab === 'category') this.categoryDataSource.paginator = this.categoryPaginator; }); }
  loadMaterials(): void { this.materialService.getMaterials().subscribe(res => { this.materials = res; this.filteredMaterialsForStock = res; this.materialDataSource.data = res; this.materialDataSource.filterPredicate = (data: any, filter: string): boolean => { return data.name.toLowerCase().includes(filter) || (data.description && data.description.toLowerCase().includes(filter)); }; if (this.activeTab === 'material') this.materialDataSource.paginator = this.materialPaginator; }); }
  getCategoryName(categoryId: number): string { const cat = this.categories.find(c => c.id === categoryId); return cat ? cat.name : 'Unknown'; }

  onProjectChange(projectId: any): void {
    this.sites = []; this.stockForm.patchValue({ site_id: '', from_site_id: '', to_site_id: '' }); this.selectedSiteId = null; this.stockDataSource.data = [];
    if (projectId) this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
  }
  onSiteChange(siteId: any): void { if (siteId) { this.selectedSiteId = Number(siteId); this.loadStockEntries(); } else { this.selectedSiteId = null; this.stockDataSource.data = []; } }
  onCategoryFilterChange(categoryId: any): void { this.stockForm.patchValue({ material_id: '' }); if (categoryId) { this.filteredMaterialsForStock = this.materials.filter(m => m.category_id === Number(categoryId)); } else { this.filteredMaterialsForStock = this.materials; } }
  onMaterialChange(materialId: any): void { if (materialId) { const selectedMat = this.materials.find(m => m.id === Number(materialId)); if (selectedMat) this.stockForm.patchValue({ category_filter: selectedMat.category_id }); } }

  submitStock(): void {
    if (this.stockForm.invalid) { this.stockForm.markAllAsTouched(); return; }
    this.submittingStock = true;
    const formValue = this.stockForm.value;

    if (formValue.entry_type === 'transfer') {
      const fromSite = Number(formValue.from_site_id);
      const toSite = Number(formValue.to_site_id);

      if (fromSite === toSite) {
        this.toastr.warning('Origin and Destination sites cannot be the same for a transfer.');
        this.submittingStock = false;
        return;
      }
      
      const fromSiteName = this.sites.find(s => s.id === fromSite)?.name || 'Another Site';
      const toSiteName = this.sites.find(s => s.id === toSite)?.name || 'Another Site';
      const userRemarks = formValue.remarks ? ` | Note: ${formValue.remarks}` : '';

      const payloadOut = { ...formValue, site_id: fromSite, entry_type: 'used', remarks: `Transfer OUT to ${toSiteName}${userRemarks}` };
      const payloadIn = { ...formValue, site_id: toSite, entry_type: 'returned_received', remarks: `Transfer IN from ${fromSiteName}${userRemarks}` };

      forkJoin([this.stockService.createStockEntry(payloadOut), this.stockService.createStockEntry(payloadIn)]).subscribe({
        next: () => this.handleStockSuccess(formValue.project_id, fromSite),
        error: () => { this.toastr.error('Failed to complete transfer'); this.submittingStock = false; }
      });
    } else {
      this.executeStockApi(formValue);
    }
  }

  executeStockApi(payload: any): void { this.stockService.createStockEntry(payload).subscribe({ next: () => this.handleStockSuccess(payload.project_id, payload.site_id), error: () => { this.toastr.error('Failed to record transaction'); this.submittingStock = false; } }); }

  handleStockSuccess(projectId: any, siteId: any): void {
    this.toastr.success('Transaction recorded successfully');
    this.stockForm.reset({ project_id: projectId, site_id: siteId, from_site_id: siteId, to_site_id: siteId, entry_type: 'received', category_filter: '' });
    this.filteredMaterialsForStock = this.materials;
    this.loadStockEntries();
    this.submittingStock = false;
  }

  loadStockEntries(): void {
    if (!this.selectedSiteId) return;
    this.loadingStockEntries = true;
    this.stockService.getStockEntries({ site_id: this.selectedSiteId }).subscribe({
      next: (entries) => {
        const mapped = entries.map(e => { const mat = this.materials.find(m => m.id === e.material_id); return { ...e, material_name: mat ? mat.name : 'Unknown' }; });
        this.stockDataSource.data = mapped;
        setTimeout(() => this.stockDataSource.paginator = this.stockPaginator);
        this.loadingStockEntries = false;
      },
      error: () => { this.toastr.error('Failed to load ledger'); this.loadingStockEntries = false; }
    });
  }

  deleteStockEntry(id: number): void { if (confirm('Delete this transaction?')) { this.stockService.deleteStockEntry(id).subscribe({ next: () => { this.toastr.success('Transaction deleted'); this.loadStockEntries(); }, error: () => this.toastr.error('Failed to delete') }); } }

  // --- NEW LEDGER DISPLAY FIXES ---
  formatEntryType(type: string, remarks?: string): string {
    if (type === 'used' && remarks?.includes('Transfer OUT')) return 'SENT TO SITE';
    if (type === 'returned_received' && remarks?.includes('Transfer IN')) return 'RECEIVED FROM SITE';
    if (type === 'returned_received') return 'RETURNED FROM SITE';
    return type.replace('_', ' ').toUpperCase();
  }

  getEntryBadge(type: string, remarks?: string): string {
    if (type === 'used' && remarks?.includes('Transfer OUT')) return 'bg-info text-dark border border-info';
    if (type === 'returned_received' && remarks?.includes('Transfer IN')) return 'bg-primary text-white';
    switch (type) {
      case 'received': return 'bg-success';
      case 'used': return 'bg-danger';
      case 'returned_received': return 'bg-primary text-white';
      case 'returned_supplier': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  }

  // --- TAB 2 & 3 OMmitted for brevity, they are identical to before ---
  // (Paste your existing TAB 2 & 3 logic here from the previous successful version)
  
  submitCategory(): void {
    if (this.categoryForm.invalid) { this.categoryForm.markAllAsTouched(); return; }
    this.submittingCategory = true;
    const payload = this.categoryForm.value;
    const request = (this.isEditingCategory && this.editingCategoryId) ? this.materialService.createCategory(payload) : this.materialService.createCategory(payload);
    request.subscribe({ next: () => { this.toastr.success(this.isEditingCategory ? 'Category updated' : 'Category created'); this.loadCategories(); this.resetCategoryForm(); this.submittingCategory = false; }, error: () => { this.toastr.error('Failed to save category'); this.submittingCategory = false; } });
  }
  editCategory(category: any): void { this.isEditingCategory = true; this.editingCategoryId = category.id; this.categoryForm.patchValue({ name: category.name, description: category.description }); }
  resetCategoryForm(): void { this.isEditingCategory = false; this.editingCategoryId = null; this.categoryForm.reset(); }
  deleteCategory(id: number): void { if (confirm('Are you sure you want to delete this category?')) { this.materialService.deleteCategory(id).subscribe({ next: () => { this.toastr.success('Category deleted'); this.loadCategories(); }, error: (err) => { this.toastr.error(err.error?.detail || 'Failed to delete category'); } }); } }

  submitMaterial(): void {
    if (this.materialForm.invalid) { this.materialForm.markAllAsTouched(); return; }
    const payload = this.materialForm.value;
    const isDuplicate = this.materials.some(existingMaterial => { if (this.isEditingMaterial && this.editingMaterialId === existingMaterial.id) return false; return existingMaterial.name.toLowerCase().trim() === payload.name.toLowerCase().trim(); });
    if (isDuplicate) { this.toastr.warning('A material with this exact name already exists!', 'Duplicate Prevented'); this.submittingMaterial = false; return; }
    this.submittingMaterial = true;
    if (this.isEditingMaterial && this.editingMaterialId) { this.materialService.updateMaterial(this.editingMaterialId, payload).subscribe({ next: () => { this.toastr.success('Material updated'); this.loadMaterials(); this.resetMaterialForm(); this.submittingMaterial = false; }, error: () => { this.toastr.error('Failed to update material'); this.submittingMaterial = false; } }); } else { this.materialService.createMaterial(payload).subscribe({ next: () => { this.toastr.success('Material created'); this.loadMaterials(); this.resetMaterialForm(); this.submittingMaterial = false; }, error: () => { this.toastr.error('Failed to create material'); this.submittingMaterial = false; } }); }
  }
  editMaterial(material: any): void { this.isEditingMaterial = true; this.editingMaterialId = material.id; this.materialForm.patchValue({ name: material.name, category_id: material.category_id, unit: material.unit, standard_cost: material.standard_cost, description: material.description }); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  deleteMaterial(id: number): void { if (confirm('Delete this material?')) { this.materialService.deleteMaterial(id).subscribe({ next: () => { this.toastr.success('Material deleted'); this.loadMaterials(); }, error: () => this.toastr.error('Failed to delete') }); } }
  resetMaterialForm(): void { this.isEditingMaterial = false; this.editingMaterialId = null; this.materialForm.reset({ unit: 'Bags', standard_cost: 0 }); }
  applyMaterialSearch(): void { this.materialDataSource.filter = this.materialSearchTerm.trim().toLowerCase(); if (this.materialDataSource.paginator) { this.materialDataSource.paginator.firstPage(); } }
}
