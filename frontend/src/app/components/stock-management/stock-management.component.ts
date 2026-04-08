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
  
  activeTab: 'stock' | 'category' | 'material' = 'stock';
  
  // Forms
  stockForm: FormGroup;
  categoryForm: FormGroup;
  materialForm: FormGroup;

  // Data arrays
  projects: any[] = [];
  sites: any[] = [];
  categories: any[] = [];
  materials: any[] = [];

  // Table variables
  stockColumns: string[] = ['entry_date', 'material_name', 'entry_type', 'quantity', 'reference_no', 'actions'];
  stockDataSource = new MatTableDataSource<any>();
  @ViewChild('stockPaginator') stockPaginator!: MatPaginator;
  @ViewChild('stockSort') stockSort!: MatSort;
  
  selectedSiteId: number | null = null;
  loadingStockEntries = false;
  submittingStock = false;

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private materialService: MaterialService,
    private projectService: ProjectService,
    private toastr: ToastrService
  ) {
    // --- MASTER-DETAIL FORM DEFINITION ---
    this.stockForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: [''],
      from_site_id: [''],
      to_site_id: [''],
      invoice_no: ['', Validators.required], // Made mandatory
      entry_type: ['received', Validators.required],
      remarks: [''],
      items: this.fb.array([]) // Array to hold multiple materials
    });

    // Site Validation Logic based on Transfer type
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

    // Category and Material Forms
    this.categoryForm = this.fb.group({ name: ['', Validators.required], description: [''] });
    this.materialForm = this.fb.group({ name: ['', Validators.required], category_id: ['', Validators.required], unit: ['Bags'], description: [''] });
  }

  ngOnInit(): void {
    this.loadProjects(); 
    this.loadCategories(); 
    this.loadMaterials();
    this.addItem(); // Add one blank row by default
    
    const savedTab = sessionStorage.getItem('activeInventoryTab');
    if (savedTab && ['stock', 'category', 'material'].includes(savedTab)) this.switchTab(savedTab as 'stock' | 'category' | 'material');
  }

  switchTab(tab: 'stock' | 'category' | 'material'): void {
    this.activeTab = tab;
    sessionStorage.setItem('activeInventoryTab', tab);
  }

  // --- FORM ARRAY GETTER & METHODS ---
  get items(): FormArray {
    return this.stockForm.get('items') as FormArray;
  }

  addItem(): void {
    const itemGroup = this.fb.group({
      category_id: [''], // Optional filter
      material_id: ['', Validators.required],
      quantity: [1, [Validators.required, Validators.min(0.01)]],
      unit_price: [0, [Validators.required, Validators.min(0)]],
      tax_percent: [0, [Validators.min(0)]],
      tax_amount: [{ value: 0, disabled: true }], // Calculated field
      total_cost: [{ value: 0, disabled: true }]  // Calculated field
    });

    // Auto-calculate logic for this specific row
    itemGroup.valueChanges.subscribe(val => {
      const qty = val.quantity || 0;
      const price = val.unit_price || 0;
      const taxPct = val.tax_percent || 0;
      
      const taxAmt = price * (taxPct / 100);
      const total = (price + taxAmt) * qty;

      // Update without triggering infinite loop
      itemGroup.patchValue({
        tax_amount: parseFloat(taxAmt.toFixed(2)),
        total_cost: parseFloat(total.toFixed(2))
      }, { emitEvent: false });
    });

    this.items.push(itemGroup);
  }

  removeItem(index: number): void {
    if (this.items.length > 1) {
      this.items.removeAt(index);
    } else {
      this.toastr.warning('You must have at least one material entry.');
    }
  }

  // --- DATA LOADING ---
  loadProjects(): void { this.projectService.getProjects().subscribe(res => this.projects = res); }
  loadCategories(): void { this.materialService.getCategories().subscribe(res => this.categories = res); }
  loadMaterials(): void { this.materialService.getMaterials().subscribe(res => this.materials = res); }

  getFilteredMaterials(categoryId: any): any[] {
    if (!categoryId) return this.materials;
    return this.materials.filter(m => m.category_id === Number(categoryId));
  }

  onProjectChange(projectId: any): void {
    this.sites = []; 
    this.stockForm.patchValue({ site_id: '', from_site_id: '', to_site_id: '' }); 
    this.selectedSiteId = null; 
    this.stockDataSource.data = [];
    if (projectId) this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
  }

  onSiteChange(siteId: any): void { 
    if (siteId) { 
      this.selectedSiteId = Number(siteId); 
      this.loadStockEntries(); 
    } else { 
      this.selectedSiteId = null; 
      this.stockDataSource.data = []; 
    } 
  }

  // --- SUBMIT LOGIC ---
  submitStock(): void {
    if (this.stockForm.invalid) { 
      this.stockForm.markAllAsTouched(); 
      this.toastr.error('Please fill all mandatory fields correctly.');
      return; 
    }

    this.submittingStock = true;
    const formValue = this.stockForm.getRawValue(); // gets raw value including disabled calculated fields
    const apiRequests: any[] = [];

    // Loop through each material row and create a separate transaction
    formValue.items.forEach((item: any) => {
      const basePayload = {
        project_id: formValue.project_id,
        reference_no: formValue.invoice_no, // using reference_no for invoice
        material_id: item.material_id,
        quantity: item.quantity,
        unit_price: item.unit_price,
        tax_percent: item.tax_percent,
        tax_amount: item.tax_amount,
        total_cost: item.total_cost
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
        const payload: any = { ...basePayload, site_id: formValue.site_id, entry_type: formValue.entry_type, remarks: formValue.remarks };
        apiRequests.push(this.stockService.createStockEntry(payload));
      }
    });

    // Execute all requests at once
    forkJoin(apiRequests).subscribe({
      next: () => {
        this.toastr.success(`Successfully saved ${formValue.items.length} material entries!`);
        
        // Reset form but keep project and site selected
        const currentProject = formValue.project_id;
        const currentSite = formValue.site_id;
        this.stockForm.reset({ project_id: currentProject, site_id: currentSite, entry_type: 'received' });
        this.items.clear();
        this.addItem(); // add blank row back
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
      error: () => { this.loadingStockEntries = false; }
    });
  }
}
