import { Component, OnInit, ViewChild, TemplateRef } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { Chart, registerables } from 'chart.js';
import { ToastrService } from 'ngx-toastr';

// Angular Material Imports (Consolidated)
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';

// Services
import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';

// Models
import { StockBalance } from '../../models/stock.model';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';

@Component({
  selector: 'app-stock-balance',
  templateUrl: './stock-balance.component.html',
  styleUrls: ['./stock-balance.component.scss']
})
export class StockBalanceComponent implements OnInit {
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
  
  // Table
  displayedColumns: string[] = ['material', 'category', 'current_balance', 'opening_balance', 'total_received', 'total_used', 'status'];
  dataSource = new MatTableDataSource<StockBalance>();
  
  // Charts
  stockChart: Chart | null = null;
  materialChart: Chart | null = null;
  
  // UI State
  loading = false;
  selectedProjectId?: number;
  selectedSiteId?: number;
  viewMode: 'table' | 'cards' = 'table';
  showNegativeOnly = false;

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
      show_negative_only: [false]
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadMaterials();
    this.loadCategories();
    this.loadStockBalances();
    
    // Subscribe to filter changes
    this.filterForm.valueChanges.subscribe(() => {
      this.applyFilters();
    });
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

  loadCategories(): void {
    this.materialService.getCategories().subscribe({
      next: (categories) => {
        this.categories = categories;
      },
      error: (error) => {
        console.warn('Could not load categories', error);
      }
    });
  }

