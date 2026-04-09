import { Component, OnInit, ViewChild, TemplateRef, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { Chart, registerables } from 'chart.js';
import { ToastrService } from 'ngx-toastr';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { forkJoin } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

import { StockService } from '../../services/stock.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';

import * as ExcelJS from 'exceljs';
import * as saveAs from 'file-saver';

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
  
  selectedMaterial: Material | null = null;
  selectedMaterialHistory: any[] = [];
  selectedSiteName: string = '';
  isLoadingHistory: boolean = false;
  
  filterForm: FormGroup;
  
  displayedColumns: string[] = ['material', 'category', 'site', 'supplier_name', 'invoice_no', 'invoice_date', 'current_balance', 'opening_balance', 'total_received', 'received_cost', 'total_used', 'used_cost', 'total_transfer_out', 'total_transfer_in', 'total_returned_supplier', 'updated_at', 'status'];
  dataSource = new MatTableDataSource<any>();
  
  materialChart: Chart | null = null;
  loading = false;
  selectedProjectId?: number;
  viewMode: 'table' | 'cards' = 'table';

  // State trackers to prevent unnecessary API calls
  private prevBackendState = { start: '', end: '', supplier: '', entryType: '', project: '' };
  private prevProjectId: any = '';

  showExportModal = false;
  exportColumns: { key: string, label: string, selected: boolean }[] = [];

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
        case 'received_cost': return Number(item.received_value || 0); 
        case 'total_used': return Number(item.total_used || 0);
        case 'used_cost': return Number(item.used_value || 0); 
        case 'total_transfer_out': return Number(item.total_transfer_out || 0);
        case 'total_transfer_in': return Number(item.total_transfer_in || 0);
        case 'total_returned_supplier': return Number(item.total_returned_supplier || 0);
        case 'supplier_name': return (item.supplier_name || '').toLowerCase();
        case 'invoice_no': return (item.invoice_no || '').toLowerCase();
        case 'invoice_date': return item.invoice_date ? new Date(item.invoice_date).getTime() : 0;
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
      supplier_name: [''], // NEW
      entry_type: [''],    // NEW
      show_negative_only: [false]
    });
  }

  ngOnInit(): void {
    this.loadCategories(); 
    this.loadMaterials();
    this.loadProjectsAndInitialData();

    // Debounce limits API calls while the user is actively typing a supplier name
    this.filterForm.valueChanges.pipe(debounceTime(400)).subscribe(vals => {
      const needsBackendFetch = 
        vals.start_date !== this.prevBackendState.start || 
        vals.end_date !== this.prevBackendState.end ||
        vals.supplier_name !== this.prevBackendState.supplier ||
        vals.entry_type !== this.prevBackendState.entryType ||
        vals.project_id !== this.prevBackendState.project;

      if (needsBackendFetch) {
        this.prevBackendState = { start: vals.start_date, end: vals.end_date, supplier: vals.supplier_name, entryType: vals.entry_type, project: vals.project_id };
        
        // If project changed, reload the site dropdown list
        if (vals.project_id !== this.prevProjectId) {
          this.prevProjectId = vals.project_id;
          this.filterForm.patchValue({ site_id: '' }, { emitEvent: false });
          this.loadSitesAndFetchData(vals.project_id);
        } else {
          this.fetchDataFromBackend();
        }
      } else {
        this.updateTable(); // Fast client-side filtering
      }
    });
  }

  loadProjectsAndInitialData(): void { 
    this.projectService.getProjects().subscribe(p => {
      this.projects = p;
      // Triggers initial load for "All Projects"
      this.loadSitesAndFetchData(''); 
    }); 
  }

  loadCategories(): void { this.materialService.getCategories().subscribe(c => this.categories = c); }
  loadMaterials(): void { this.materialService.getMaterials().subscribe(m => { this.materials = m; this.filteredMaterials = m; }); }

  loadSitesAndFetchData(projectId: any): void {
    this.sites = [];
    if (!projectId) {
      // ALL PROJECTS SELECTED: Fetch sites for every single project
      if (this.projects.length === 0) { this.updateTable(); return; }
      this.loading = true;
      const requests = this.projects.map(p => this.projectService.getProjectSites(p.id));
      forkJoin(requests).subscribe(results => {
        this.sites = results.flat().filter(s => s.status.toUpperCase() === 'ACTIVE' || s.status.toUpperCase() === 'IN_PROGRESS');
        this.fetchDataFromBackend();
      });
    } else {
      // SINGLE PROJECT SELECTED
      this.loading = true;
      this.projectService.getProjectSites(Number(projectId)).subscribe(sites => {
        this.sites = sites.filter(s => s.status.toUpperCase() === 'ACTIVE' || s.status.toUpperCase() === 'IN_PROGRESS');
        this.fetchDataFromBackend();
      });
    }
  }

  fetchDataFromBackend(): void {
    if (this.sites.length === 0) {
      this.allTimeBalances = [];
      this.updateTable();
      this.loading = false;
      return;
    }

    this.loading = true;
    this.allTimeBalances = [];
    let loaded = 0;
    const filters = this.filterForm.value;

    this.sites.forEach(site => {
      // NOTE: Ensure your stockService is updated to accept the two new parameters
      this.stockService.getSiteStockSummary(site.id, filters.start_date, filters.end_date, filters.supplier_name, filters.entry_type).subscribe({
        next: (balances: any) => {
          const tagged = balances.map((b: any) => ({ ...b, site_name: site.name, site_id: site.id }));
          this.allTimeBalances = [...this.allTimeBalances, ...tagged];
          loaded++;
          if (loaded === this.sites.length) { this.loading = false; this.updateTable(); }
        },
        error: () => { loaded++; if (loaded === this.sites.length) { this.loading = false; this.updateTable(); } }
      });
    });
  }

  onCategoryChange(categoryId: any): void {
    this.filterForm.patchValue({ material_id: '' }, { emitEvent: false }); 
    if (categoryId) { this.filteredMaterials = this.materials.filter(m => m.category_id === Number(categoryId)); } 
    else { this.filteredMaterials = this.materials; }
    this.updateTable(); 
  }

  updateTable(): void {
    const filters = this.filterForm.value;
    let baseData = this.allTimeBalances;

    // Apply Client-Side Filters
    baseData = baseData.filter(b => {
      // Standard filters
      if (filters.site_id && b.site_id !== Number(filters.site_id)) return false;
      if (filters.material_id && b.material_id !== Number(filters.material_id)) return false;
      if (filters.show_negative_only && !b.has_negative_balance) return false;
      if (filters.category_id) {
        const mat = this.materials.find(m => m.id === b.material_id);
        if (!mat || mat.category_id !== Number(filters.category_id)) return false;
      }
      
      // NEW: Instant Supplier Name Filter
      if (filters.supplier_name) {
        const searchStr = filters.supplier_name.toLowerCase().trim();
        const recordSupplier = (b.supplier_name || '').toLowerCase();
        if (!recordSupplier.includes(searchStr)) return false;
      }

      // NEW: Instant Transaction Type Filter
      // (Since this is a summary balance sheet, if you pick "Used", it hides materials that haven't been used)
      if (filters.entry_type) {
        if (filters.entry_type === 'received' && (!b.total_received || b.total_received <= 0)) return false;
        if (filters.entry_type === 'used' && (!b.total_used || b.total_used <= 0)) return false;
        if (filters.entry_type === 'transfer' && (!b.total_transfer_out || b.total_transfer_out <= 0) && (!b.total_transfer_in || b.total_transfer_in <= 0)) return false;
        if (filters.entry_type === 'returned_supplier' && (!b.total_returned_supplier || b.total_returned_supplier <= 0)) return false;
      }

      return true;
    });

    this.dataSource.data = baseData;
    if (this.viewMode === 'table') { 
      this.dataSource.paginator = this.paginator; 
      this.dataSource.sort = this.sort; 
    }
  }

  // --- Utility & Display Methods remain exactly the same as your code ---
  get cardData() { return this.dataSource.data; }
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
        if (entries.length > 0) { setTimeout(() => this.drawChart(entries), 100); }
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

  openExportModal(): void {
    if (this.dataSource.data.length === 0) {
      this.toastr.warning('No data to export', 'Warning');
      return;
    }

    this.exportColumns = [
      { key: 'project', label: 'Project', selected: true },
      { key: 'site_name', label: 'Site', selected: true },
      { key: 'material_name', label: 'Material', selected: true },
      { key: 'category', label: 'Category', selected: true },
      { key: 'supplier_name', label: 'Supplier Name', selected: true },
      { key: 'invoice_no', label: 'Invoice No', selected: true },
      { key: 'invoice_date', label: 'Invoice Date', selected: true },
      { key: 'current_balance', label: 'Current Balance', selected: true },
      { key: 'opening_balance', label: 'Opening Balance', selected: true },
      { key: 'total_received', label: 'Received Qty', selected: true },
      { key: 'received_value', label: 'Received Cost', selected: true },
      { key: 'total_used', label: 'Consumed Qty', selected: true },
      { key: 'used_value', label: 'Consumed Cost', selected: true },
      { key: 'total_transfer_out', label: 'Sent to Site', selected: true },
      { key: 'total_transfer_in', label: 'Received from Site', selected: true },
      { key: 'total_returned_supplier', label: 'Ret. (Supplier)', selected: true },
      { key: 'dateStr', label: 'Date', selected: true },
      { key: 'status', label: 'Status', selected: true }
    ];

    this.showExportModal = true;
  }

  closeExportModal(): void { this.showExportModal = false; }

  moveColumn(index: number, direction: number): void {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= this.exportColumns.length) return;
    const temp = this.exportColumns[index];
    this.exportColumns[index] = this.exportColumns[newIndex];
    this.exportColumns[newIndex] = temp;
  }

  async confirmAndExport(): Promise<void> {
    const selectedCols = this.exportColumns.filter(c => c.selected);
    
    if (selectedCols.length === 0) {
      this.toastr.warning('You must select at least one column to export.');
      return;
    }

    const projectName = this.projects.find(p => p.id === this.selectedProjectId)?.name || 'All Projects';
    const data = this.dataSource.data.map(item => {
      return {
        ...item,
        project: projectName,
        site_name: item.site_name || 'N/A',
        received_value: item.received_value || 0,
        used_value: item.used_value || 0,
        total_transfer_out: item.total_transfer_out || 0,
        total_transfer_in: item.total_transfer_in || 0,
        total_returned_supplier: item.total_returned_supplier || 0,
        dateStr: this.getFormattedDate(item),
        status: this.getStockStatusText(item)
      };
    });

    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Stock Balance');

    worksheet.mergeCells(`A1:${String.fromCharCode(64 + selectedCols.length)}1`);
    const titleCell = worksheet.getCell('A1');
    titleCell.value = `Enterprise System: Stock Balance Report`;
    titleCell.font = { name: 'Arial', size: 16, bold: true, color: { argb: 'FFFFFFFF' } };
    titleCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F3864' } }; 
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    worksheet.getRow(1).height = 30;

    const dateStr = new Date().toISOString().split('T')[0];
    worksheet.mergeCells(`A2:${String.fromCharCode(64 + selectedCols.length)}2`);
    const dateCell = worksheet.getCell('A2');
    dateCell.value = `Generated on: ${new Date().toLocaleString()}`;
    dateCell.font = { name: 'Arial', size: 10, italic: true };
    dateCell.alignment = { horizontal: 'right' };

    worksheet.addRow([]);

    const headerRow = worksheet.addRow(selectedCols.map(c => c.label));
    headerRow.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }; 
      cell.font = { name: 'Arial', size: 12, bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center' };
      cell.border = { top: { style: 'thin' }, left: { style: 'thin' }, bottom: { style: 'thin' }, right: { style: 'thin' } };
    });

    data.forEach((item, index) => {
      const rowData = selectedCols.map(c => item[c.key]);
      const row = worksheet.addRow(rowData);
      if (index % 2 === 0) {
        row.eachCell((cell) => { cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F2F2' } }; });
      }
    });

    worksheet.columns.forEach(column => { column.width = 22; });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, `stock-balance-${dateStr}.xlsx`);

    this.toastr.success('Enterprise Report generated successfully!');
    this.closeExportModal();
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
  refreshData(): void { this.loadSitesAndFetchData(this.filterForm.value.project_id); }
}
