import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ToastrService } from 'ngx-toastr';
import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';

@Component({
  selector: 'app-stock-management',
  templateUrl: './stock-management.component.html'
})
export class StockManagementComponent implements OnInit {
  entryForm: FormGroup;
  materialForm: FormGroup;
  categoryForm: FormGroup; // NEW: Form for creating categories

  projects: Project[] = [];
  entrySites: Site[] = [];
  materials: Material[] = [];
  categories: any[] = [];
  
  loading = false;
  showCategoryModal = false; // NEW: Controls the popup

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    private toastr: ToastrService
  ) {
    this.entryForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference: [''],
      remarks: ['']
    });

    this.materialForm = this.fb.group({
      name: ['', Validators.required],
      category_id: ['', Validators.required],
      unit: ['bags', Validators.required],
      standard_cost: [0, Validators.min(0)],
      description: ['']
    });

    // NEW: Initialize Category Form
    this.categoryForm = this.fb.group({
      name: ['', Validators.required],
      description: ['']
    });
  }

  ngOnInit(): void {
    this.loadInitialData();
  }

  loadInitialData(): void {
    this.projectService.getProjects().subscribe(p => this.projects = p);
    this.materialService.getMaterials().subscribe(m => this.materials = m);
    this.materialService.getCategories().subscribe(c => this.categories = c);
  }

  onProjectChange(projectId: any): void {
    const id = Number(projectId);
    this.entrySites = [];
    if (id) {
      this.projectService.getProjectSites(id).subscribe(sites => this.entrySites = sites);
    }
  }

  submitStockEntry(): void {
    if (this.entryForm.invalid) return;
    this.loading = true;
    this.stockService.createStockEntry(this.entryForm.value).subscribe({
      next: () => {
        this.toastr.success('Stock entry recorded successfully!');
        this.entryForm.reset({ entry_type: 'received' });
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to record entry.');
        this.loading = false;
      }
    });
  }

  submitMaterial(): void {
    if (this.materialForm.invalid) return;
    this.loading = true;
    
    this.materialService.createMaterial(this.materialForm.value).subscribe({
      next: () => {
        this.toastr.success('New Material created successfully!');
        this.materialForm.reset({ unit: 'bags', standard_cost: 0 });
        this.loadInitialData(); 
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to create material.');
        this.loading = false;
      }
    });
  }

  // --- NEW: CATEGORY LOGIC ---
  openCategoryModal(): void {
    this.categoryForm.reset();
    this.showCategoryModal = true;
  }

  submitCategory(): void {
    if (this.categoryForm.invalid) return;
    this.loading = true;

    this.materialService.createCategory(this.categoryForm.value).subscribe({
      next: (newCategory) => {
        this.toastr.success('Category created!');
        this.showCategoryModal = false;
        
        // Reload categories and auto-select the new one
        this.materialService.getCategories().subscribe(c => {
          this.categories = c;
          if (newCategory && newCategory.id) {
            this.materialForm.patchValue({ category_id: newCategory.id });
          }
          this.loading = false;
        });
      },
      error: () => {
        this.toastr.error('Failed to create category.');
        this.loading = false;
      }
    });
  }
}
