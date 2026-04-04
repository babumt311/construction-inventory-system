import { Component, OnInit, ViewChild, TemplateRef, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { Chart, registerables } from 'chart.js';
import { ToastrService } from 'ngx-toastr';

import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';

import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';

import { StockBalance } from '../../models/stock.model';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';

@Component({
  selector: 'app-stock-balance',
  templateUrl: './stock-balance.component.html',
  styleUrls: ['./stock-balance.component.scss']
})
export class StockBalanceComponent implements OnInit, OnDestroy {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('materialDetails') materialDetailsDialog!: TemplateRef<any>;

  projects: Project[] = [];
  sites: Site[] = [];
  materials: Material[] = [];
  categories: any[] = [];
  stockBalances: any[] = []; // Allows our dynamically added site_name
  selectedMaterial: Material | null = null;
  materialStockHistory: any[] = [];
  
  filterForm: FormGroup;
  
  // ADDED 'site' to the displayed columns array
  displayedColumns: string[] = ['material', 'category', 'site', 'current_balance', 'opening_balance', 'total_received', 'total_used', 'updated_at', 'status'];
  dataSource = new MatTableDataSource<any>();
  
  stockChart: Chart | null = null;
  materialChart: Chart | null = null;
  loading = false;
  selectedProjectId?: number;
  selectedSiteId?: number;
  viewMode: 'table' | 'cards' = 'table';

  constructor(
    private fb: FormBuilder,
    private stockService: StockService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    public dialog: MatDialog,
    private toastr: ToastrService
  ) {
    Chart.register(...registerables);
    
    this.filterForm = this.fb.group({
      project_id: [''],
      site_id: [''],
      material_id: [''],
      start_date: [''],
      end_date: [''],
      show_negative_only: [false]
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadMaterials();
    this.loadCategories();
    this.filterForm.valueChanges.subscribe(() => this.applyFilters());
  }

  loadProjects(): void {
    this.projectService.getProjects().subscribe({
      next: (projects) => this.projects = projects,
      error: () => this.toastr.error('Failed to load projects')
    });
  }

  loadMaterials(): void {
    this.materialService.getMaterials().subscribe({
      next: (materials) => this.materials = materials,
      error: () => this.toastr.error('Failed to load materials')
    });
  }

  loadCategories(): void {
    this.materialService.getCategories().subscribe(categories => this.categories = categories);
  }

  // ==========================================
  // UPDATED: Fetch All Sites for a Project
  // ==========================================
  onProjectChange(projectId: any): void {
    const id = projectId ? Number(projectId) : 0;
    this.selectedProjectId = id;
    this.sites = [];
    this.selectedSiteId = undefined;
    this.stockBalances = [];
    
    // Reset site filter silently
    this.filterForm.patchValue({ site_id: '' }, { emitEvent: false });
    this.applyFilters();

    if (id) {
      this.loading = true;
      this.projectService.getProjectSites(id).subscribe(sites => {
        this.sites = sites.filter(site => site.status === 'ACTIVE' || site.status === 'active' || site.status === 'IN_PROGRESS');
        
        if (this.sites.length === 0) {
          this.loading = false;
          return;
        }

        // Fetch stock for EVERY site in the project and combine them
        let loadedCount = 0;
        this.sites.forEach(site => {
          this.stockService.getSiteStockSummary(site.id).subscribe({
            next: (balances) => {
              // Tag the data with the Site Name so we can show it in the table
              const taggedBalances = balances.map((b: any) => ({ ...b, site_name: site.name, site_id: site.id }));
              this.stockBalances = [...this.stockBalances, ...taggedBalances];
              
              loadedCount++;
              if (loadedCount === this.sites.length) {
                this.loading = false;
                this.applyFilters();
              }
            },
            error: () => {
              loadedCount++;
              if (loadedCount === this.sites.length) {
                this.loading = false;
                this.applyFilters();
              }
            }
          });
        });
      });
    }
  }

  onSiteChange(siteId: any): void {
    this.selectedSiteId = siteId ? Number(siteId) : undefined;
    // We already have all the data! Just re-run the local filter.
    this.applyFilters();
  }

  // ==========================================
  // FILTER LOGIC
  // ==========================================
  applyFilters(): void {
    const filters = this.filterForm.value;
    let filteredData = [...this.stockBalances]; // Copy array
    
    // NEW: Filter by specific Site if selected
    if (filters.site_id) {
      filteredData = filteredData.filter(b => Number(b.site_id) === Number(filters.site_id));
    }

    if (filters.material_id) {
      filteredData = filteredData.filter(b => Number(b.material_id) === Number(filters.material_id));
    }
    
    if (filters.start_date) {
      const start = new Date(filters.start_date);
      start.setHours(0, 0, 0, 0);
      const startTime = start.getTime();
      
      filteredData = filteredData.filter((b: any) => {
        const rawDate = b.updated_at || b.created_at || b.last_updated || b.entry_date;
        if (!rawDate) return true; // Keep items with no date tracking
        return new Date(rawDate).getTime() >= startTime;
      });
    }

    if (filters.end_date) {
      const end = new Date(filters.end_date);
      end.setHours(23, 59, 59, 999);
      const endTime = end.getTime();
      
      filteredData = filteredData.filter((b: any) => {
        const rawDate = b.updated_at || b.created_at || b.last_updated || b.entry_date;
        if (!rawDate) return true; // Keep items with no date tracking
        return new Date(rawDate).getTime() <= endTime;
      });
    }
    
    if (filters.show_negative_only) {
      filteredData = filteredData.filter(b => b.has_negative_balance);
    }
    
    this.dataSource.data = filteredData;
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
    this.createStockChart(filteredData);
  }

  // ==========================================
  // SUMMARY CALCULATORS
  // ==========================================
  getHealthyStockCount(): number { return this.dataSource.data.filter(b => !b.has_negative_balance && b.current_balance > 0).length; }
  getLowStockCount(): number { return this.dataSource.data.filter(b => b.current_balance < 10 && !b.has_negative_balance).length; }
  calculateStockValue(): number {
    return this.dataSource.data.reduce((total, balance) => {
      const material = this.materials.find(m => m.id === balance.material_id);
      return total + (balance.current_balance * (material?.standard_cost || 0));
    }, 0);
  }

  getCategoryName(categoryId: number | undefined): string {
    const category = this.categories?.find((c: any) => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }
  getMaterial(materialId: number | undefined): any { return this.materials?.find(m => m.id === materialId); }
  getCurrentStock(materialId: number | undefined): number {
    const balance = this.stockBalances?.find(b => b.material_id === materialId);
    return balance ? balance.current_balance : 0;
  }
  getStockStatus(balance: any): string {
    if (!balance) return 'secondary';
    return balance.has_negative_balance ? 'danger' : (balance.current_balance < 10 ? 'warning' : 'success');
  }
  getStockStatusText(balance: any): string {
    if (!balance) return 'Unknown';
    return balance.has_negative_balance ? 'Negative Stock' : (balance.current_balance < 10 ? 'Low Stock' : 'In Stock');
  }

  // --- CHARTS & EXPORT ---
  createStockChart(balances: any[]): void {
    this.destroyChart('stockChart');
    const ctx = document.getElementById('stockChart') as HTMLCanvasElement;
    if (!ctx || balances.length === 0) return;
    
    const topMaterials = balances.filter(b => b.current_balance > 0).sort((a, b) => b.current_balance - a.current_balance).slice(0, 15);
    this.stockChart = new Chart(ctx, {
      type: 'bar',
      data: {
        // Show Site Name in the chart label if multiple sites exist
        labels: topMaterials.map(b => `${b.material_name} (${b.site_name || 'Site'})`),
        datasets: [
          { label: 'Current Stock', data: topMaterials.map(b => b.current_balance), backgroundColor: 'rgba(63, 81, 181, 0.7)', borderColor: 'rgb(63, 81, 181)', borderWidth: 1 },
          { label: 'Opening Stock', data: topMaterials.map(b => b.opening_balance), backgroundColor: 'rgba(76, 175, 80, 0.7)', borderColor: 'rgb(76, 175, 80)', borderWidth: 1 }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  createMaterialChart(materialId: number): void {
    this.destroyChart('materialChart');
    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    if (!ctx || !this.selectedSiteId) return;
    this.stockService.getStockEntries({ site_id: this.selectedSiteId, material_id: materialId, limit: 30 }).subscribe({
      next: (entries) => {
        const labels = entries.map(e => new Date(e.entry_date).toLocaleDateString()).reverse();
        const quantities = entries.map(e => (e.entry_type === 'used' || e.entry_type === 'returned_supplier') ? -e.quantity : e.quantity).reverse();
        let runningBalance = 0;
        const balances = quantities.map(qty => { runningBalance += qty; return runningBalance; });
        this.materialChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [
              { label: 'Stock Balance', data: balances, borderColor: 'rgb(63, 81, 181)', backgroundColor: 'rgba(63, 81, 181, 0.1)', fill: true, tension: 0.4 },
              { label: 'Daily Movement', data: quantities, borderColor: 'rgb(255, 152, 0)', backgroundColor: 'rgba(255, 152, 0, 0.1)', type: 'bar' }
            ]
          },
          options: { responsive: true, maintainAspectRatio: false }
        });
        this.materialStockHistory = entries;
      }
    });
  }

  showMaterialDetails(material: Material): void {
    this.selectedMaterial = material;
    this.createMaterialChart(material.id);
    this.dialog.open(this.materialDetailsDialog, { width: '800px', maxHeight: '90vh' });
  }

  exportStockReport(): void {
    if (this.dataSource.data.length === 0) {
      this.toastr.warning('No data to export', 'Warning');
      return;
    }
    const headers = ['Project', 'Site', 'Material', 'Category', 'Current Balance', 'Opening Balance', 'Received', 'Used', 'Date', 'Status'];
    const projectName = this.projects.find(p => p.id === this.selectedProjectId)?.name || 'Unknown';
    
    const rows = this.dataSource.data.map((item: any) => {
      const rawDate = item.updated_at || item.created_at || item.last_updated;
      const dateStr = rawDate ? new Date(rawDate).toLocaleDateString() : 'N/A';
      return [
        projectName,
        item.site_name || 'N/A',
        item.material_name, 
        this.getCategoryName(item.material_id), 
        item.current_balance, 
        item.opening_balance, 
        item.total_received, 
        item.total_used, 
        dateStr,
        this.getStockStatusText(item)
      ];
    });
    const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(new Blob([csvContent], { type: 'text/csv' }));
    a.download = `stock-balance-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    this.toastr.success('Stock report exported', 'Success');
  }

  destroyChart(chartId: string): void {
    const canvas = document.getElementById(chartId) as HTMLCanvasElement;
    if (canvas) {
      const chart = Chart.getChart(canvas);
      if (chart) chart.destroy();
    }
  }

  ngOnDestroy(): void {
    this.destroyChart('stockChart');
    this.destroyChart('materialChart');
  }

  toggleViewMode(): void { this.viewMode = this.viewMode === 'table' ? 'cards' : 'table'; }
  
  // Fix refresh to use Project change instead of single site load
  refreshData(): void { 
    if (this.selectedProjectId) {
      this.onProjectChange(this.selectedProjectId);
    }
  }
}
