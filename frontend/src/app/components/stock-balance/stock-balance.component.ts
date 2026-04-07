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
  selectedMaterialHistory: any[] = [];
  selectedSiteName: string = '';
  isLoadingHistory: boolean = false;
  
  filterForm: FormGroup;
  
  // ADDED received_cost AND used_cost TO COLUMNS
  displayedColumns: string[] = ['material', 'category', 'site', 'current_balance', 'opening_balance', 'total_received', 'received_cost', 'total_used', 'used_cost', 'total_transfer_out', 'total_transfer_in', 'total_returned_supplier', 'updated_at', 'status'];
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
    
    this.dataSource.sortingDataAccessor = (item, property) => {
      switch(property) {
        case 'material': return (item.material_name || '').toLowerCase();
        case 'category': return (item.category || '').toLowerCase();
        case 'site': return (item.site_name || '').toLowerCase();
        case 'current_balance': return Number(item.current_balance || 0);
        case 'opening_balance': return Number(item.opening_balance || 0);
        case 'total_received': return Number(item.total_received || 0);
        case 'received_cost': return this.getReceivedCost(item); // Sort by calculated cost
        case 'total_used': return Number(item.total_used || 0);
        case 'used_cost': return this.getUsedCost(item); // Sort by calculated cost
        case 'total_transfer_out': return Number(item.total_transfer_out || 0);
        case 'total_transfer_in': return Number(item.total_transfer_in || 0);
        case 'total_returned_supplier': return Number(item.total_returned_supplier || 0);
        case 'updated_at': 
          const dateStr = item.updated_at || item.created_at || item.last_updated || item.entry_date || item.report_date;
          return dateStr ? new Date(dateStr).getTime() : 0;
        default: return item[property];
      }
    };

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
    this.loadProjects(); this.loadCategories(); this.loadMaterials();
    this.filterForm.valueChanges.subscribe(vals => {
      if (vals.start_date !== this.prevStart || vals.end_date !== this.prevEnd) {
        this.prevStart = vals.start_date; this.prevEnd = vals.end_date;
        this.fetchDateRangedData();
      } else {
        this.updateTable();
      }
    });
  }

  loadProjects(): void { this.projectService.getProjects().subscribe(p => this.projects = p); }
  loadCategories(): void { this.materialService.getCategories().subscribe(c => this.categories = c); }
  loadMaterials(): void { this.materialService.getMaterials().subscribe(m => { this.materials = m; this.filteredMaterials = m; }); }

  onProjectChange(projectId: any): void {
    const id = projectId ? Number(projectId) : 0;
    this.selectedProjectId = id; this.sites = []; this.allTimeBalances = []; this.dateRangedBalances = null;
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
              if (loaded === this.sites.length) { this.loading = false; this.updateTable(); }
            }
          });
        });
      });
    } else { this.updateTable(); }
  }

  onSiteChange(siteId: any): void {}
  onCategoryChange(categoryId: any): void {
    this.filterForm.patchValue({ material_id: '' }, { emitEvent: false }); 
    if (categoryId) { this.filteredMaterials = this.materials.filter(m => m.category_id === Number(categoryId)); } 
    else { this.filteredMaterials = this.materials; }
    this.updateTable(); 
  }

  fetchDateRangedData(): void {
    const start = this.filterForm.value.start_date; const end = this.filterForm.value.end_date;
    if (!start && !end) { this.dateRangedBalances = null; this.updateTable(); return; }

    this.loading = true; this.dateRangedBalances = [];
    let loaded = 0;
    this.sites.forEach(site => {
      this.stockService.getSiteStockSummary(site.id, start, end).subscribe({
        next: (balances) => {
          const tagged = balances.map((b: any) => ({ ...b, site_name: site.name, site_id: site.id }));
          this.dateRangedBalances = [...(this.dateRangedBalances || []), ...tagged];
          loaded++;
          if (loaded === this.sites.length) { this.loading = false; this.updateTable(); }
        },
        error: () => { loaded++; if (loaded === this.sites.length) { this.loading = false; this.updateTable(); } }
      });
    });
  }

  updateTable(): void {
    const filters = this.filterForm.value;
    let baseData = (this.viewMode === 'table' && this.dateRangedBalances !== null) ? this.dateRangedBalances : this.allTimeBalances;

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
    if (this.viewMode === 'table') { this.dataSource.paginator = this.paginator; this.dataSource.sort = this.sort; }
  }

  get cardData() { return this.dataSource.data; }
  getHealthyStockCount(data: any[]): number { return data.filter(b => !b.has_negative_balance && b.current_balance > 0).length; }
  getLowStockCount(data: any[]): number { return data.filter(b => b.current_balance < 10 && !b.has_negative_balance).length; }
  calculateStockValue(data: any[]): number {
    return data.reduce((total, balance) => {
      const material = this.materials.find(m => m.id === balance.material_id);
      return total + (balance.current_balance * (material?.standard_cost || 0));
    }, 0);
  }

  // --- NEW COST CALCULATION HELPERS ---
  getReceivedCost(balance: any): number {
    const material = this.getMaterial(balance.material_id);
    const standardCost = material ? Number(material.standard_cost) : 0;
    return Number(balance.total_received || 0) * standardCost;
  }

  getUsedCost(balance: any): number {
    const material = this.getMaterial(balance.material_id);
    const standardCost = material ? Number(material.standard_cost) : 0;
    return Number(balance.total_used || 0) * standardCost;
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
  getStockStatus(balance: any): string { return balance?.has_negative_balance ? 'danger' : (balance?.current_balance < 10 ? 'warning' : 'success'); }
  getStockStatusText(balance: any): string { return balance?.has_negative_balance ? 'Negative Stock' : (balance?.current_balance < 10 ? 'Low Stock' : 'In Stock'); }
  getCurrentStock(materialId: number | undefined): number { const balance = this.allTimeBalances.find(b => b.material_id === materialId); return balance ? balance.current_balance : 0; }

  showMaterialDetails(balanceRow: any): void {
    const material = this.getMaterial(balanceRow.material_id);
    if (!material) return;
    
    this.selectedMaterial = material;
    this.selectedSiteName = balanceRow.site_name || 'Selected Site';
    this.selectedMaterialHistory = [];
    this.isLoadingHistory = true;

    const dialogRef = this.dialog.open(this.materialDetailsDialog, { width: '900px', maxHeight: '90vh' });

    dialogRef.afterOpened().subscribe(() => {
      this.fetchHistoryAndDrawChart(balanceRow.material_id, balanceRow.site_id);
    });
  }

  fetchHistoryAndDrawChart(materialId: number, siteId: number): void {
    this.stockService.getStockEntries({ site_id: siteId, material_id: materialId, limit: 15 }).subscribe({
      next: (entries) => {
        this.selectedMaterialHistory = entries;
        this.isLoadingHistory = false;
        if (entries.length > 0) {
          setTimeout(() => this.drawChart(entries), 100);
        }
      },
      error: () => { this.isLoadingHistory = false; }
    });
  }

  drawChart(entries: any[]): void {
    this.destroyChart('materialChart');
    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    if (!ctx) return;

    const sortedEntries = [...entries].reverse();
    const labels = sortedEntries.map(e => new Date(e.entry_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    
    const inData = sortedEntries.map(e => this.isEntryIn(e) ? Number(e.quantity) : 0);
    const outData = sortedEntries.map(e => !this.isEntryIn(e) ? Number(e.quantity) : 0);

    this.materialChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Stock IN', data: inData, backgroundColor: 'rgba(76, 175, 80, 0.7)' },
          { label: 'Stock OUT', data: outData, backgroundColor: 'rgba(244, 67, 54, 0.7)' }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
    });
  }

  isEntryIn(entry: any): boolean {
    const isOut = ['used', 'returned_supplier'].includes(entry.entry_type) || (entry.remarks && entry.remarks.includes('Transfer OUT'));
    return !isOut;
  }

  formatEntryType(type: string, remarks?: string): string {
    if (type === 'used' && remarks?.includes('Transfer OUT')) return 'SENT TO SITE';
    if (type === 'returned_received' && remarks?.includes('Transfer IN')) return 'RECEIVED FROM SITE';
    if (type === 'returned_received') return 'RETURNED FROM SITE';
    return (type || '').replace('_', ' ').toUpperCase();
  }

  getEntryBadge(type: string, remarks?: string): string {
    if (type === 'used' && remarks?.includes('Transfer OUT')) return 'bg-info text-dark border border-info';
    if (type === 'returned_received' && remarks?.includes('Transfer IN')) return 'bg-primary text-white';
    switch (type) {
      case 'received': return 'bg-success';
      case 'used': return 'bg-danger';
      case 'returned_supplier': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  }

  exportStockReport(): void {
    if (this.dataSource.data.length === 0) { this.toastr.warning('No data to export', 'Warning'); return; }
    
    // UPDATED HEADERS TO INCLUDE COSTS
    const headers = ['Project', 'Site', 'Material', 'Category', 'Current Balance', 'Opening Balance', 'Received Qty', 'Received Cost', 'Used Qty', 'Used Cost', 'Sent to Site', 'Received from Site', 'Returned (OUT to Supplier)', 'Date', 'Status'];
    const projectName = this.projects.find(p => p.id === this.selectedProjectId)?.name || 'Unknown';
    
    const rows = this.dataSource.data.map((item: any) => {
      const dateStr = this.getFormattedDate(item);
      return [ 
        projectName, item.site_name || 'N/A', item.material_name, item.category, 
        item.current_balance, item.opening_balance, 
        item.total_received, this.getReceivedCost(item), // Added Recv Cost
        item.total_used, this.getUsedCost(item),         // Added Used Cost
        item.total_transfer_out || 0, item.total_transfer_in || 0, 
        item.total_returned_supplier || 0, dateStr, this.getStockStatusText(item) 
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
    if (canvas) { const chart = Chart.getChart(canvas); if (chart) chart.destroy(); }
  }
  
  ngOnDestroy(): void { this.destroyChart('materialChart'); }
  toggleViewMode(): void { 
    this.viewMode = this.viewMode === 'table' ? 'cards' : 'table'; 
    this.updateTable(); 
    if (this.viewMode === 'table') { setTimeout(() => { this.dataSource.paginator = this.paginator; this.dataSource.sort = this.sort; }); }
  }
  refreshData(): void { if (this.selectedProjectId) this.onProjectChange(this.selectedProjectId); }
}
