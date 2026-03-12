import { Component, OnInit, ViewChild, TemplateRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { MatDialog } from '@angular/material/dialog';
import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { StockEntry, StockEntryType, StockEntryCreateRequest } from '../../models/stock.model';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-stock-entry',
  templateUrl: './stock-entry.component.html',
  styleUrls: ['./stock-entry.component.scss']
})
export class StockEntryComponent implements OnInit {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('detailsDialog') detailsDialog!: TemplateRef<any>;

  // Data
  projects: Project[] = [];
  sites: Site[] = [];
  materials: Material[] = [];
  stockEntries: StockEntry[] = [];
  selectedEntry: StockEntry | null = null;
  
  // Forms
  entryForm: FormGroup;
  filterForm: FormGroup;
  
  // Table
  displayedColumns: string[] = ['date', 'site', 'material', 'type', 'quantity', 'supplier', 'actions'];
  dataSource = new MatTableDataSource<StockEntry>();
  
  // UI State
  loading = false;
  isEditing = false;
  currentEntryId?: number;
  selectedProjectId?: number;
  selectedSiteId?: number;
  StockEntryType = StockEntryType;
  entryTypes = [
    { value: StockEntryType.RECEIVED, label: 'Received', icon: 'fas fa-arrow-down', color: 'success' },
    { value: StockEntryType.USED, label: 'Used', icon: 'fas fa-arrow-up', color: 'danger' },
    { value: StockEntryType.RETURNED_RECEIVED, label: 'Return Received', icon: 'fas fa-undo', color: 'warning' },
    { value: StockEntryType.RETURNED_SUPPLIER, label: 'Return to Supplier', icon: 'fas fa-truck-loading', color: 'secondary' }
  ];

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    private dialog: MatDialog,
    private toastr: ToastrService
  ) {
    this.entryForm = this.fb.group({
      site_id: ['', Validators.required],
      material_id: ['', Validators.required],
      entry_type: ['', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      supplier_name: [''],
      invoice_no: [''],
      reference: [''],
      remarks: [''],
      entry_date: [new Date()]
    });

    this.filterForm = this.fb.group({
      site_id: [''],
      material_id: [''],
      entry_type: [''],
      start_date: [''],
      end_date: ['']
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadMaterials();
    this.loadStockEntries();
  }

  loadProjects(): void {
    this.projectService.getProjects().subscribe({
      next: (projects) => {
        this.projects = projects;
      },
      error: (error) => {
        this.toastr.error('Failed to load projects', 'Error');
      }
    });
  }

  loadMaterials(): void {
    this.materialService.getMaterials().subscribe({
      next: (materials) => {
        this.materials = materials;
      },
      error: (error) => {
        this.toastr.error('Failed to load materials', 'Error');
      }
    });
  }

  loadStockEntries(params?: any): void {
    this.loading = true;
    this.stockService.getStockEntries(params).subscribe({
      next: (entries) => {
        this.stockEntries = entries;
        this.dataSource.data = entries;
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error('Failed to load stock entries', 'Error');
        this.loading = false;
      }
    });
  }

  onProjectChange(projectId: number): void {
    this.selectedProjectId = projectId;
    this.sites = [];
    this.entryForm.patchValue({ site_id: '' });
    
    if (projectId) {
      this.projectService.getProjectSites(projectId).subscribe({
        next: (sites) => {
          this.sites = sites;
        },
        error: (error) => {
          this.toastr.error('Failed to load sites', 'Error');
        }
      });
    }
  }

  createEntry(): void {
    if (this.entryForm.invalid) {
      this.markFormGroupTouched(this.entryForm);
      return;
    }

    const entryData: StockEntryCreateRequest = this.entryForm.value;
    this.loading = true;

    this.stockService.createStockEntry(entryData).subscribe({
      next: () => {
        this.toastr.success('Stock entry created successfully', 'Success');
        this.loadStockEntries();
        this.resetForm();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to create stock entry', 'Error');
        this.loading = false;
      }
    });
  }

  updateEntry(): void {
    if (this.entryForm.invalid || !this.currentEntryId) {
      return;
    }

    const entryData = this.entryForm.value;
    this.loading = true;

    this.stockService.updateStockEntry(this.currentEntryId, entryData).subscribe({
      next: () => {
        this.toastr.success('Stock entry updated successfully', 'Success');
        this.loadStockEntries();
        this.resetForm();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to update stock entry', 'Error');
        this.loading = false;
      }
    });
  }

  deleteEntry(id: number): void {
    if (confirm('Are you sure you want to delete this stock entry?')) {
      this.stockService.deleteStockEntry(id).subscribe({
        next: () => {
          this.toastr.success('Stock entry deleted successfully', 'Success');
          this.loadStockEntries();
        },
        error: (error) => {
          this.toastr.error(error.message || 'Failed to delete stock entry', 'Error');
        }
      });
    }
  }

  editEntry(entry: StockEntry): void {
    this.isEditing = true;
    this.currentEntryId = entry.id;
    
    if (entry.site?.project_id) {
      this.onProjectChange(entry.site.project_id);
    }
    
    this.entryForm.patchValue({
      site_id: entry.site_id,
      material_id: entry.material_id,
      entry_type: entry.entry_type,
      quantity: entry.quantity,
      supplier_name: entry.supplier_name,
      invoice_no: entry.invoice_no,
      reference: entry.reference,
      remarks: entry.remarks,
      entry_date: new Date(entry.entry_date)
    });
  }

  private markFormGroupTouched(formGroup: any): void {
  Object.values(formGroup.controls).forEach((control: any) => {
    control.markAsTouched();

    if (control.controls) {
      this.markFormGroupTouched(control);
      }
    });
  }

  showEntryDetails(entry: StockEntry): void {
    this.selectedEntry = entry;
    this.dialog.open(this.detailsDialog, {
      width: '600px',
      data: { entry }
    });
  }

  resetForm(): void {
    this.entryForm.reset({
      site_id: ''
    });
  }  
}