  loadStockBalances(): void {
    this.loading = true;
    
    if (this.selectedSiteId) {
      this.loadSiteStockSummary(this.selectedSiteId);
    } else {
      this.loadAllStockBalances();
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
      error: (error) => {
        this.toastr.error('Failed to load stock balances', 'Error');
        this.loading = false;
      }
    });
  }

  loadAllStockBalances(): void {
    this.loading = false;
    this.toastr.info('Please select a site to view stock balances', 'Info');
  }

  onProjectChange(projectId: any): void {
    const id = projectId ? Number(projectId) : 0;
    this.selectedProjectId = id;
    this.sites = [];
    this.selectedSiteId = undefined;
    this.filterForm.patchValue({ site_id: '' });
    
    if (id) {
      this.projectService.getProjectSites(id).subscribe({
        next: (sites) => {
          this.sites = sites.filter(site => site.status === 'active');
        },
        error: (error) => {
          this.toastr.error('Failed to load sites', 'Error');
        }
      });
    }
  }

  onSiteChange(siteId: any): void {
    const id = siteId ? Number(siteId) : 0;
    this.selectedSiteId = id;
    if (id) {
      this.loadStockBalances();
    }
  }

  applyFilters(): void {
    const filters = this.filterForm.value;
    let filteredData = this.stockBalances;
    
    if (filters.material_id) {
      filteredData = filteredData.filter(balance => 
        balance.material_id === filters.material_id
      );
    }
    
    if (filters.show_negative_only) {
      filteredData = filteredData.filter(balance => 
        balance.has_negative_balance
      );
    }
    
    this.dataSource.data = filteredData;
  }

  // --- HTML Helper Methods ---

  getHealthyStockCount(): number {
    return this.stockBalances.filter(b => !b.has_negative_balance && b.current_balance > 0).length;
  }

  getLowStockCount(): number {
    return this.stockBalances.filter(b => b.current_balance < 10 && !b.has_negative_balance).length;
  }

  getCategoryName(categoryId: number | undefined): string {
    if (!categoryId) return 'Unknown';
    const category = this.categories?.find((c: any) => c.id === categoryId);
    return category ? category.name : 'Unknown';
  }

  getMaterial(materialId: number | undefined): any {
    if (!materialId) return null;
    return this.materials?.find(m => m.id === materialId);
  }

  getCurrentStock(materialId: number | undefined): number {
    if (!materialId) return 0;
    const balance = this.stockBalances?.find(b => b.material_id === materialId);
    return balance ? balance.current_balance : 0;
  }

  getBalance(materialId: number | undefined): any {
    if (!materialId) return null;
    return this.stockBalances?.find(b => b.material_id === materialId);
  }
  
  getMaterialName(materialId: number): string {
    const material = this.materials.find(m => m.id === materialId);
    return material ? material.name : 'Unknown';
  }

  calculateStockValue(): number {
    return this.stockBalances.reduce((total, balance) => {
      const material = this.materials.find(m => m.id === balance.material_id);
      const unitCost = material?.standard_cost || 0;
      return total + (balance.current_balance * unitCost);
    }, 0);
  }

  getStockStatus(balance: any): string {
    if (!balance) return 'secondary';
    if (balance.has_negative_balance) {
      return 'danger';
    } else if (balance.current_balance < 10) {
      return 'warning';
    } else {
      return 'success';
    }
  }

  getStockStatusText(balance: any): string {
    if (!balance) return 'Unknown';
    if (balance.has_negative_balance) {
      return 'Negative Stock';
    } else if (balance.current_balance < 10) {
      return 'Low Stock';
    } else {
      return 'In Stock';
    }
  }

  // --- Charts & Export ---

  createStockChart(balances: StockBalance[]): void {
    this.destroyChart('stockChart');
    
    const ctx = document.getElementById('stockChart') as HTMLCanvasElement;
    if (!ctx) return;
    
    const topMaterials = balances
      .filter(b => b.current_balance > 0)
      .sort((a, b) => b.current_balance - a.current_balance)
      .slice(0, 10);
    
    this.stockChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: topMaterials.map(b => b.material_name),
        datasets: [
          {
            label: 'Current Stock',
            data: topMaterials.map(b => b.current_balance),
            backgroundColor: 'rgba(63, 81, 181, 0.7)',
            borderColor: 'rgb(63, 81, 181)',
            borderWidth: 1
          },
          {
            label: 'Opening Stock',
            data: topMaterials.map(b => b.opening_balance),
            backgroundColor: 'rgba(76, 175, 80, 0.7)',
            borderColor: 'rgb(76, 175, 80)',
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: 'Top Materials by Stock Balance' },
          legend: { position: 'top' }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Quantity' } },
          x: { ticks: { maxRotation: 45, minRotation: 45 } }
        }
      }
    });
  }

  createMaterialChart(materialId: number): void {
    this.destroyChart('materialChart');
    
    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    if (!ctx) return;
    
    if (this.selectedSiteId) {
      this.stockService.getStockEntries({
        site_id: this.selectedSiteId,
        material_id: materialId,
        limit: 30,
        sort_by: 'entry_date',
        sort_order: 'desc'
      }).subscribe({
        next: (entries) => {
          const labels = entries.map(e => new Date(e.entry_date).toLocaleDateString()).reverse();
          const quantities = entries.map(e => {
            let qty = e.quantity;
            if (e.entry_type === 'used' || e.entry_type === 'returned_supplier') {
              qty = -qty;
            }
            return qty;
          }).reverse();
          
          let runningBalance = 0;
          const balances = quantities.map(qty => {
            runningBalance += qty;
            return runningBalance;
          });
          
          this.materialChart = new Chart(ctx, {
            type: 'line',
            data: {
              labels: labels,
              datasets: [
                {
                  label: 'Stock Balance',
                  data: balances,
                  borderColor: 'rgb(63, 81, 181)',
                  backgroundColor: 'rgba(63, 81, 181, 0.1)',
                  fill: true,
                  tension: 0.4
                },
                {
                  label: 'Daily Movement',
                  data: quantities,
                  borderColor: 'rgb(255, 152, 0)',
                  backgroundColor: 'rgba(255, 152, 0, 0.1)',
                  type: 'bar'
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { title: { display: true, text: 'Material Stock History (Last 30 Days)' } },
              scales: { y: { title: { display: true, text: 'Quantity' } } }
            }
          });
          this.materialStockHistory = entries;
        }
      });
    }
  }

  showMaterialDetails(material: Material): void {
    this.selectedMaterial = material;
    this.createMaterialChart(material.id);
    this.dialog.open(this.materialDetailsDialog, { width: '800px', maxHeight: '90vh' });
  }

  exportStockReport(): void {
    const data = this.dataSource.data;
    if (data.length === 0) {
      this.toastr.warning('No data to export', 'Warning');
      return;
    }

    const headers = ['Material', 'Category', 'Current Balance', 'Opening Balance', 'Received', 'Used', 'Status'];
    const rows = data.map(item => [
      item.material_name,
      this.getCategoryName(item.material_id),
      item.current_balance,
      item.opening_balance,
      item.total_received,
      item.total_used,
      this.getStockStatusText(item)
    ]);

    const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stock-balance-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    this.toastr.success('Stock report exported', 'Success');
  }

  destroyChart(chartId: string): void {
    const canvas = document.getElementById(chartId) as HTMLCanvasElement;
    if (canvas) {
      const chart = Chart.getChart(canvas);
      if (chart) { chart.destroy(); }
    }
  }

  ngOnDestroy(): void {
    this.destroyChart('stockChart');
    this.destroyChart('materialChart');
  }

  toggleViewMode(): void {
    this.viewMode = this.viewMode === 'table' ? 'cards' : 'table';
  }

  refreshData(): void {
    this.loadStockBalances();
    this.toastr.info('Stock data refreshed', 'Success');
  }
}
