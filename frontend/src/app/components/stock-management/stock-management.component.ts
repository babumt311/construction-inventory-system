import { Component, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
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
  
  activeTab: 'stock' | 'category' | 'material' | 'supplier' = 'stock';
  
  stockForm: FormGroup;
  categoryForm: FormGroup;
  materialForm: FormGroup;
  supplierForm: FormGroup;

  projects: any[] = [];
  sites: any[] = [];
  categories: any[] = [];
  materials: any[] = [];
  suppliers: any[] = [];

  private materialCache: { [key: string]: any[] } = {};

  stockColumns: string[] = ['entry_date', 'material_name', 'entry_type', 'quantity', 'supplier_name', 'invoice_no', 'actions'];
  stockDataSource = new MatTableDataSource<any>();
  @ViewChild('stockPaginator') stockPaginator!: MatPaginator;
  @ViewChild('stockSort') stockSort!: MatSort;
  
  selectedSiteId: number | null = null;
  loadingStockEntries = false;
  submittingStock = false;
  
  isEditingStock = false;
  editingStockId: number | null = null;

  categoryColumns: string[] = ['name', 'description', 'actions'];
  categoryDataSource = new MatTableDataSource<any>();
  @ViewChild('categoryPaginator') categoryPaginator!: MatPaginator;
  @ViewChild('categorySort') categorySort!: MatSort;
  isEditingCategory = false;
  editingCategoryId: number | null = null;
  submittingCategory = false;

  materialColumns: string[] = ['name', 'category', 'unit', 'actions'];
  materialDataSource = new MatTableDataSource<any>();
  @ViewChild('materialPaginator') materialPaginator!: MatPaginator;
  @ViewChild('materialSort') materialSort!: MatSort;
  isEditingMaterial = false;
  editingMaterialId: number | null = null;
  submittingMaterial = false;
  materialSearchTerm = '';

  supplierColumns: string[] = ['name', 'contact_info', 'actions'];
  supplierDataSource = new MatTableDataSource<any>();
  @ViewChild('supplierPaginator') supplierPaginator!: MatPaginator;
  @ViewChild('supplierSort') supplierSort!: MatSort;
  isEditingSupplier = false;
  editingSupplierId: number | null = null;
  submittingSupplier = false;

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private materialService: MaterialService,
    private projectService: ProjectService,
    private toastr: ToastrService
  ) {
    this.stockForm = this.fb.group({
      project_id: [null, Validators.required],
      site_id: [null],
      from_site_id: [null],
      to_site_id: [null],
      supplier_name: [null, Validators.required], 
      invoice_no: [null, Validators.required],    
      invoice_date: [null, Validators.required],  
      entry_type: ['received', Validators.required],
      remarks: [null],
      items: this.fb.array([]) 
    });

    this.stockForm.get('entry_type')?.valueChanges.subscribe(type => {
      const siteCtrl = this.stockForm.get('site_id');
      const fromCtrl = this.stockForm.get('from_site_id');
      const toCtrl = this.stockForm.get('to_site_id');
      const supplierCtrl = this.stockForm.get('supplier_name');
      const invoiceNoCtrl = this.stockForm.get('invoice_no');
      const invoiceDateCtrl = this.stockForm.get('invoice_date');

      if (type !== 'received') {
        const itemsArray = this.stockForm.get('items') as FormArray;
        itemsArray.controls.forEach(control => {
          control.patchValue({ unit_price: 0, tax_percent: 0, tax_amount: 0, total_cost: 0 });
        });
      }

      if (type === 'transfer') {
        siteCtrl?.clearValidators();
        fromCtrl?.setValidators(Validators.required);
        toCtrl?.setValidators(Validators.required);
      } else {
        siteCtrl?.setValidators(Validators.required);
        fromCtrl?.clearValidators();
        toCtrl?.clearValidators();
      }

      if (type === 'received') {
        supplierCtrl?.setValidators(Validators.required);
        invoiceNoCtrl?.setValidators(Validators.required);
        invoiceDateCtrl?.setValidators(Validators.required);
      } else {
        supplierCtrl?.clearValidators();
        invoiceNoCtrl?.clearValidators();
        invoiceDateCtrl?.clearValidators();
        if(!this.isEditingStock) {
          supplierCtrl?.setValue(null);
          invoiceNoCtrl?.setValue(null);
          invoiceDateCtrl?.setValue(null);
        }
      }

      siteCtrl?.updateValueAndValidity();
      fromCtrl?.updateValueAndValidity();
      toCtrl?.updateValueAndValidity();
      supplierCtrl?.updateValueAndValidity();
      invoiceNoCtrl?.updateValueAndValidity();
      invoiceDateCtrl?.updateValueAndValidity();
    });

    this.categoryForm = this.fb.group({ name: [null, Validators.required], description: [null] });
    this.materialForm = this.fb.group({ name: [null, Validators.required], category_id: [null, Validators.required], unit: ['Bags'], description: [null] });
    this.supplierForm = this.fb.group({ name: [null, Validators.required], contact_info: [null] });
  }

  ngOnInit(): void {
    this.loadProjects(); 
    this.loadCategories(); 
    this.loadMaterials();
    this.loadSuppliers();
    this.addItem(); 
    
    const savedTab = sessionStorage.getItem('activeInventoryTab');
    if (savedTab && ['stock', 'category', 'material', 'supplier'].includes(savedTab)) {
      this.switchTab(savedTab as any);
    }
  }

  get isReceivedType(): boolean { return this.stockForm.get('entry_type')?.value === 'received'; }

  switchTab(tab: 'stock' | 'category' | 'material' | 'supplier'): void {
    this.activeTab = tab;
    sessionStorage.setItem('activeInventoryTab', tab);
    setTimeout(() => {
      if (tab === 'stock') { this.stockDataSource.paginator = this.stockPaginator; this.stockDataSource.sort = this.stockSort; }
      else if (tab === 'category') { this.categoryDataSource.paginator = this.categoryPaginator; this.categoryDataSource.sort = this.categorySort; }
      else if (tab === 'material') { this.materialDataSource.paginator = this.materialPaginator; this.materialDataSource.sort = this.materialSort; }
      else if (tab === 'supplier') { this.supplierDataSource.paginator = this.supplierPaginator; this.supplierDataSource.sort = this.supplierSort; }
    });
  }

  get items(): FormArray { return this.stockForm.get('items') as FormArray; }

  addItem(): void {
    const itemGroup = this.fb.group({
      category_id: [null],
      material_id: [null, Validators.required],
      quantity: [1, [Validators.required, Validators.min(0.01)]],
      unit_price: [0, [Validators.min(0)]],
      tax_percent: [0, [Validators.min(0)]],
      tax_amount: [{ value: 0, disabled: true }], 
      total_cost: [{ value: 0, disabled: true }]  
    });

    itemGroup.get('material_id')?.valueChanges.subscribe(matId => {
      if (matId) {
        const selectedMat = this.materials.find(m => m.id === Number(matId));
        if (selectedMat && selectedMat.category_id) {
          itemGroup.patchValue({ category_id: selectedMat.category_id }, { emitEvent: false });
        }
      }
    });

    itemGroup.get('category_id')?.valueChanges.subscribe(catId => {
      if (catId) {
        const currentMatId = itemGroup.get('material_id')?.value;
        if (currentMatId) {
          const mat = this.materials.find(m => m.id === Number(currentMatId));
          if (mat && mat.category_id !== Number(catId)) {
            itemGroup.patchValue({ material_id: null }, { emitEvent: false });
          }
        }
      }
    });
    
    itemGroup.valueChanges.subscribe(val => {
      const qty = val.quantity || 0;
      const price = val.unit_price || 0;
      const taxPct = val.tax_percent || 0;
      const taxAmt = price * (taxPct / 100);
      const total = (price + taxAmt) * qty;

      itemGroup.patchValue({
        tax_amount: parseFloat(taxAmt.toFixed(2)),
        total_cost: parseFloat(total.toFixed(2))
      }, { emitEvent: false });
    });

    this.items.push(itemGroup);
  }

  removeItem(index: number): void {
    if (this.items.length > 1) { this.items.removeAt(index); } 
    else { this.toastr.warning('You must have at least one material entry.'); }
  }

  loadProjects(): void { this.projectService.getProjects().subscribe(res => this.projects = res); }
  
  getFilteredMaterials(categoryId: any): any[] {
    const key = categoryId ? String(categoryId) : 'all';
    if (!this.materialCache[key]) {
      this.materialCache[key] = categoryId ? this.materials.filter(m => m.category_id === Number(categoryId)) : this.materials;
    }
    return this.materialCache[key];
  }

  onProjectChange(): void {
    if (this.isEditingStock) return; 
    const projectId = this.stockForm.get('project_id')?.value;
    this.sites = []; 
    this.stockForm.patchValue({ site_id: null, from_site_id: null, to_site_id: null }); 
    this.selectedSiteId = null; 
    this.stockDataSource.data = [];
    if (projectId) this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
  }

  onSiteChange(): void { 
    const siteId = this.stockForm.get('site_id')?.value;
    if (siteId) { 
      this.selectedSiteId = Number(siteId); 
      this.loadStockEntries(); 
    } else { 
      this.selectedSiteId = null; 
      this.stockDataSource.data = []; 
    } 
  }

  editStockEntry(entry: any): void {
    this.isEditingStock = true;
    this.editingStockId = entry.id;

    const formattedDate = entry.invoice_date ? new Date(entry.invoice_date).toISOString().split('T')[0] : '';

    this.stockForm.patchValue({
      entry_type: entry.entry_type,
      supplier_name: entry.supplier_name || '',
      invoice_no: entry.invoice_no || '',
      invoice_date: formattedDate,
      remarks: entry.remarks || ''
    });

    this.items.clear();
    
    const itemGroup = this.fb.group({
      category_id: [null],
      material_id: [entry.material_id, Validators.required],
      quantity: [entry.quantity, [Validators.required, Validators.min(0.01)]],
      unit_price: [entry.unit_cost, [Validators.min(0)]],
      tax_percent: [entry.tax_percent, [Validators.min(0)]],
      tax_amount: [{ value: entry.tax_amount, disabled: true }],
      total_cost: [{ value: entry.total_cost, disabled: true }]
    });

    itemGroup.get('material_id')?.valueChanges.subscribe(matId => {
      if (matId) {
        const selectedMat = this.materials.find(m => m.id === Number(matId));
        if (selectedMat && selectedMat.category_id) {
          itemGroup.patchValue({ category_id: selectedMat.category_id }, { emitEvent: false });
        }
      }
    });

    itemGroup.get('category_id')?.valueChanges.subscribe(catId => {
      if (catId) {
        const currentMatId = itemGroup.get('material_id')?.value;
        if (currentMatId) {
          const mat = this.materials.find(m => m.id === Number(currentMatId));
          if (mat && mat.category_id !== Number(catId)) {
            itemGroup.patchValue({ material_id: null }, { emitEvent: false });
          }
        }
      }
    });

    itemGroup.valueChanges.subscribe(val => {
      const qty = val.quantity || 0;
      const price = val.unit_price || 0;
      const taxPct = val.tax_percent || 0;
      const taxAmt = price * (taxPct / 100);
      const total = (price + taxAmt) * qty;
      itemGroup.patchValue({ tax_amount: parseFloat(taxAmt.toFixed(2)), total_cost: parseFloat(total.toFixed(2)) }, { emitEvent: false });
    });

    const selectedMat = this.materials.find(m => m.id === Number(entry.material_id));
    if (selectedMat && selectedMat.category_id) { itemGroup.patchValue({ category_id: selectedMat.category_id }, { emitEvent: false }); }

    this.items.push(itemGroup);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    this.toastr.info('Transaction loaded for editing.');
  }

  cancelEditStock(): void {
    this.isEditingStock = false;
    this.editingStockId = null;
    const currentProject = this.stockForm.get('project_id')?.value;
    const currentSite = this.stockForm.get('site_id')?.value;
    
    this.stockForm.reset({ project_id: currentProject, site_id: currentSite, entry_type: 'received' });
    this.items.clear();
    this.addItem();
  }

  submitStock(): void {
    if (this.stockForm.invalid) { 
      this.stockForm.markAllAsTouched(); 
      this.toastr.error('Please fill all mandatory fields correctly.');
      return; 
    }

    this.submittingStock = true;
    const formValue = this.stockForm.getRawValue(); 

    if (this.isEditingStock && this.editingStockId) {
      const item = formValue.items[0]; 
      const updatePayload = {
        site_id: Number(formValue.site_id),
        supplier_name: formValue.supplier_name || null,
        invoice_no: formValue.invoice_no || null,
        invoice_date: formValue.invoice_date || null,
        reference_no: formValue.invoice_no || null,
        material_id: Number(item.material_id),
        quantity: Number(item.quantity),
        unit_cost: Number(item.unit_price) || 0,
        tax_percent: Number(item.tax_percent) || 0,
        tax_amount: Number(item.tax_amount) || 0,
        total_cost: Number(item.total_cost) || 0,
        entry_type: formValue.entry_type,
        remarks: formValue.remarks
      };

      this.stockService.updateStockEntry(this.editingStockId, updatePayload).subscribe({
        next: () => {
          this.toastr.success('Transaction updated successfully!');
          this.cancelEditStock(); 
          this.loadStockEntries();
          this.submittingStock = false;
        },
        error: () => {
          this.toastr.error('Failed to update transaction.');
          this.submittingStock = false;
        }
      });
      return; 
    }

    const apiRequests: any[] = [];

    formValue.items.forEach((item: any) => {
      const basePayload = {
        project_id: Number(formValue.project_id),
        supplier_name: formValue.supplier_name || null, 
        invoice_no: formValue.invoice_no || null,       
        invoice_date: formValue.invoice_date || null,   
        reference_no: formValue.invoice_no || null,     
        material_id: Number(item.material_id),
        quantity: Number(item.quantity),
        unit_cost: Number(item.unit_price) || 0,
        tax_percent: Number(item.tax_percent) || 0,
        tax_amount: Number(item.tax_amount) || 0,
        total_cost: Number(item.total_cost) || 0
      };

      if (formValue.entry_type === 'transfer') {
        const fromSite = Number(formValue.from_site_id);
        const toSite = Number(formValue.to_site_id);
        const fromSiteName = this.sites.find(s => s.id === fromSite)?.name || 'Origin';
        const toSiteName = this.sites.find(s => s.id === toSite)?.name || 'Destination';
        const userRemarks = formValue.remarks ? ` | Note: ${formValue.remarks}` : '';

        const payloadOut: any = { ...basePayload, site_id: fromSite, entry_type: 'used', remarks: `Transfer OUT to ${toSiteName}${userRemarks}` };
        const payloadIn: any = { ...basePayload, site_id: toSite, entry_type: 'returned_received', remarks: `Transfer IN from ${fromSiteName}${userRemarks}` };

        apiRequests.push(this.stockService.createStockEntry(payloadOut));
        apiRequests.push(this.stockService.createStockEntry(payloadIn));
      } else {
        const payload: any = { ...basePayload, site_id: Number(formValue.site_id), entry_type: formValue.entry_type, remarks: formValue.remarks };
        apiRequests.push(this.stockService.createStockEntry(payload));
      }
    });

    forkJoin(apiRequests).subscribe({
      next: () => {
        this.toastr.success(`Successfully saved ${formValue.items.length} material entries!`);
        
        // Auto-add new supplier if typed
        if (formValue.supplier_name && !this.suppliers.some(s => s.name === formValue.supplier_name)) {
          this.stockService.createSupplier({ name: formValue.supplier_name }).subscribe(() => this.loadSuppliers());
        }

        const currentProject = formValue.project_id;
        const currentSite = formValue.site_id;
        this.stockForm.reset({ project_id: currentProject, site_id: currentSite, entry_type: 'received' });
        this.items.clear();
        this.addItem(); 
        
        this.selectedSiteId = currentSite;
        this.loadStockEntries();
        this.submittingStock = false;
      },
      error: () => {
        this.toastr.error('Failed to process transactions.');
        this.submittingStock = false;
      }
    });
  }

  loadStockEntries(): void {
    const activeSite = this.selectedSiteId || this.stockForm.get('site_id')?.value;
    if (!activeSite) return;
    
    this.selectedSiteId = Number(activeSite);
    this.loadingStockEntries = true;
    
    this.stockService.getStockEntries({ site_id: this.selectedSiteId }).subscribe({
      next: (entries: any) => {
        const dataArray = Array.isArray(entries) ? entries : (entries.data || []);
        
        const mapped = dataArray.map((e: any) => { 
          const mat = this.materials.find(m => m.id === e.material_id); 
          return { ...e, material_name: mat ? mat.name : 'Unknown' }; 
        });
        
        this.stockDataSource.data = mapped;
        setTimeout(() => {
          if (this.stockPaginator) this.stockDataSource.paginator = this.stockPaginator;
          if (this.stockSort) this.stockDataSource.sort = this.stockSort;
        });
        this.loadingStockEntries = false;
      },
      error: (err) => { 
        console.error("Failed to load ledger:", err);
        this.stockDataSource.data = [];
        this.loadingStockEntries = false; 
      }
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

  formatEntryType(type: string, remarks?: string): string {
    if (!type) return 'UNKNOWN';
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

  loadCategories(): void { 
    this.materialService.getCategories().subscribe(res => { 
      this.categories = res; 
      this.categoryDataSource.data = res; 
      if (this.activeTab === 'category') this.categoryDataSource.paginator = this.categoryPaginator; 
    }); 
  }

  getCategoryName(categoryId: number): string { 
    const cat = this.categories.find(c => c.id === categoryId); 
    return cat ? cat.name : 'Unknown'; 
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

  editCategory(category: any): void { 
    this.isEditingCategory = true; 
    this.editingCategoryId = category.id; 
    this.categoryForm.patchValue({ name: category.name, description: category.description }); 
  }

  resetCategoryForm(): void { 
    this.isEditingCategory = false; 
    this.editingCategoryId = null; 
    this.categoryForm.reset(); 
  }

  deleteCategory(id: number): void { 
    if (confirm('Are you sure you want to delete this category?')) { 
      this.materialService.deleteCategory(id).subscribe({ 
        next: () => { this.toastr.success('Category deleted successfully'); this.loadCategories(); }, 
        error: (err) => { this.toastr.error(err.error?.detail || 'Failed to delete category'); } 
      }); 
    } 
  }

  loadMaterials(): void { 
    this.materialService.getMaterials().subscribe(res => { 
      this.materials = res; 
      this.materialCache = {}; 
      this.materialDataSource.data = res; 
      this.materialDataSource.filterPredicate = (data: any, filter: string): boolean => { 
        return data.name.toLowerCase().includes(filter) || (data.description && data.description.toLowerCase().includes(filter)); 
      }; 
      if (this.activeTab === 'material') this.materialDataSource.paginator = this.materialPaginator; 
    }); 
  }

  submitMaterial(): void {
    if (this.materialForm.invalid) { this.materialForm.markAllAsTouched(); return; }
    const payload = this.materialForm.value;
    const isDuplicate = this.materials.some(existingMaterial => { 
      if (this.isEditingMaterial && this.editingMaterialId === existingMaterial.id) return false; 
      return existingMaterial.name.toLowerCase().trim() === payload.name.toLowerCase().trim(); 
    });
    
    if (isDuplicate) { this.toastr.warning('A material with this name already exists!'); return; }
    
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
    this.isEditingMaterial = true; 
    this.editingMaterialId = material.id; 
    this.materialForm.patchValue({ name: material.name, category_id: material.category_id, unit: material.unit, description: material.description }); 
    window.scrollTo({ top: 0, behavior: 'smooth' }); 
  }

  deleteMaterial(id: number): void { 
    if (confirm('Delete this material?')) { 
      this.materialService.deleteMaterial(id).subscribe({ 
        next: () => { this.toastr.success('Material deleted'); this.loadMaterials(); }, 
        error: () => this.toastr.error('Failed to delete') 
      }); 
    } 
  }

  resetMaterialForm(): void { 
    this.isEditingMaterial = false; 
    this.editingMaterialId = null; 
    this.materialForm.reset({ unit: 'Bags' }); 
  }

  applyMaterialSearch(): void { 
    this.materialDataSource.filter = this.materialSearchTerm.trim().toLowerCase(); 
    if (this.materialDataSource.paginator) { this.materialDataSource.paginator.firstPage(); } 
  }

  // --- SUPPLIER LOGIC ---
  loadSuppliers(): void {
    this.stockService.getSuppliers().subscribe({
      next: (res) => {
        this.suppliers = res;
        this.supplierDataSource.data = res;
        if (this.activeTab === 'supplier') {
          this.supplierDataSource.paginator = this.supplierPaginator;
          this.supplierDataSource.sort = this.supplierSort;
        }
      }
    });
  }

  submitSupplier(): void {
    if (this.supplierForm.invalid) { 
      this.supplierForm.markAllAsTouched(); 
      return; 
    }
    this.submittingSupplier = true;
    const payload = this.supplierForm.value;
    
    const request = this.isEditingSupplier && this.editingSupplierId 
      ? this.stockService.updateSupplier(this.editingSupplierId, payload) 
      : this.stockService.createSupplier(payload);

    request.subscribe({
      next: () => {
        this.toastr.success(this.isEditingSupplier ? 'Supplier updated!' : 'Supplier created!');
        this.loadSuppliers();
        this.resetSupplierForm();
        this.submittingSupplier = false;
      },
      error: () => {
        this.toastr.error('Failed to save supplier.');
        this.submittingSupplier = false;
      }
    });
  }

  editSupplier(supplier: any): void {
    this.isEditingSupplier = true;
    this.editingSupplierId = supplier.id;
    this.supplierForm.patchValue({
      name: supplier.name,
      contact_info: supplier.contact_info
    });
  }

  deleteSupplier(id: number): void {
    if (confirm('Are you sure you want to delete this supplier?')) {
      this.stockService.deleteSupplier(id).subscribe({
        next: () => {
          this.toastr.success('Supplier deleted.');
          this.loadSuppliers();
        },
        error: () => this.toastr.error('Failed to delete supplier.')
      });
    }
  }

  resetSupplierForm(): void {
    this.isEditingSupplier = false;
    this.editingSupplierId = null;
    this.supplierForm.reset();
  }
}
