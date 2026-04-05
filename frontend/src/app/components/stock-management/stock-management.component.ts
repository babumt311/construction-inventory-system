import { Component, OnInit, ViewChild, TemplateRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { MatDialog } from '@angular/material/dialog';
import { ToastrService } from 'ngx-toastr';

import { StockService } from '../../services/stock.service';
import { MaterialService } from '../../services/material.service';
import { ProjectService } from '../../services/project.service';

@Component({
  selector: 'app-stock-management',
  templateUrl: './stock-management.component.html',
  styleUrls: ['./stock-management.component.scss']
})
export class StockManagementComponent implements OnInit {
  // Forms
  stockForm: FormGroup;
  materialForm: FormGroup;
  categoryForm: FormGroup;

  // Form Dropdown Data
  projects: any[] = [];
  sites: any[] = [];
  categories: any[] = [];
  materials: any[] = [];
  filteredMaterialsForStock: any[] = [];

  // Material Table Data
  materialColumns: string[] = ['name', 'category', 'unit', 'standard_cost', 'actions'];
  materialDataSource = new MatTableDataSource<any>();
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('categoryDialog') categoryDialog!: TemplateRef<any>;

  // UI State
  loading = false;
  submittingStock = false;
  submittingMaterial = false;
  isEditingMaterial = false;
  editingMaterialId: number | null = null;
  
  // Table Filters
  materialSearchTerm = '';
  selectedCategoryId = '';

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private materialService: MaterialService,
    private projectService: ProjectService,
    private toastr: ToastrService,
    public dialog: MatDialog
  ) {
    // 1. Record Stock Transaction Form
    this.stockForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      category_filter: [''], // UI helper, not sent to backend
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference_no: [''],
      remarks: ['']
    });

    // 2. Create/Edit Material Form
    this.materialForm = this.fb.group({
      name: ['', Validators.required],
      category_id: ['', Validators.required],
      unit: ['Bags'],
      standard_cost: [0, Validators.min(0)],
      description: ['']
    });

    // 3. Add Category Form (Modal)
    this.categoryForm = this.fb.group({
      name: ['', Validators.required],
      description: ['']
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
    this.loading = true;
    this.materialService.getMaterials().subscribe({
      next: (res) => {
        this.materials = res;
        this.filteredMaterialsForStock = res; // Populate dropdown
        
        // Populate Table
        this.materialDataSource.data = res;
        this.materialDataSource.paginator = this.paginator;
        this.materialDataSource.sort = this.sort;
        
        // Strict typing for filter
        this.materialDataSource.filterPredicate = (data: any, filter: string): boolean => {
          try {
            const searchTerms = JSON.parse(filter);
            const textMatch = Boolean(
              !searchTerms.text || 
              data.name.toLowerCase().includes(searchTerms.text) || 
              (data.description ? data.description.toLowerCase().includes(searchTerms.text) : false)
            );
            const categoryMatch = Boolean(
              !searchTerms.category || 
              data.category_id.toString() === searchTerms.category
            );
            return textMatch && categoryMatch;
          } catch (e) {
            return true; 
          }
        };
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to load materials');
        this.loading = false;
      }
    });
  }

  // ==========================================
  // STOCK TRANSACTION LOGIC
  // ==========================================
  onProjectChange(projectId: any): void {
    this.sites = [];
    this.stockForm.patchValue({ site_id: '' });
    if (projectId) {
      this.projectService.getProjectSites(Number(projectId)).subscribe(res => this.sites = res);
    }
  }

  onStockCategoryFilterChange(categoryId: any): void {
    this.stockForm.patchValue({ material_id: '' });
    if (categoryId) {
      this.filteredMaterialsForStock = this.materials.filter(m => m.category_id === Number(categoryId));
    } else {
      this.filteredMaterialsForStock = this.materials;
    }
  }

  submitStockTransaction(): void {
    if (this.stockForm.invalid) {
      this.stockForm.markAllAsTouched();
      return;
    }
    this.submittingStock = true;
    this.stockService.createStockEntry(this.stockForm.value).subscribe({
      next: () => {
        this.toastr.success('Stock transaction recorded successfully');
        this.stockForm.reset({ entry_type: 'received' }); 
        this.filteredMaterialsForStock = this.materials; 
        this.submittingStock = false;
      },
      error: () => {
        this.toastr.error('Failed to record transaction');
        this.submittingStock = false;
      }
    });
  }

  // ==========================================
  // MATERIAL MANAGEMENT LOGIC
  // ==========================================
  submitMaterial(): void {
    if (this.materialForm.invalid) {
      this.materialForm.markAllAsTouched();
      return;
    }
    
    this.submittingMaterial = true;
    const payload = this.materialForm.value;

    if (this.isEditingMaterial && this.editingMaterialId) {
      this.materialService.updateMaterial(this.editingMaterialId, payload).subscribe({
        next: () => {
          this.toastr.success('Material updated successfully');
          this.resetMaterialForm();
          this.loadMaterials(); // Refresh table
        },
        error: () => {
          this.toastr.error('Failed to update material');
          this.submittingMaterial = false;
        }
      });
    } else {
      this.materialService.createMaterial(payload).subscribe({
        next: () => {
          this.toastr.success('Material created successfully');
          this.resetMaterialForm();
          this.loadMaterials(); // Refresh table
        },
        error: () => {
          this.toastr.error('Failed to create material');
          this.submittingMaterial = false;
        }
      });
    }
  }

  editMaterial(material: any): void {
    this.isEditingMaterial = true;
    this.editingMaterialId = material.id;
    this.materialForm.patchValue({
      name: material.name,
      category_id: material.category_id,
      unit: material.unit,
      standard_cost: material.standard_cost,
      description: material.description
    });
    // Scroll up to the form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  deleteMaterial(id: number): void {
    if (confirm('Are you sure you want to delete this material?')) {
      this.materialService.deleteMaterial(id).subscribe({
        next: () => {
          this.toastr.success('Material deleted successfully');
          this.loadMaterials();
        },
        error: () => this.toastr.error('Failed to delete material')
      });
    }
  }

  resetMaterialForm(): void {
    this.isEditingMaterial = false;
    this.editingMaterialId = null;
    this.submittingMaterial = false;
    this.materialForm.reset({ unit: 'Bags', standard_cost: 0 });
  }

  // ==========================================
  // TABLE FILTERING
  // ==========================================
  applyMaterialFilter(): void {
    const filterValue = {
      text: this.materialSearchTerm.trim().toLowerCase(),
      category: this.selectedCategoryId
    };
    this.materialDataSource.filter = JSON.stringify(filterValue);
    if (this.materialDataSource.paginator) {
      this.materialDataSource.paginator.firstPage();
    }
  }

  getCategoryName(categoryId: number): string {
    const category = this.categories.find(c => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }

  // ==========================================
  // CATEGORY DIALOG
  // ==========================================
  openCategoryDialog(): void {
    this.categoryForm.reset();
    this.dialog.open(this.categoryDialog, { width: '400px' });
  }

  submitCategory(): void {
    if (this.categoryForm.invalid) return;
    this.materialService.createCategory(this.categoryForm.value).subscribe({
      next: () => {
        this.toastr.success('Category created');
        this.loadCategories();
        this.dialog.closeAll();
      },
      error: () => this.toastr.error('Failed to create category')
    });
  }
}
