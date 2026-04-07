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
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';

@Component({
  selector: 'app-stock-balance',
  templateUrl: './stock-balance.component.html'
})
export class StockBalanceComponent implements OnInit, OnDestroy {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('materialDetails') materialDetailsDialog!: TemplateRef<any>;

  projects: Project[] = [];
  sites: Site[] = [];
  categories: any[] = [];
  materials: Material[] = [];
  filteredMaterials: Material[] = []; 
  
  allTimeBalances: any[] = []; 
  dateRangedBalances: any[] | null = null; 
  
  selectedMaterial: Material | null = null;
  filterForm: FormGroup;
  
  displayedColumns: string[] = ['material', 'category', 'site', 'current_balance', 'opening_balance', 'total_received', 'total_used', 'total_transfer_out', 'total_transfer_in', 'total_returned_supplier', 'updated_at', 'status'];
  dataSource = new MatTableDataSource<any>();
  
  materialChart: Chart | null = null;
  loading = false;
  selectedProjectId?: number;
  viewMode: 'table' | 'cards' = 'table';

  private prevStart: string = '';
  private prevEnd: string = '';

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
      category_id: [''], 
      material_id: [''],
      start_date: [''],
      end_date: [''],
      show_negative_only: [false]
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadCategories();
    this.loadMaterials();
    
