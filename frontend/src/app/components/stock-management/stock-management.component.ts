import { Component, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { ToastrService } from 'ngx-toastr';

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
      from_site_id: [''], // NEW FIELD: For Site-to-Site Transfers
      category_filter: [''], 
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference_no: [''],
      remarks: ['']
    });

    this.categoryForm = this.fb.group({ name: ['', Validators.required], description: [''] });
    this.materialForm = this.fb.group({ name: ['', Validators.required], category_id: ['', Validators.required], unit: ['Bags'], standard_cost: [0, Validators.min(0)], description: [''] });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadCategories();
    this.loadMaterials();

    const savedTab = sessionStorage.getItem('activeInventoryTab');
    if (savedTab && ['stock', 'category', 'material'].includes(savedTab)) {
      this.switchTab(savedTab as 'stock' | 'category' | 'material');
    }

    // NEW LOGIC: Make "From Site" mandatory only if doing a Transfer
    this.stockForm.get('entry_type')?.valueChanges.subscribe(type => {
      const fromSiteCtrl = this.stockForm.get('from_site_id');
      if (type === 'returned_received') {
        fromSiteCtrl?.setValidators([Validators.required]);
      } else {
        fromSiteCtrl?.clearValidators();
        fromSiteCtrl?.setValue('');
      }
      fromSiteCtrl?.updateValueAndValidity();
    });
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
  loadCategories(): void {
    this.materialService.getCategories().subscribe(res => {
      this.categories = res; this.categoryDataSource.data = res;
      if (this.activeTab === 'category') this.categoryDataSource.paginator = this.categoryPaginator;
    });
  }
  loadMaterials(): void {
    this.materialService.getMaterials().subscribe(res => {
      this.materials = res; this.filteredMaterialsForStock = res; this.materialDataSource.data = res;
      this.materialDataSource.filterPredicate = (data: any, filter: string): boolean => { return data.name.toLowerCase().includes(filter) || (data.description && data.description.toLowerCase().includes(filter)); };
      if (this.activeTab === 'material') this.materialDataSource.paginator = this.materialPaginator;
    });
  }
  getCategoryName(categoryId: number): string { const cat = this.categories.find(c => c.id === categoryId); return cat ? cat.name : 'Unknown'; }

  onProjectChange(projectId: any): void {
    this.sites = []; this.stockForm.patchValue({ site_id: '', from_site_id: '' }); this.selectedSiteId = null; this.stockDataSource.data = [];
    if (projectId) this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
  }
  onSiteChange(siteId: any): void {
    if (siteId) { this.selectedSiteId = Number(siteId); this.loadStockEntries(); }
    else { this.selectedSiteId = null; this.stockDataSource.data = []; }
  }
  onCategoryFilterChange(categoryId: any): void {
    this.stockForm.patchValue({ material_id: '' });
    if (categoryId) { this.filteredMaterialsForStock = this.materials.filter(m => m.category_id === Number(categoryId)); }
    else { this.filteredMaterialsForStock = this.materials; }
  }
  onMaterialChange(materialId: any): void {
    if (materialId) {
      const selectedMat = this.materials.find(m => m.id === Number(materialId));
      if (selectedMat) { this.stockForm.patchValue({ category_filter: selectedMat.category_id }); }
    }
  }

  submitStock(): void {
    if (this.stockForm.invalid) { this.stockForm.markAllAsTouched(); return; }
    this.submittingStock = true;
    
    const formValue = this.stockForm.value;

    // --- NEW LOGIC: Site to Site Transfer Handling ---
    if (formValue.entry_type === 'returned_received' && formValue.from_site_id) {
      const fromSiteName = this.sites.find(s => s.id === Number(formValue.from_site_id))?.name || 'Unknown Site';
      const toSiteName = this.sites.find(s => s.id === Number(formValue.site_id))?.name || 'Unknown Site';

      // 1. Payload to Deduct from Source
      const outPayload = { 
        ...formValue, 
        site_id: formValue.from_site_id, 
        entry_type: 'used', 
        remarks: formValue.remarks ? `${formValue.remarks} (Transfer to ${toSiteName})` : `Transfer to ${toSiteName}` 
      };
      
      // 2. Payload to Add to Destination
      const inPayload = { 
        ...formValue, 
        site_id: formValue.site_id, 
        entry_type: 'returned_received', 
        remarks: formValue.remarks ? `${formValue.remarks} (Transfer from ${fromSiteName})` : `Transfer from ${fromSiteName}` 
      };

      // Execute OUT then IN sequentially
      this.stockService.createStockEntry(outPayload).subscribe({
        next: () => {
          this.stockService.createStockEntry(inPayload).subscribe({
            next: () => {
              this.toastr.success('Site-to-Site Transfer completed successfully!');
              this.resetStockFormAfterSubmit();
            },
            error: () => { this.toastr.error('Failed to complete transfer IN phase'); this.submittingStock = false; }
          });
        },
        error: () => { this.toastr.error('Failed to complete transfer OUT phase'); this.submittingStock = false; }
      });
    } 
    // --- Standard Single Entry Handling ---
    else {
      this.stockService.createStockEntry(formValue).subscribe({
        next: () => {
          this.toastr.success('Transaction recorded');
          this.resetStockFormAfterSubmit();
        },
        error: () => { this.toastr.error('Failed to record transaction'); this.submittingStock = false; }
      });
    }
  }

  resetStockFormAfterSubmit(): void {
    const proj = this.stockForm.get('project_id')?.value;
    const site = this.stockForm.get('site_id')?.value;
    this.stockForm.reset({ project_id: proj, site_id: site, from_site_id: '', entry_type: 'received', category_filter: '' });
    this.filteredMaterialsForStock = this.materials;
    this.loadStockEntries();
    this.submittingStock = false;
  }

  loadStockEntries(): void {
    if (!this.selectedSiteId) return;
    this.loadingStockEntries = true;
    this.stockService.getStockEntries({ site_id: this.selectedSiteId }).subscribe({
      next: (entries) => {
        const mapped = entries.map(e => {
          const mat = this.materials.find(m => m.id === e.material_id);
          return { ...e, material_name: mat ? mat.name : 'Unknown' };
        });
        this.stockDataSource.data = mapped;
        setTimeout(() => this.stockDataSource.paginator = this.stockPaginator);
        this.loadingStockEntries = false;
      },
      error: () => { this.toastr.error('Failed to load ledger'); this.loadingStockEntries = false; }
    });
  }

  deleteStockEntry(id: number): void {
    if (confirm('Delete this transaction?')) {
      this.stockService.deleteStockEntry(id).subscribe({
        next: () => { this.toastr.success('Transaction deleted'); this.loadStockEntries(); },
        error: () => this.toastr.error('Failed to delete')
      });
    }
  }

  getEntryBadge(type: string): string {
    switch (type) {
      case 'received': return 'bg-success';
      case 'used': return 'bg-danger';
      case 'returned_received': return 'bg-info text-dark';
      case 'returned_supplier': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  }
  formatEntryType(type: string): string { 
    if (type === 'returned_received') return 'TRANSFERRED IN';
    return type.replace('_', ' ').toUpperCase(); 
  }

  submitCategory(): void {
    if (this.categoryForm.invalid) { this.categoryForm.markAllAsTouched(); return; }
    this.submittingCategory = true;
    const payload = this.categoryForm.value;
    const request = (this.isEditingCategory && this.editingCategoryId) ? this.materialService.createCategory(payload) : this.materialService.createCategory(payload);
    request.subscribe({
      next: () => { this.toastr.success(this.isEditingCategory ? 'Category updated' : 'Category created'); this.loadCategories(); this.resetCategoryForm(); this.submittingCategory = false; },
      error: () => { this.toastr.error('Failed to save category'); this.submittingCategory = false; }
    });
  }
  editCategory(category: any): void { this.isEditingCategory = true; this.editingCategoryId = category.id; this.categoryForm.patchValue({ name: category.name, description: category.description }); }
  resetCategoryForm(): void { this.isEditingCategory = false; this.editingCategoryId = null; this.categoryForm.reset(); }
  deleteCategory(id: number): void {
    if (confirm('Are you sure you want to delete this category? Please ensure no materials are attached to it.')) {
      this.materialService.deleteCategory(id).subscribe({ next: () => { this.toastr.success('Category deleted successfully', 'Success'); this.loadCategories(); }, error: (err) => { this.toastr.error(err.error?.detail || 'Failed to delete category', 'Error'); } });
    }
  }

  submitMaterial(): void {
    if (this.materialForm.invalid) { this.materialForm.markAllAsTouched(); return; }
    const payload = this.materialForm.value;
    const isDuplicate = this.materials.some(existingMaterial => {
      if (this.isEditingMaterial && this.editingMaterialId === existingMaterial.id) { return false; }
      return existingMaterial.name.toLowerCase().trim() === payload.name.toLowerCase().trim();
    });
    if (isDuplicate) { this.toastr.warning('A material with this exact name already exists!', 'Duplicate Prevented'); this.submittingMaterial = false; return; }
    
    this.submittingMaterial = true;
    if (this.isEditingMaterial && this.editingMaterialId) {
      this.materialService.updateMaterial(this.editingMaterialId, payload).subscribe({
        next: () => { this.toastr.success('Material updated'); this.loadMaterials(); this.resetMaterialForm(); this.submittingMaterial = false; },
        error: () => { this.toastr.error('Failed to update material'); this.submittingMaterial = false; }
      });
    } else {
      this.materialService.createMaterial(payload).subscribe({
        next: () => { this.toastr.success('Material created'); this.loadMaterials(); this.resetMaterialForm(); this.submittingMaterial = false; },
        error: () => { this.toastr.error('Failed to create material'); this.submittingMaterial = false; }
      });
    }
  }
  editMaterial(material: any): void {
    this.isEditingMaterial = true; this.editingMaterialId = material.id;
    this.materialForm.patchValue({ name: material.name, category_id: material.category_id, unit: material.unit, standard_cost: material.standard_cost, description: material.description });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  deleteMaterial(id: number): void {
    if (confirm('Delete this material?')) {
      this.materialService.deleteMaterial(id).subscribe({ next: () => { this.toastr.success('Material deleted'); this.loadMaterials(); }, error: () => this.toastr.error('Failed to delete') });
    }
  }
  resetMaterialForm(): void { this.isEditingMaterial = false; this.editingMaterialId = null; this.materialForm.reset({ unit: 'Bags', standard_cost: 0 }); }
  applyMaterialSearch(): void { this.materialDataSource.filter = this.materialSearchTerm.trim().toLowerCase(); if (this.materialDataSource.paginator) { this.materialDataSource.paginator.firstPage(); } }
}
