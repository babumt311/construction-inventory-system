import { Component, OnInit, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { Chart, registerables } from 'chart.js';
import { ReportService } from '../../services/report.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { ReportFilter, MaterialWiseReport, SupplierWiseReport, PeriodReport } from '../../models/report.model';
import { Project, Site } from '../../models/project.model';
import { Category } from '../../models/material.model';
import { ToastrService } from 'ngx-toastr';

// NEW ENTERPRISE EXCEL IMPORTS
import * as ExcelJS from 'exceljs';
import * as saveAs from 'file-saver';

@Component({
  selector: 'app-reports',
  templateUrl: './reports.component.html',
  styleUrls: ['./reports.component.scss']
})
export class ReportsComponent implements OnInit {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  // Data
  projects: Project[] = [];
  sites: Site[] = [];
  categories: Category[] = [];
  
  // Forms
  reportForm: FormGroup;
  currentReportType: 'material' | 'supplier' | 'period' | 'custom' = 'material';
  
  // Report Data
  materialReportData: MaterialWiseReport[] = [];
  supplierReportData: SupplierWiseReport[] = [];
  periodReportData: PeriodReport[] = [];
  customReportData: any[] = [];
  
  // Tables
  materialColumns: string[] = ['category', 'material', 'quantity', 'unit', 'unit_cost', 'total_cost'];
  supplierColumns: string[] = ['supplier_name', 'material', 'quantity', 'unit', 'total_cost', 'invoice_no', 'purchase_date'];
  periodColumns: string[] = ['material', 'unit', 'opening_stock', 'received', 'total_issued', 'returned', 'closing_stock'];
  
  materialDataSource = new MatTableDataSource<MaterialWiseReport>();
  supplierDataSource = new MatTableDataSource<SupplierWiseReport>();
  periodDataSource = new MatTableDataSource<PeriodReport>();
  
  // Charts
  materialChart: any;
  supplierChart: any;
  
  // UI State
  loading = false;
  showChart = true;

  // ==========================================
  // NEW: EXPORT MODAL STATE
  // ==========================================
  showExportModal = false;
  exportColumns: { key: string, label: string, selected: boolean }[] = [];

  constructor(
    private fb: FormBuilder,
    private reportService: ReportService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    private toastr: ToastrService
  ) {
    Chart.register(...registerables);
    
    this.reportForm = this.fb.group({
      report_type: ['material'],
      start_date: [''],
      end_date: [''],
      project_id: [''],
      site_id: [''],
      material_id: [''],
      supplier_name: [''],
      category_id: ['']
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadCategories();
    this.setDefaultDates();
    this.onReportTypeChange('material');
  }

  setDefaultDates(): void {
    const today = new Date();
    const lastMonth = new Date();
    lastMonth.setMonth(lastMonth.getMonth() - 1);
    
    this.reportForm.patchValue({
      start_date: lastMonth,
      end_date: today
    });
  }

  loadProjects(): void {
    this.projectService.getProjects().subscribe({
      next: (projects) => {
        this.projects = projects;
      }
    });
  }

  loadCategories(): void {
    this.materialService.getCategories().subscribe({
      next: (categories) => {
        this.categories = categories;
      }
    });
  }

  onReportTypeChange(type: 'material' | 'supplier' | 'period' | 'custom'): void {
    this.currentReportType = type;
    this.reportForm.patchValue({ report_type: type });
    this.clearReportData();
  }

  onProjectChange(projectId: number): void {
    this.sites = [];
    this.reportForm.patchValue({ site_id: '' });
    
    if (projectId) {
      this.projectService.getProjectSites(projectId).subscribe({
        next: (sites) => {
          this.sites = sites;
        }
      });
    }
  }

  generateReport(): void {
    if (this.reportForm.invalid) {
      return;
    }

    const filters: ReportFilter = this.reportForm.value;
    this.loading = true;

    switch (this.currentReportType) {
      case 'material':
        this.generateMaterialReport(filters);
        break;
      case 'supplier':
        this.generateSupplierReport(filters);
        break;
      case 'period':
        this.generatePeriodReport(filters);
        break;
      case 'custom':
        this.generateCustomReport(filters);
        break;
    }
  }

  generateMaterialReport(filters: ReportFilter): void {
    this.reportService.getMaterialWiseReport(filters).subscribe({
      next: (data) => {
        this.materialReportData = data;
        this.materialDataSource.data = data;
        this.materialDataSource.paginator = this.paginator;
        this.materialDataSource.sort = this.sort;
        this.createMaterialChart(data);
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to generate material report');
        this.loading = false;
      }
    });
  }

  generateSupplierReport(filters: ReportFilter): void {
    this.reportService.getSupplierWiseReport(filters).subscribe({
      next: (data) => {
        this.supplierReportData = data;
        this.supplierDataSource.data = data;
        this.supplierDataSource.paginator = this.paginator;
        this.supplierDataSource.sort = this.sort;
        this.createSupplierChart(data);
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to generate supplier report');
        this.loading = false;
      }
    });
  }

  generatePeriodReport(filters: ReportFilter): void {
    if (!filters.site_id) {
      this.toastr.error('Please select a site for period report');
      this.loading = false;
      return;
    }

    this.reportService.getPeriodReport(
      filters.site_id,
      filters.start_date!,
      filters.end_date!,
      filters.material_id
    ).subscribe({
      next: (data) => {
        this.periodReportData = data;
        this.periodDataSource.data = data;
        this.periodDataSource.paginator = this.paginator;
        this.periodDataSource.sort = this.sort;
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to generate period report');
        this.loading = false;
      }
    });
  }

  generateCustomReport(filters: ReportFilter): void {
    this.reportService.getCustomReport(filters).subscribe({
      next: (data) => {
        this.customReportData = data;
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to generate custom report');
        this.loading = false;
      }
    });
  }

  createMaterialChart(data: MaterialWiseReport[]): void {
    if (this.materialChart) {
      this.materialChart.destroy();
    }

    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    const top10 = data.slice(0, 10);
    
    this.materialChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top10.map(item => item.material),
        datasets: [{
          label: 'Total Cost (₹)',
          data: top10.map(item => item.total_cost),
          backgroundColor: '#4CAF50',
          borderColor: '#388E3C',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'Top 10 Materials by Cost'
          },
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Cost (₹)'
            }
          }
        }
      }
    });
  }

  createSupplierChart(data: SupplierWiseReport[]): void {
    if (this.supplierChart) {
      this.supplierChart.destroy();
    }

    const ctx = document.getElementById('supplierChart') as HTMLCanvasElement;
    
    const supplierMap = new Map<string, number>();
    data.forEach(item => {
      const current = supplierMap.get(item.supplier_name) || 0;
      supplierMap.set(item.supplier_name, current + item.total_cost);
    });

    const suppliers = Array.from(supplierMap.keys());
    const costs = Array.from(supplierMap.values());

    this.supplierChart = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: suppliers,
        datasets: [{
          data: costs,
          backgroundColor: [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
            '#9966FF', '#FF9F40', '#8AC926', '#1982C4',
            '#6A4C93', '#F15BB5'
          ]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'Supplier Cost Distribution'
          },
          legend: {
            position: 'right'
          }
        }
      }
    });
  }

  clearReportData(): void {
    this.materialReportData = [];
    this.supplierReportData = [];
    this.periodReportData = [];
    this.customReportData = [];
    
    this.materialDataSource.data = [];
    this.supplierDataSource.data = [];
    this.periodDataSource.data = [];
    
    if (this.materialChart) {
      this.materialChart.destroy();
      this.materialChart = null;
    }
    
    if (this.supplierChart) {
      this.supplierChart.destroy();
      this.supplierChart = null;
    }
  }

  // ==========================================
  // NEW: MODAL AND CUSTOM EXPORT LOGIC
  // ==========================================

  formatLabel(key: string): string {
    return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  }

  openExportModal(): void {
    let rawKeys: string[] = [];
    
    // Determine available columns based on current report
    switch (this.currentReportType) {
      case 'material':
        if (this.materialReportData.length === 0) return this.toastr.warning('No data to export');
        rawKeys = Object.keys(this.materialReportData[0]);
        break;
      case 'supplier':
        if (this.supplierReportData.length === 0) return this.toastr.warning('No data to export');
        rawKeys = Object.keys(this.supplierReportData[0]);
        break;
      case 'period':
        if (this.periodReportData.length === 0) return this.toastr.warning('No data to export');
        rawKeys = Object.keys(this.periodReportData[0]);
        break;
      case 'custom':
        if (this.customReportData.length === 0) return this.toastr.warning('No data to export');
        rawKeys = Object.keys(this.customReportData[0]);
        break;
    }

    // Build the column config for the modal
    this.exportColumns = rawKeys.map(key => ({
      key: key,
      label: this.formatLabel(key),
      selected: true // By default, select all
    }));

    this.showExportModal = true;
  }

  closeExportModal(): void {
    this.showExportModal = false;
  }

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

    let data: any[] = [];
    let title = '';
    let filename = '';
    
    switch (this.currentReportType) {
      case 'material':
        data = this.materialReportData;
        title = 'Material Stock Report';
        filename = 'material_wise_report';
        break;
      case 'supplier':
        data = this.supplierReportData;
        title = 'Supplier Purchases Report';
        filename = 'supplier_wise_report';
        break;
      case 'period':
        data = this.periodReportData;
        title = 'Period Stock Balance Report';
        filename = 'period_report';
        break;
      case 'custom':
        data = this.customReportData;
        title = 'Custom Stock Report';
        filename = 'custom_report';
        break;
    }

    // Create ExcelJS Workbook
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Report Data');

    // Add a Main Title Row
    worksheet.mergeCells(`A1:${String.fromCharCode(64 + selectedCols.length)}1`);
    const titleCell = worksheet.getCell('A1');
    titleCell.value = `Enterprise System: ${title}`;
    titleCell.font = { name: 'Arial', size: 16, bold: true, color: { argb: 'FFFFFFFF' } };
    titleCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1F3864' } }; // Dark Blue
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    worksheet.getRow(1).height = 30;

    // Add Subtitle (Date)
    const dateStr = new Date().toISOString().split('T')[0];
    worksheet.mergeCells(`A2:${String.fromCharCode(64 + selectedCols.length)}2`);
    const dateCell = worksheet.getCell('A2');
    dateCell.value = `Generated on: ${new Date().toLocaleString()}`;
    dateCell.font = { name: 'Arial', size: 10, italic: true };
    dateCell.alignment = { horizontal: 'right' };

    // Spacer Row
    worksheet.addRow([]);

    // Add Headers
    const headerRow = worksheet.addRow(selectedCols.map(c => c.label));
    headerRow.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F81BD' } }; // Light Blue
      cell.font = { name: 'Arial', size: 12, bold: true, color: { argb: 'FFFFFFFF' } };
      cell.alignment = { horizontal: 'center' };
      cell.border = {
        top: { style: 'thin' }, left: { style: 'thin' },
        bottom: { style: 'thin' }, right: { style: 'thin' }
      };
    });

    // Add Data
    data.forEach((item, index) => {
      const rowData = selectedCols.map(c => item[c.key]);
      const row = worksheet.addRow(rowData);
      
      // Alternating row colors for readability
      if (index % 2 === 0) {
        row.eachCell((cell) => {
          cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F2F2' } };
        });
      }
    });

    // Adjust Column Widths
    worksheet.columns.forEach(column => {
      column.width = 22;
    });

    // Generate Excel File
    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, `${filename}_${dateStr}.xlsx`);

    this.toastr.success('Enterprise Report generated successfully!');
    this.closeExportModal();
  }

  // NOTE: You must update your 'Export' button in reports.component.html 
  // to call openExportModal() instead of exportToExcel()
  exportToExcel(): void {
    this.openExportModal();
  }

  exportFromBackend(): void {
    const filters: ReportFilter = this.reportForm.value;
    this.reportService.exportReport(this.currentReportType, filters);
  }

  toggleChart(): void {
    this.showChart = !this.showChart;
  }

  get totalMaterialCost(): number {
    return this.materialReportData.reduce((sum, item) => sum + item.total_cost, 0);
  }

  get totalSupplierCost(): number {
    return this.supplierReportData.reduce((sum, item) => sum + item.total_cost, 0);
  }

  getReportSummary(): any {
    switch (this.currentReportType) {
      case 'material':
        return {
          totalItems: this.materialReportData.length,
          totalCost: this.totalMaterialCost,
          avgCost: this.materialReportData.length > 0 
            ? this.totalMaterialCost / this.materialReportData.length 
            : 0
        };
      case 'supplier':
        const uniqueSuppliers = new Set(this.supplierReportData.map(item => item.supplier_name));
        return {
          totalItems: this.supplierReportData.length,
          uniqueSuppliers: uniqueSuppliers.size,
          totalCost: this.totalSupplierCost
        };
      case 'period':
        return {
          totalItems: this.periodReportData.length,
          avgOpening: this.periodReportData.reduce((sum, item) => sum + item.opening_stock, 0) / this.periodReportData.length || 0,
          avgClosing: this.periodReportData.reduce((sum, item) => sum + item.closing_stock, 0) / this.periodReportData.length || 0
        };
      default:
        return {};
    }
  }
}
