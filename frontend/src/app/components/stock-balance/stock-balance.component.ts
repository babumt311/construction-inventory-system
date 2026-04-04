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

  // Data
  projects: Project[] = [];
  sites: Site[] = [];
  materials: Material[] = [];
  categories: any[] = [];
  stockBalances: StockBalance[] = [];
  selectedMaterial: Material | null = null;
  materialStockHistory: any[] = [];
  
  // Forms
  filterForm: FormGroup;
  
  // Table - NEW: Added 'updated_at' to the displayed columns array
  displayedColumns: string[] = ['material', 'category', 'current_balance', 'opening_balance', 'total_received', 'total_used', 'updated_at', 'status'];
  dataSource = new MatTableDataSource<StockBalance>();
  
  // Charts & UI
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
    
    // NEW: Added start_date and end_date to the form
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
    this.loadStockBalances();
    
    this.filterForm.valueChanges.subscribe(() => this.applyFilters());
  }

  // --- DATA LOADING ---
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

  loadStockBalances(): void {
    this.loading = true;
    if (this.selectedSiteId) {
      this.loadSiteStockSummary(this.selectedSiteId);
    } else {
      this.loading = false;
    }
  }

  loadSiteStockSummary(siteId: number): void {
    this.stockService.getSiteStockSummary(siteId).subscribe({
      next: (balances) => {
        this.stockBalances = balances;
        this.dataSource.data = balances;
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        this.createStockChart(balances);
        this.loading = false;
      },
      error: () => {
        this.toastr.error('Failed to load stock balances');
        this.loading = false;
      }
    });
  }

  // --- DROPDOWN LOGIC ---
  onProjectChange(projectId: any): void {
    const id = projectId ? Number(projectId) : 0;
    this.selectedProjectId = id;
    this.sites = [];
    this.selectedSiteId = undefined;
    this.filterForm.patchValue({ site_id: '' });
    
    if (id) {
      this.projectService.getProjectSites(id).subscribe(sites => {
        this.sites = sites.filter(site => site.status === 'ACTIVE' || site.status === 'active' || site.status === 'IN_PROGRESS');
      });
    }
  }

  onSiteChange(siteId: any): void {
    const id = siteId ? Number(siteId) : 0;
    this.selectedSiteId = id;
    if (id) this.loadStockBalances();
  }

  // NEW: Updated to handle Date Range filtering
  applyFilters(): void {
    const filters = this.filterForm.value;
    let filteredData = this.stockBalances;
    
    if (filters.material_id) {
      filteredData = filteredData.filter(b => Number(b.material_id) === Number(filters.material_id));
    }
    
    // Apply Start Date Filter
    if (filters.start_date) {
      const start = new Date(filters.start_date).getTime();
      filteredData = filteredData.filter(b => {
        const itemDate = new Date(b.updated_at || b.created_at).getTime();
        return itemDate >= start;
      });
    }

    // Apply End Date Filter
    if (filters.end_date) {
      const end = new Date(filters.end_date).getTime() + (24 * 60 * 60 * 1000) - 1; // End of the selected day
      filteredData = filteredData.filter(b => {
        const itemDate = new Date(b.updated_at || b.created_at).getTime();
        return itemDate <= end;
      });
    }
    
    if (filters.show_negative_only) {
      filteredData = filteredData.filter(b => b.has_negative_balance);
    }
    
    this.dataSource.data = filteredData;
  }

  // --- HTML Helper Methods ---
  getHealthyStockCount(): number { return this.stockBalances.filter(b => !b.has_negative_balance && b.current_balance > 0).length; }
  getLowStockCount(): number { return this.stockBalances.filter(b => b.current_balance < 10 && !b.has_negative_balance).length; }
  getCategoryName(categoryId: number | undefined): string {
    const category = this.categories?.find((c: any) => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }
  getMaterial(materialId: number | undefined): any { return this.materials?.find(m => m.id === materialId); }
  getCurrentStock(materialId: number | undefined): number {
    const balance = this.stockBalances?.find(b => b.material_id === materialId);
    return balance ? balance.current_balance : 0;
  }
  getBalance(materialId: number | undefined): any { return this.stockBalances?.find(b => b.material_id === materialId); }
  calculateStockValue(): number {
    return this.stockBalances.reduce((total, balance) => {
      const material = this.materials.find(m => m.id === balance.material_id);
      return total + (balance.current_balance * (material?.standard_cost || 0));
    }, 0);
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
  createStockChart(balances: StockBalance[]): void {
    this.destroyChart('stockChart');
    const ctx = document.getElementById('stockChart') as HTMLCanvasElement;
    if (!ctx) return;
    const topMaterials = balances.filter(b => b.current_balance > 0).sort((a, b) => b.current_balance - a.current_balance).slice(0, 10);
    this.stockChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: topMaterials.map(b => b.material_name),
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
    // NEW: Added 'Last Updated' to the exported CSV
    const headers = ['Material', 'Category', 'Current Balance', 'Opening Balance', 'Received', 'Used', 'Last Updated', 'Status'];
    const rows = this.dataSource.data.map(item => [
      item.material_name, 
      this.getCategoryName(item.material_id), 
      item.current_balance, 
      item.opening_balance, 
      item.total_received, 
      item.total_used, 
      item.updated_at ? new Date(item.updated_at).toLocaleDateString() : 'N/A',
      this.getStockStatusText(item)
    ]);
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
  refreshData(): void { this.loadStockBalances(); }
}
