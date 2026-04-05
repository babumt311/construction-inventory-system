import { Component, OnInit, ViewChild, TemplateRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { saveAs } from 'file-saver';
import { MaterialService } from '../../services/material.service';
import { Category, Material } from '../../models/material.model';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-material-management',
  templateUrl: './material-management.component.html',
  styleUrls: ['./material-management.component.scss']
})
export class MaterialManagementComponent implements OnInit {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('uploadDialog') uploadDialog!: TemplateRef<any>;
  @ViewChild('categoryDialog') categoryDialog!: TemplateRef<any>;

  // Data
  materials: Material[] = [];
  categories: Category[] = [];
  
  // Table
  displayedColumns: string[] = ['id', 'name', 'category', 'unit', 'standard_cost', 'actions'];
  dataSource = new MatTableDataSource<Material>();
  
  // Forms
  materialForm: FormGroup;
  categoryForm: FormGroup;
  
  // UI State
  loading = false;
  isEditing = false;
  currentMaterialId?: number;
  selectedFile: File | null = null;
  uploadProgress = 0;
  
  // Filters
  searchTerm = '';
  selectedCategoryId: string = ''; // Added for Category Filter

  constructor(
    private fb: FormBuilder,
    private materialService: MaterialService,
    public dialog: MatDialog,
    private toastr: ToastrService
  ) {
    this.materialForm = this.fb.group({
      name: ['', [Validators.required, Validators.minLength(2)]],
      category_id: ['', Validators.required],
      unit: [''],
      description: [''],
      standard_cost: [0, [Validators.min(0)]]
    });

    this.categoryForm = this.fb.group({
      name: ['', [Validators.required, Validators.minLength(2)]],
      description: ['']
    });
  }

  ngOnInit(): void {
    this.loadMaterials();
    this.loadCategories();
  }

  loadMaterials(): void {
    this.loading = true;
    this.materialService.getMaterials().subscribe({
      next: (materials) => {
        this.materials = materials;
        this.dataSource.data = materials;
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        
        // Custom filter logic to handle BOTH search text and category dropdown
        this.dataSource.filterPredicate = (data: Material, filter: string) => {
          const searchTerms = JSON.parse(filter);
          const textMatch = !searchTerms.text || 
                            data.name.toLowerCase().includes(searchTerms.text) || 
                            (data.description && data.description.toLowerCase().includes(searchTerms.text));
          const categoryMatch = !searchTerms.category || 
                                data.category_id.toString() === searchTerms.category;
          
          return textMatch && categoryMatch;
        };

        this.loading = false;
      },
      error: (error) => {
        this.toastr.error('Failed to load materials', 'Error');
        this.loading = false;
      }
    });
  }

  loadCategories(): void {
    this.materialService.getCategories().subscribe({
      next: (categories) => {
        this.categories = categories;
      },
      error: (error) => {
        this.toastr.error('Failed to load categories', 'Error');
      }
    });
  }

  applyFilter(): void {
    // Combine both filters into a JSON string since MatTable filter only accepts a single string
    const filterValue = {
      text: this.searchTerm.trim().toLowerCase(),
      category: this.selectedCategoryId
    };
    
    this.dataSource.filter = JSON.stringify(filterValue);

    if (this.dataSource.paginator) {
      this.dataSource.paginator.firstPage();
    }
  }

  createMaterial(): void {
    if (this.materialForm.invalid) {
      this.markFormGroupTouched(this.materialForm);
      return;
    }

    const materialData = this.materialForm.value;
    this.loading = true;

    this.materialService.createMaterial(materialData).subscribe({
      next: () => {
        this.toastr.success('Material created successfully', 'Success');
        this.loadMaterials();
        this.resetForm();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to create material', 'Error');
        this.loading = false;
      }
    });
  }

