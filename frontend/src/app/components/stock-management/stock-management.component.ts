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
  templateUrl: './stock-management.component.html',
  styleUrls: ['./stock-management.component.scss'] // Remove this line if you don't have the SCSS file!
})
export class StockManagementComponent implements OnInit {
  
  // Form
  stockForm: FormGroup;

  // Dropdown Data
  projects: any[] = [];
  sites: any[] = [];
  categories: any[] = [];
  materials: any[] = [];
  filteredMaterials: any[] = [];

  // Recent Transactions Table
  displayedColumns: string[] = ['entry_date', 'material_name', 'entry_type', 'quantity', 'reference_no', 'actions'];
  dataSource = new MatTableDataSource<any>();
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  // UI State
  loading = false;
  submitting = false;
  loadingEntries = false;
  selectedSiteId: number | null = null;

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
      category_filter: [''], // Just a UI helper
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference_no: [''],
      remarks: ['']
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadCategories();
    this.loadMaterials();
  }

  // ==========================================
  // DATA LOADING
  // ==========================================
  loadProjects(): void {
    this.projectService.getProjects().subscribe(res => this.projects = res);
  }

  loadCategories(): void {
    this.materialService.getCategories().subscribe(res => this.categories = res);
  }

  loadMaterials(): void {
    this.materialService.getMaterials().subscribe(res => {
      this.materials = res;
      this.filteredMaterials = res;
    });
  }

  // ==========================================
  // FORM INTERACTIONS
  // ==========================================
  onProjectChange(projectId: any): void {
    this.sites = [];
    this.stockForm.patchValue({ site_id: '' });
    this.selectedSiteId = null;
    this.dataSource.data = []; // Clear table

    if (projectId) {
      this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
    }
  }

  onSiteChange(siteId: any): void {
    if (siteId) {
      this.selectedSiteId = Number(siteId);
      this.loadRecentEntries();
    } else {
      this.selectedSiteId = null;
      this.dataSource.data = [];
    }
  }

  onCategoryFilterChange(categoryId: any): void {
    this.stockForm.patchValue({ material_id: '' });
    if (categoryId) {
      this.filteredMaterials = this.materials.filter(m => m.category_id === Number(categoryId));
    } else {
      this.filteredMaterials = this.materials;
    }
  }

  // ==========================================
  // TRANSACTIONS LOGIC
  // ==========================================
  submitStockTransaction(): void {
    if (this.stockForm.invalid) {
      this.stockForm.markAllAsTouched();
      return;
    }

    this.submitting = true;
    this.stockService.createStockEntry(this.stockForm.value).subscribe({
      next: () => {
        this.toastr.success('Stock transaction recorded successfully', 'Success');
        
        // Keep the Project and Site selected, reset the rest
        const currentProject = this.stockForm.get('project_id')?.value;
        const currentSite = this.stockForm.get('site_id')?.value;
        
        this.stockForm.reset({ 
          project_id: currentProject,
          site_id: currentSite,
          entry_type: 'received',
          category_filter: '' 
        });
        
        this.filteredMaterials = this.materials;
        this.loadRecentEntries(); // Refresh the table
        this.submitting = false;
      },
      error: (err) => {
        this.toastr.error(err.message || 'Failed to record transaction', 'Error');
        this.submitting = false;
      }
    });
  }

  loadRecentEntries(): void {
    if (!this.selectedSiteId) return;

    this.loadingEntries = true;
    this.stockService.getStockEntries({ site_id: this.selectedSiteId }).subscribe({
      next: (entries) => {
        // Map material names for the table
        const mappedEntries = entries.map(entry => {
          const material = this.materials.find(m => m.id === entry.material_id);
          return { ...entry, material_name: material ? material.name : 'Unknown Material' };
        });

        this.dataSource.data = mappedEntries;
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        this.loadingEntries = false;
      },
      error: () => {
        this.toastr.error('Failed to load recent transactions');
        this.loadingEntries = false;
      }
    });
  }

  deleteEntry(id: number): void {
    if (confirm('Are you sure you want to delete this transaction record? This will alter the current stock balance.')) {
      this.stockService.deleteStockEntry(id).subscribe({
        next: () => {
          this.toastr.success('Transaction deleted successfully');
          this.loadRecentEntries();
        },
        error: () => this.toastr.error('Failed to delete transaction')
      });
    }
  }

  // ==========================================
  // UI HELPERS
  // ==========================================
  getEntryTypeBadgeClass(type: string): string {
    switch (type) {
      case 'received': return 'bg-success';
      case 'used': return 'bg-danger';
      case 'returned_received': return 'bg-info text-dark';
      case 'returned_supplier': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  }

  formatEntryType(type: string): string {
    return type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
}
