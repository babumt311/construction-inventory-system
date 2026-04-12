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

import { CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop';

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
  
  displayedColumns: string[] = [];
  dataSource = new MatTableDataSource<any>();
  
  materialChart: Chart | null = null;
  loading = false;
  selectedProjectId?: number;
  viewMode: 'table' | 'cards' = 'table';

  private prevBackendState = { start: '', end: '', supplier: '', entryType: '', project: '', asOfDate: '' };
  private prevProjectId: any = '';

  showExportModal = false;
  exportColumns: { key: string, label: string, selected: boolean }[] = [];
  includeExportTotals = true; 

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
        case 'project': return this.getProjectNameForSite(item.site_id).toLowerCase();
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
          const dateStr = item.updated_at || item.last_updated;
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
      as_of_date: [''], // NEW: Snapshot date for Card View
      supplier_name: [''],
      entry_type: [''],    
      show_negative_only: [false]
    });
  }

  ngOnInit(): void {
    this.loadCategories(); 
    this.loadMaterials();
    this.loadProjectsAndInitialData();

    this.filterForm.get('start_date')?.valueChanges.subscribe(startDate => {
      const endDate = this.filterForm.get('end_date')?.value;
      if (startDate && endDate && new Date(endDate) < new Date(startDate)) {
        this.filterForm.patchValue({ end_date: startDate }, { emitEvent: false });
      }
    });

    this.filterForm.valueChanges.pipe(debounceTime(400)).subscribe(vals => {
      const needsBackendFetch = 
        vals.start_date !== this.prevBackendState.start || 
        vals.end_date !== this.prevBackendState.end ||
        vals.supplier_name !== this.prevBackendState.supplier ||
        vals.entry_type !== this.prevBackendState.entryType ||
        vals.as_of_date !== this.prevBackendState.asOfDate ||
        vals.project_id !== this.prevBackendState.project;

      if (needsBackendFetch) {
        this.prevBackendState = { 
          start: vals.start_date, end: vals.end_date, supplier: vals.supplier_name, 
          entryType: vals.entry_type, asOfDate: vals.as_of_date, project: vals.project_id 
        };
        
        if (vals.project_id !== this.prevProjectId) {
          this.prevProjectId = vals.project_id;
          this.filterForm.patchValue({ site_id: '' }, { emitEvent: false });
          this.loadSitesAndFetchData(vals.project_id);
        } else {
          this.fetchDataFromBackend();
        }
      } else {
        this.updateTable();
      }
    });
  }

  drop(event: CdkDragDrop<string[]>) {
    const newCols = [...this.displayedColumns];
    moveItemInArray(newCols, event.previousIndex, event.currentIndex);
    
    const matIndex = newCols.indexOf('material');
    if (matIndex !== 0 && matIndex !== -1) {
      newCols.splice(matIndex, 1);
      newCols.unshift('material');
    }

    this.displayedColumns = newCols;
    localStorage.setItem('stockTableColumnOrder', JSON.stringify(this.displayedColumns));
  }

  getUniqueLotsData(dataArray: any[]): any[] {
    const lotMap = new Map<string, any>();
    const sorted = [...dataArray].sort((a, b) => {
        return new Date(a.last_updated || 0).getTime() - new Date(b.last_updated || 0).getTime();
    });
    for (const item of sorted) {
        lotMap.set(item.material_id.toString(), item); 
    }
    return Array.from(lotMap.values());
  }

  get mergedCardsData(): any[] {
    const merged = new Map<number, any>();
    
    for (const item of this.dataSource.data) {
      if (merged.has(item.material_id)) {
        const existing = merged.get(item.material_id);
        existing.total_received = Number(existing.total_received || 0) + Number(item.total_received || 0);
        existing.received_value = Number(existing.received_value || 0) + Number(item.received_value || 0);
        existing.total_used = Number(existing.total_used || 0) + Number(item.total_used || 0);
        existing.used_value = Number(existing.used_value || 0) + Number(item.used_value || 0);
        existing.total_transfer_out = Number(existing.total_transfer_out || 0) + Number(item.total_transfer_out || 0);
        existing.total_transfer_in = Number(existing.total_transfer_in || 0) + Number(item.total_transfer_in || 0);
        existing.total_returned_supplier = Number(existing.total_returned_supplier || 0) + Number(item.total_returned_supplier || 0);
      } else {
        merged.set(item.material_id, JSON.parse(JSON.stringify(item)));
      }
    }

    const latestLots = this.getUniqueLotsData(this.dataSource.data);
    const trueBalances = new Map<number, number>();
    for(const lot of latestLots) {
        trueBalances.set(lot.material_id, Number(lot.current_balance || 0));
    }

    const result = Array.from(merged.values());
    for(const card of result) {
        card.current_balance = trueBalances.get(card.material_id) || 0;
        card.supplier_name = '-';
        card.invoice_no = '-';
    }
    
    return result;
  }

  getProjectNameForSite(siteId: any): string {
    if (!siteId) return '-';
    const site = this.sites?.find(s => s.id === Number(siteId));
    if (!site || !site.project_id) return '-';
    
    const proj = this.projects?.find(p => p.id === site.project_id);
    return proj ? proj.name : '-';
  }

  loadProjectsAndInitialData(): void { 
    this.projectService.getProjects().subscribe(p => {
      this.projects = p;
      this.loadSitesAndFetchData(''); 
    }); 
  }

  loadCategories(): void { this.materialService.getCategories().subscribe(c => this.categories = c); }
  loadMaterials(): void { this.materialService.getMaterials().subscribe(m => { this.materials = m; this.filteredMaterials = m; }); }

  loadSitesAndFetchData(projectId: any): void {
    this.sites = [];
    if (!projectId) {
      if (this.projects.length === 0) { this.updateTable(); return; }
      this.loading = true;
      const requests = this.projects.map(p => this.projectService.getProjectSites(p.id));
      forkJoin(requests).subscribe(results => {
        this.sites = results.flat().filter(s => s.status.toUpperCase() === 'ACTIVE' || s.status.toUpperCase() === 'IN_PROGRESS');
        this.fetchDataFromBackend();
      });
    } else {
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

    const apiParams: any = {};

    // --- TIME TRAVEL ENGINE ---
    if (this.viewMode === 'cards') {
      if (filters.as_of_date) {
        apiParams.end_date = filters.as_of_date; // Fetch everything from dawn of time up to this date
      }
    } else {
      if (filters.start_date) apiParams.start_date = filters.start_date;
      if (filters.end_date) apiParams.end_date = filters.end_date;
      if (filters.supplier_name) apiParams.supplier_name = filters.supplier_name;
      if (filters.entry_type) apiParams.entry_type = filters.entry_type;
    }
    // --------------------------

    this.sites.forEach(site => {
      this.stockService.getSiteStockSummary(site.id, apiParams).subscribe({
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

    baseData = baseData.filter(b => {
      if (filters.site_id && b.site_id !== Number(filters.site_id)) return false;
      if (filters.material_id && b.material_id !== Number(filters.material_id)) return false;
      if (filters.show_negative_only && !b.has_negative_balance) return false;
      if (filters.category_id) {
        const mat = this.materials.find(m => m.id === b.material_id);
        if (!mat || mat.category_id !== Number(filters.category_id)) return false;
      }
      
      if (this.viewMode === 'table' && filters.supplier_name) {
        const searchStr = filters.supplier_name.toLowerCase().trim();
        const recordSupplier = (b.supplier_name || '').toLowerCase();
        if (!recordSupplier.includes(searchStr)) return false;
      }
      return true;
    });

    this.dataSource.data = baseData;

    const type = filters.entry_type;
    let cols = ['material', 'category', 'project', 'site'];

    if (type === 'received') cols.push('supplier_name', 'invoice_no', 'invoice_date');

    cols.push('current_balance', 'opening_balance');

    if (!type || type === '') {
      cols.push('total_received', 'received_cost', 'total_used', 'used_cost', 'total_transfer_out', 'total_transfer_in', 'total_returned_supplier');
    } else if (type === 'received') {
      cols.push('total_received', 'received_cost');
    } else if (type === 'used') {
      cols.push('total_used', 'used_cost');
    } else if (type === 'transfer') {
      cols.push('total_transfer_out', 'total_transfer_in');
    } else if (type === 'returned_supplier') {
      cols.push('total_returned_supplier');
    }
    
    cols.push('updated_at', 'status');

    const savedOrderJson = localStorage.getItem('stockTableColumnOrder');
    if (savedOrderJson) {
      try {
        const savedOrder = JSON.parse(savedOrderJson);
        cols.sort((a, b) => {
          if (a === 'material') return -1;
          if (b === 'material') return 1;
          let indexA = savedOrder.indexOf(a);
          let indexB = savedOrder.indexOf(b);
          if (indexA === -1) indexA = 999; 
          if (indexB === -1) indexB = 999;
          return indexA - indexB;
        });
      } catch (e) {}
    }

    this.displayedColumns = cols;

    if (this.viewMode === 'table') {
      setTimeout(() => {
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        if (this.paginator) { this.paginator.firstPage(); }
      });
    }
  }

  get totalReceivedQty(): number { return this.dataSource.data.reduce((sum, item) => sum + (Number(item.total_received) || 0), 0); }
  get totalReceivedCost(): number { return this.dataSource.data.reduce((sum, item) => sum + (Number(item.received_value) || 0), 0); }
  get totalUsedQty(): number { return this.dataSource.data.reduce((sum, item) => sum + (Number(item.total_used) || 0), 0); }
  get totalUsedCost(): number { return this.dataSource.data.reduce((sum, item) => sum + (Number(item.used_value) || 0), 0); }

  getFormattedDate(balance: any): string {
    const rawDate = balance.updated_at || balance.last_updated;
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
  
  getCurrentStock(materialId: number | undefined): number { 
    if (!materialId) return 0;
    const latestLots = this.getUniqueLotsData(this.allTimeBalances.filter(b => b.material_id === materialId));
    return latestLots.reduce((sum, lot) => sum + Number(lot.current_balance || 0), 0);
  }

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

    const type = this.filterForm.value.entry_type;
    this.exportColumns = [
      { key: 'project', label: 'Project', selected: true },
      { key: 'site_name', label: 'Site', selected: true },
      { key: 'material_name', label: 'Material', selected: true },
      { key: 'category', label: 'Category', selected: true }
    ];

    if (type === 'received') {
      this.exportColumns.push(
        { key: 'supplier_name', label: 'Supplier Name', selected: true },
        { key: 'invoice_no', label: 'Invoice No', selected: true },
        { key: 'invoice_date', label: 'Invoice Date', selected: true }
      );
    }

    this.exportColumns.push(
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
    );

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

    const data = this.dataSource.data.map(item => {
      return {
        ...item,
        project: this.getProjectNameForSite(item.site_id),
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
    titleCell.value = `ENTERPRISE INVENTORY: STOCK LEDGER REPORT`;
    titleCell.font = { name: 'Arial', size: 16, bold: true, color: { argb: 'FFFFFFFF' } };
    titleCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F3864' } }; 
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    worksheet.getRow(1).height = 35;

    worksheet.mergeCells(`A2:${String.fromCharCode(64 + selectedCols.length)}2`);
    const dateCell = worksheet.getCell('A2');
    dateCell.value = `Report generated on: ${new Date().toLocaleString()}`;
    dateCell.font = { name: 'Arial', size: 10, italic: true, color: { argb: 'FF595959' } };
    dateCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.addRow([]);

    const headerRow = worksheet.addRow(selectedCols.map(c => c.label));
    headerRow.height = 25;
    headerRow.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } }; 
      cell.font = { name: 'Arial', size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
      cell.border = { top: { style: 'thin' }, left: { style: 'thin' }, bottom: { style: 'medium' }, right: { style: 'thin' } };
    });

    data.forEach((item, index) => {
      const rowData = selectedCols.map(c => item[c.key as keyof typeof item]);
      const row = worksheet.addRow(rowData);
      row.height = 20;
      
      row.eachCell((cell) => {
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
        cell.border = { left: { style: 'thin', color: { argb: 'FFD9D9D9' } }, right: { style: 'thin', color: { argb: 'FFD9D9D9' } }, bottom: { style: 'thin', color: { argb: 'FFD9D9D9' } }};
        if (index % 2 !== 0) { cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF9F9F9' } }; }
      });
    });

    if (this.includeExportTotals && data.length > 0) {
      const summableColumns = [
        'current_balance', 'opening_balance', 'total_received', 'received_cost', 
        'total_used', 'used_cost', 'total_transfer_out', 'total_transfer_in', 'total_returned_supplier'
      ];

      const totalsData = selectedCols.map((col, index) => {
        if (index === 0) return 'GRAND TOTALS';
        if (summableColumns.includes(col.key)) {
          const sum = data.reduce((acc, item) => acc + (Number(item[col.key as keyof typeof item]) || 0), 0);
          return Number(sum.toFixed(2));
        }
        return '';
      });

      const totalRow = worksheet.addRow(totalsData);
      totalRow.height = 28;
      totalRow.eachCell((cell) => {
        cell.font = { name: 'Arial', size: 11, bold: true, color: { argb: 'FF000000' } };
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD9E1F2' } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
        cell.border = { top: { style: 'double', color: { argb: 'FF4472C4' } }, bottom: { style: 'medium', color: { argb: 'FF4472C4' } }, left: { style: 'thin', color: { argb: 'FFD9D9D9' } }, right: { style: 'thin', color: { argb: 'FFD9D9D9' } }};
      });
    }

    worksheet.columns.forEach(column => { column.width = 20; });

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const dateStr = new Date().toISOString().split('T')[0];
    saveAs(blob, `Stock_Ledger_Report_${dateStr}.xlsx`);

    this.toastr.success('Professional Report downloaded!');
    this.closeExportModal();
  }

  destroyChart(chartId: string): void {
    const canvas = document.getElementById(chartId) as HTMLCanvasElement;
    if (canvas) { const chart = Chart.getChart(canvas); if (chart) chart.destroy(); }
  }
  
  ngOnDestroy(): void { this.destroyChart('materialChart'); }
  
  toggleViewMode(): void { 
    this.viewMode = this.viewMode === 'table' ? 'cards' : 'table'; 
    
    if (this.viewMode === 'cards') {
      this.filterForm.patchValue({ start_date: '', end_date: '', entry_type: '', supplier_name: '' });
    } else {
      this.filterForm.patchValue({ as_of_date: '' });
    }

    this.updateTable(); 
    if (this.viewMode === 'table') { 
      setTimeout(() => { 
        this.dataSource.paginator = this.paginator; 
        this.dataSource.sort = this.sort; 
      }); 
    }
  }

  refreshData(): void { this.loadSitesAndFetchData(this.filterForm.value.project_id); }
}