  editMaterial(material: Material): void {
    this.isEditing = true;
    this.currentMaterialId = material.id;
    this.materialForm.patchValue({
      name: material.name,
      category_id: material.category_id,
      unit: material.unit,
      description: material.description,
      standard_cost: material.standard_cost || 0
    });
    
    // Smooth scroll back up to the form
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  updateMaterial(): void {
    if (this.materialForm.invalid || !this.currentMaterialId) {
      return;
    }

    const materialData = this.materialForm.value;
    this.loading = true;

    this.materialService.updateMaterial(this.currentMaterialId, materialData).subscribe({
      next: () => {
        this.toastr.success('Material updated successfully', 'Success');
        this.loadMaterials();
        this.resetForm();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to update material', 'Error');
        this.loading = false;
      }
    });
  }

  deleteMaterial(id: number): void {
    if (confirm('Are you sure you want to delete this material? This action cannot be undone.')) {
      this.materialService.deleteMaterial(id).subscribe({
        next: () => {
          this.toastr.success('Material deleted successfully', 'Success');
          this.loadMaterials();
        },
        error: (error) => {
          this.toastr.error(error.message || 'Failed to delete material', 'Error');
        }
      });
    }
  }

  resetForm(): void {
    this.materialForm.reset({
      name: '',
      category_id: '',
      unit: '',
      description: '',
      standard_cost: 0
    });
    this.isEditing = false;
    this.currentMaterialId = undefined;
    this.loading = false;
  }

  createCategory(): void {
    if (this.categoryForm.invalid) {
      this.markFormGroupTouched(this.categoryForm);
      return;
    }

    const categoryData = this.categoryForm.value;
    this.loading = true;

    this.materialService.createCategory(categoryData).subscribe({
      next: () => {
        this.toastr.success('Category created successfully', 'Success');
        this.loadCategories();
        this.categoryForm.reset();
        this.dialog.closeAll();
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to create category', 'Error');
        this.loading = false;
      }
    });
  }

  openUploadDialog(): void {
    this.selectedFile = null;
    this.uploadProgress = 0;
    this.dialog.open(this.uploadDialog, {
      width: '500px'
    });
  }

  openCategoryDialog(): void {
    this.categoryForm.reset();
    this.dialog.open(this.categoryDialog, {
      width: '400px'
    });
  }

  onFileSelected(event: any): void {
    const file: File = event.target.files[0];
    if (file) {
      const validTypes = ['.xlsx', '.xls', '.csv'];
      const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
      
      if (!validTypes.includes(fileExt)) {
        this.toastr.error('Invalid file type. Please upload Excel or CSV file.', 'Error');
        return;
      }

      this.selectedFile = file;
    }
  }

  uploadFile(): void {
    if (!this.selectedFile) {
      this.toastr.error('Please select a file to upload', 'Error');
      return;
    }

    this.uploadProgress = 0;
    this.loading = true;

    const progressInterval = setInterval(() => {
      if (this.uploadProgress < 90) {
        this.uploadProgress += 10;
      }
    }, 200);

    this.materialService.uploadMaterials(this.selectedFile).subscribe({
      next: (response) => {
        clearInterval(progressInterval);
        this.uploadProgress = 100;
        
        this.toastr.success(
          `File uploaded successfully! Processed: ${response.rows_processed}, Successful: ${response.rows_successful}, Failed: ${response.rows_failed}`,
          'Success'
        );
        
        this.loadMaterials();
        this.dialog.closeAll();
        this.loading = false;
      },
      error: (error) => {
        clearInterval(progressInterval);
        this.toastr.error(error.message || 'File upload failed', 'Error');
        this.loading = false;
      }
    });
  }

  downloadTemplate(): void {
    this.materialService.downloadTemplate().subscribe({
      next: (blob) => {
        saveAs(blob, 'material_template.xlsx');
        this.toastr.success('Template downloaded successfully', 'Success');
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to download template', 'Error');
      }
    });
  }

  getCategoryName(categoryId: number): string {
    const category = this.categories.find(c => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }

  private markFormGroupTouched(formGroup: FormGroup): void {
    Object.values(formGroup.controls).forEach(control => {
      control.markAsTouched();
      if (control instanceof FormGroup) {
        this.markFormGroupTouched(control);
      }
    });
  }
}
