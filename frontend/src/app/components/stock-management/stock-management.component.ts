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

  projects: Project[] = [];
  entrySites: Site[] = [];
  materials: Material[] = [];
  categories: any[] = [];
  loading = false;

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    private toastr: ToastrService
  ) {
    // 1. Stock Entry Form
    this.entryForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference: [''],
      remarks: ['']
    });

    // 2. Material Creation Form
    this.materialForm = this.fb.group({
      name: ['', Validators.required],
      category_id: ['', Validators.required],
      unit: ['kg', Validators.required],
      standard_cost: [0, Validators.min(0)],
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
    
    // Assuming your MaterialService has a createMaterial method
    this.materialService.createMaterial(this.materialForm.value).subscribe({
      next: () => {
        this.toastr.success('New Material created successfully!');
        this.materialForm.reset({ unit: 'kg', standard_cost: 0 });
        this.loadInitialData(); // Refresh dropdowns!
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to create material.');
        this.loading = false;
      }
    });
  }
}