    this.filterForm.valueChanges.subscribe(vals => {
      if (vals.start_date !== this.prevStart || vals.end_date !== this.prevEnd) {
        this.prevStart = vals.start_date;
        this.prevEnd = vals.end_date;
        this.fetchDateRangedData();
      } else {
        this.updateTable();
      }
    });
  }

  loadProjects(): void { this.projectService.getProjects().subscribe(p => this.projects = p); }
  loadCategories(): void { this.materialService.getCategories().subscribe(c => this.categories = c); }
  
  loadMaterials(): void { 
    this.materialService.getMaterials().subscribe(m => {
      this.materials = m;
      this.filteredMaterials = m;
    }); 
  }

  onProjectChange(projectId: any): void {
    const id = projectId ? Number(projectId) : 0;
    this.selectedProjectId = id;
    this.sites = [];
    this.allTimeBalances = [];
    this.dateRangedBalances = null;
    this.filterForm.patchValue({ site_id: '', start_date: '', end_date: '' }, { emitEvent: false });
    this.prevStart = ''; this.prevEnd = '';

    if (id) {
      this.loading = true;
      this.projectService.getProjectSites(id).subscribe(sites => {
        this.sites = sites.filter(s => s.status.toUpperCase() === 'ACTIVE' || s.status.toUpperCase() === 'IN_PROGRESS');
        if (this.sites.length === 0) { this.loading = false; return; }

        let loaded = 0;
        this.sites.forEach(site => {
          this.stockService.getSiteStockSummary(site.id).subscribe({
            next: (balances) => {
              const tagged = balances.map((b: any) => ({ ...b, site_name: site.name, site_id: site.id }));
              this.allTimeBalances = [...this.allTimeBalances, ...tagged];
              loaded++;
              if (loaded === this.sites.length) {
                this.loading = false;
                this.updateTable();
              }
            }
          });
        });
      });
    } else {
      this.updateTable();
    }
  }

  onSiteChange(siteId: any): void {}

  onCategoryChange(categoryId: any): void {
    this.filterForm.patchValue({ material_id: '' }, { emitEvent: false }); 
    if (categoryId) {
      this.filteredMaterials = this.materials.filter(m => m.category_id === Number(categoryId));
    } else {
      this.filteredMaterials = this.materials;
    }
    this.updateTable(); 
  }

  fetchDateRangedData(): void {
    const start = this.filterForm.value.start_date;
    const end = this.filterForm.value.end_date;

    if (!start && !end) {
      this.dateRangedBalances = null;
      this.updateTable();
      return;
    }

    this.loading = true;
    this.dateRangedBalances = [];
    let loaded = 0;
    this.sites.forEach(site => {
      this.stockService.getSiteStockSummary(site.id, start, end).subscribe({
        next: (balances) => {
          const tagged = balances.map((b: any) => ({ ...b, site_name: site.name, site_id: site.id }));
          this.dateRangedBalances = [...(this.dateRangedBalances || []), ...tagged];
          loaded++;
          if (loaded === this.sites.length) {
            this.loading = false;
            this.updateTable();
          }
        },
        error: () => {
          loaded++;
          if (loaded === this.sites.length) {
            this.loading = false;
            this.updateTable();
          }
        }
      });
    });
  }

  updateTable(): void {
    const filters = this.filterForm.value;
    let baseData = this.dateRangedBalances !== null ? this.dateRangedBalances : this.allTimeBalances;

    baseData = baseData.filter(b => {
      if (filters.site_id && b.site_id !== Number(filters.site_id)) return false;
      if (filters.material_id && b.material_id !== Number(filters.material_id)) return false;
      if (filters.show_negative_only && !b.has_negative_balance) return false;
      
      if (filters.category_id) {
        const mat = this.materials.find(m => m.id === b.material_id);
        if (!mat || mat.category_id !== Number(filters.category_id)) return false;
      }
      return true;
    });

    this.dataSource.data = baseData;
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
  }

  get cardData() {
    const filters = this.filterForm.value;
    return this.allTimeBalances.filter(b => {
      if (filters.site_id && b.site_id !== Number(filters.site_id)) return false;
      if (filters.material_id && b.material_id !== Number(filters.material_id)) return false;
      if (filters.show_negative_only && !b.has_negative_balance) return false;
      
      if (filters.category_id) {
        const mat = this.materials.find(m => m.id === b.material_id);
        if (!mat || mat.category_id !== Number(filters.category_id)) return false;
      }
      return true;
    });
  }

  getHealthyStockCount(data: any[]): number { return data.filter(b => !b.has_negative_balance && b.current_balance > 0).length; }
  getLowStockCount(data: any[]): number { return data.filter(b => b.current_balance < 10 && !b.has_negative_balance).length; }
  calculateStockValue(data: any[]): number {
    return data.reduce((total, balance) => {
      const material = this.materials.find(m => m.id === balance.material_id);
      return total + (balance.current_balance * (material?.standard_cost || 0));
    }, 0);
  }

  getFormattedDate(balance: any): string {
    const rawDate = balance.updated_at || balance.created_at || balance.last_updated || balance.entry_date || balance.report_date;
    if (!rawDate) return 'N/A';
    return new Date(rawDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  getCategoryName(categoryId: number | undefined): string {
    if (!categoryId) return 'Unknown';
    const category = this.categories?.find((c: any) => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }
  
  getMaterial(materialId: number | undefined): any { return this.materials?.find(m => m.id === materialId); }
  
  getStockStatus(balance: any): string {
    if (!balance) return 'secondary';
    return balance.has_negative_balance ? 'danger' : (balance.current_balance < 10 ? 'warning' : 'success');
  }
  getStockStatusText(balance: any): string {
    if (!balance) return 'Unknown';
    return balance.has_negative_balance ? 'Negative Stock' : (balance.current_balance < 10 ? 'Low Stock' : 'In Stock');
  }

  getCurrentStock(materialId: number | undefined): number {
    if (!materialId) return 0;
    const balance = this.allTimeBalances.find(b => b.material_id === materialId);
    return balance ? balance.current_balance : 0;
  }

  createMaterialChart(materialId: number): void {
    this.destroyChart('materialChart');
    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    const filters = this.filterForm.value;
    
    let siteIdToFetch = filters.site_id;
    if (!siteIdToFetch) {
        const mat = this.allTimeBalances.find(b => b.material_id === materialId);
        if (mat) siteIdToFetch = mat.site_id;
    }
    
    if (!ctx || !siteIdToFetch) return; 

    this.stockService.getStockEntries({ site_id: siteIdToFetch, material_id: materialId, limit: 30 }).subscribe({
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
    const headers = ['Project', 'Site', 'Material', 'Category', 'Current Balance', 'Opening Balance', 'Received', 'Used', 'Sent to Site', 'Received from Site', 'Returned (OUT to Supplier)', 'Date', 'Status'];
    const projectName = this.projects.find(p => p.id === this.selectedProjectId)?.name || 'Unknown';
    const rows = this.dataSource.data.map((item: any) => {
      const dateStr = this.getFormattedDate(item);
      return [ projectName, item.site_name || 'N/A', item.material_name, item.category, item.current_balance, item.opening_balance, item.total_received, item.total_used, item.total_transfer_out || 0, item.total_transfer_in || 0, item.total_returned_supplier || 0, dateStr, this.getStockStatusText(item) ];
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
    if (canvas) { const chart = Chart.getChart(canvas); if (chart) chart.destroy(); }
  }
  
  ngOnDestroy(): void { this.destroyChart('materialChart'); }
  toggleViewMode(): void { this.viewMode = this.viewMode === 'table' ? 'cards' : 'table'; }
  refreshData(): void { if (this.selectedProjectId) this.onProjectChange(this.selectedProjectId); }
}
