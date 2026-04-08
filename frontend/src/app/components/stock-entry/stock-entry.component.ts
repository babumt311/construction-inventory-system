import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { ToastrService } from 'ngx-toastr';

import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { Project, Site } from '../../models/project.model';
import { Material, Category } from '../../models/material.model';

@Component({
  selector: 'app-stock-entry',
  templateUrl: './stock-entry.component.html',
  styleUrls: ['./stock-entry.component.scss']
})
export class StockEntryComponent implements OnInit {
  
  stockForm!: FormGroup;
  
  projects: Project[] = [];
  sites: Site[] = [];
  toSites: Site[] = []; // For transfers
  categories: Category[] = [];
  materials: Material[] = [];
  
  recentTransactions: any[] = [];
  loading = false;
  submitting = false;

  transactionTypes = [
    { value: 'received', label: 'Received (Delivery IN)' },
    { value: 'used', label: 'Consumed (Used OUT)' },
    { value: 'transfer', label: 'Site-to-Site Transfer' },
    { value: 'returned_supplier', label: 'Returned to Supplier' }
  ];

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    private toastr: ToastrService
  ) {
    this.initForm();
  }

  ngOnInit(): void {
    this.loadInitialData();
    this.setupFormListeners();
  }

  initForm(): void {
    this.stockForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      to_site_id: [''], // Only required for transfers
      transaction_type: ['received', Validators.required],
      invoice_no: ['', Validators.required],
      remarks: [''],
      items: this.fb.array([])
    });
    
    // Start with one empty row
    this.addItem();
  }

  get items(): FormArray {
    return this.stockForm.get('items') as FormArray;
  }

  addItem(): void {
    const itemForm = this.fb.group({
      category_id: [''],
      material_id: ['', Validators.required],
      quantity: [null, [Validators.required, Validators.min(0.01)]],
      unit_price: [null, [Validators.required, Validators.min(0)]],
      tax_percent: [0, [Validators.min(0)]],
      tax_amount: [{ value: 0, disabled: true }],
      total_cost: [{ value: 0, disabled: true }]
    });

    // Auto-calculate tax and totals when inputs change
    itemForm.valueChanges.subscribe(val => {
      const qty = Number(val.quantity || 0);
      const price = Number(val.unit_price || 0);
      const taxPct = Number(val.tax_percent || 0);

      const taxAmt = price * (taxPct / 100);
      const total = (price + taxAmt) * qty;

      itemForm.patchValue({
        tax_amount: taxAmt,
        total_cost: total
      }, { emitEvent: false });
    });

    this.items.push(itemForm);
  }

  removeItem(index: number): void {
    if (this.items.length > 1) {
      this.items.removeAt(index);
    } else {
      this.toastr.warning('You must have at least one material entry.');
    }
  }

  loadInitialData(): void {
    this.loading = true;
    forkJoin({
      projects: this.projectService.getProjects(),
      categories: this.materialService.getCategories(),
      materials: this.materialService.getMaterials()
    }).subscribe({
      next: (res) => {
        this.projects = res.projects;
        this.categories = res.categories;
        this.materials = res.materials;
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to load master data');
        this.loading = false;
      }
    });
  }

  setupFormListeners(): void {
    // Load sites when project changes
    this.stockForm.get('project_id')?.valueChanges.subscribe(projectId => {
      this.stockForm.patchValue({ site_id: '', to_site_id: '' });
      this.sites = [];
      this.toSites = [];
      
      if (projectId) {
        this.projectService.getProjectSites(projectId).subscribe(sites => {
          this.sites = sites.filter(s => s.status === 'active' || s.status === 'IN_PROGRESS');
          this.toSites = [...this.sites]; 
        });
      }
    });

    // Handle Site-to-Site transfer validation
    this.stockForm.get('transaction_type')?.valueChanges.subscribe(type => {
      const toSiteCtrl = this.stockForm.get('to_site_id');
      if (type === 'transfer') {
        toSiteCtrl?.setValidators([Validators.required]);
      } else {
        toSiteCtrl?.clearValidators();
        toSiteCtrl?.setValue('');
      }
      toSiteCtrl?.updateValueAndValidity();
    });

    // Load ledger when site changes
    this.stockForm.get('site_id')?.valueChanges.subscribe(siteId => {
      if (siteId) {
        this.loadRecentLedger(siteId);
      } else {
        this.recentTransactions = [];
      }
    });
  }

  getFilteredMaterials(categoryId: any): Material[] {
    if (!categoryId) return this.materials;
    return this.materials.filter(m => m.category_id === Number(categoryId));
  }

  loadRecentLedger(siteId: number): void {
    this.stockService.getSiteStockSummary(siteId).subscribe(data => {
      this.recentTransactions = data;
    });
  }

  submitTransaction(): void {
    if (this.stockForm.invalid) {
      this.stockForm.markAllAsTouched();
      this.toastr.error('Please fill all mandatory fields correctly.');
      return;
    }

    this.submitting = true;
    const formData = this.stockForm.getRawValue(); // gets disabled fields too (totals)
    
    const isTransfer = formData.transaction_type === 'transfer';
    const apiRequests: any[] = [];

    // Generate API payload for each material row
    formData.items.forEach((item: any) => {
      
      const basePayload = {
        material_id: item.material_id,
        quantity: item.quantity,
        unit_cost: Number(item.unit_price) + Number(item.tax_amount), // Final cost per unit
        total_cost: item.total_cost,
        invoice_no: formData.invoice_no,
        remarks: formData.remarks
      };

      if (isTransfer) {
        // Site-to-Site requires 2 entries: OUT from source, IN to destination
        const transferOut: any = { ... };
          ...basePayload,
          site_id: formData.site_id,
          entry_type: 'used', // Taking it out of inventory
          remarks: `Transfer OUT to Site ID ${formData.to_site_id} | ${formData.remarks}`
        };
        
        const transferIn: any = { ... };
          ...basePayload,
          site_id: formData.to_site_id,
          entry_type: 'received', // Putting it into new inventory
          remarks: `Transfer IN from Site ID ${formData.site_id} | ${formData.remarks}`
        };

        apiRequests.push(this.stockService.createStockEntry(transferOut));
        apiRequests.push(this.stockService.createStockEntry(transferIn));
        
      } else {
        // Standard single transaction
        const entry = {
          ...basePayload,
          site_id: formData.site_id,
          entry_type: formData.transaction_type
        };
        apiRequests.push(this.stockService.createStockEntry(entry));
      }
    });

    // Execute all requests concurrently
    forkJoin(apiRequests).subscribe({
      next: () => {
        this.toastr.success(`Successfully saved ${formData.items.length} material entries!`);
        
        // Reset the form but keep the project and site selected for easy continued entry
        const currentProject = this.stockForm.get('project_id')?.value;
        const currentSite = this.stockForm.get('site_id')?.value;
        
        this.stockForm.reset();
        this.items.clear();
        this.addItem(); // add one blank row back
        
        this.stockForm.patchValue({
          project_id: currentProject,
          site_id: currentSite,
          transaction_type: 'received'
        });

        if (currentSite) this.loadRecentLedger(currentSite);
        this.submitting = false;
      },
      error: (err) => {
        this.toastr.error('Failed to save some entries. Check balances.');
        console.error(err);
        this.submitting = false;
      }
    });
  }
}
