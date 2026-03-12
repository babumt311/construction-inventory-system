import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableDataSource, MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { TruncatePipe } from '../../pipes/truncate.pipe';

// Services and Models
import { AuditService } from '../../services/audit.service';
import { AuditLog, AuditAction, AuditResource } from '../../models/audit.model';

@Component({
  selector: 'app-audit-logs',
  templateUrl: './audit-logs.component.html',
  styleUrls: ['./audit-logs.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatFormFieldModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    TruncatePipe
  ]
})
export class AuditLogsComponent implements OnInit, OnDestroy {
  dataSource = new MatTableDataSource<AuditLog>([]);
  all_logs: AuditLog[] = [];
  
  displayedColumns: string[] = ['timestamp', 'user', 'action', 'entity', 'entityId', 'details', 'status', 'ipAddress', 'actions'];
  
  isLoading = false;
  loading = false;
  error = '';
  errorMessage = '';
  
  // Filters
  searchTerm = '';
  selectedUser: string | null = null;
  selectedAction: AuditAction | null = null;
  selectedEntity: string | null = null;
  uniqueUsers: string[] = [];
  actionTypes: string[] = Object.values(AuditAction);
  entityTypes: string[] = Object.values(AuditResource);
  dateRange = { start: '', end: '' };
  hasActiveFilters = false;
  
  // Pagination
  pageSize = 20;
  pageSizeOptions = [10, 20, 50, 100];
  
  filteredCount = 0;
  totalCount = 0;
  
  private destroy$ = new Subject<void>();

  constructor(private auditService: AuditService) {}

  ngOnInit(): void {
    this.loadAuditLogs();
  }

  loadAuditLogs(): void {
    this.loading = true;
    this.isLoading = true;
    this.error = '';
    this.errorMessage = '';
    
    this.auditService.getAuditLogs()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (logs: AuditLog[]) => {
          this.all_logs = logs;
          this.dataSource.data = [...logs];
          this.totalCount = logs.length;
          this.extractUniqueUsers();
          this.applyFilters();
          this.loading = false;
          this.isLoading = false;
        },
        error: (error: any) => {
          this.error = 'Failed to load audit logs';
          this.errorMessage = 'Failed to load audit logs';
          console.error('Error loading audit logs:', error);
          this.loading = false;
          this.isLoading = false;
        }
      });
  }

  refreshLogs(): void {
    this.loadAuditLogs();
  }

  extractUniqueUsers(): void {
    const users = new Set(this.all_logs.map(log => log.user));
    this.uniqueUsers = Array.from(users).sort();
  }

  applyFilters(): void {
    let filtered = [...this.all_logs];

    // Apply search filter
    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      filtered = filtered.filter(log =>
        log.user.toLowerCase().includes(term) ||
        log.resource.toLowerCase().includes(term) ||
        log.description.toLowerCase().includes(term)
      );
    }

    // Apply action filter
    if (this.selectedAction) {
      filtered = filtered.filter(log => log.action === this.selectedAction);
    }

    // Apply resource/entity filter
    if (this.selectedEntity) {
      filtered = filtered.filter(log => log.resource === this.selectedEntity);
    }

    // Apply user filter
    if (this.selectedUser) {
      filtered = filtered.filter(log => log.user === this.selectedUser);
    }

    // Apply date range filter
    if (this.dateRange.start) {
      const startDate = new Date(this.dateRange.start);
      filtered = filtered.filter(log => new Date(log.created_at) >= startDate);
    }
    
    if (this.dateRange.end) {
      const endDate = new Date(this.dateRange.end);
      endDate.setHours(23, 59, 59, 999);
      filtered = filtered.filter(log => new Date(log.created_at) <= endDate);
    }

    // Sort by created_at (newest first)
    filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    this.dataSource.data = filtered;
    this.filteredCount = filtered.length;
    this.updateActiveFiltersFlag();
  }

  updateActiveFiltersFlag(): void {
    this.hasActiveFilters = !!(
      this.searchTerm || 
      this.selectedUser || 
      this.selectedAction || 
      this.selectedEntity || 
      this.dateRange.start || 
      this.dateRange.end
    );
  }

  applyFilter(): void {
    this.applyFilters();
  }

  clearAllFilters(): void {
    this.searchTerm = '';
    this.selectedUser = null;
    this.selectedAction = null;
    this.selectedEntity = null;
    this.dateRange = { start: '', end: '' };
    this.applyFilters();
  }

  clearDateFilter(): void {
    this.dateRange = { start: '', end: '' };
    this.applyFilters();
  }

  exportLogs(): void {
    this.auditService.exportAuditLogs()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (blob: Blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`;
          a.click();
          window.URL.revokeObjectURL(url);
        },
        error: (error) => {
          this.error = 'Failed to export logs';
          console.error('Error exporting logs:', error);
        }
      });
  }

  getActionClass(action: AuditAction): string {
    switch (action) {
      case 'CREATE': return 'badge bg-success';
      case 'UPDATE': return 'badge bg-warning text-dark';
      case 'DELETE': return 'badge bg-danger';
      case 'LOGIN': return 'badge bg-info';
      default: return 'badge bg-primary';
    }
  }

  getResourceClass(resource: AuditResource): string {
    switch (resource) {
      case 'USER': return 'badge bg-primary';
      case 'PROJECT': return 'badge bg-success';
      case 'MATERIAL': return 'badge bg-warning text-dark';
      case 'STOCK': return 'badge bg-info';
      case 'PO': return 'badge bg-secondary';
      default: return 'badge bg-dark';
    }
  }

  getEntityIcon(entityType: string): string {
    switch (entityType) {
      case 'USER': return 'person';
      case 'PROJECT': return 'assignment';
      case 'MATERIAL': return 'inventory_2';
      case 'STOCK': return 'warehouse';
      case 'PO': return 'receipt';
      default: return 'category';
    }
  }

  getDisplayRange(): string {
    const data = this.dataSource.filteredData;
    if (data.length === 0) return 'No entries';
    const start = this.pageSize > data.length ? 1 : 1;
    const end = Math.min(this.pageSize, data.length);
    return `${start}-${end}`;
  }

  onPageChange(event: PageEvent): void {
    this.pageSize = event.pageSize;
  }

  onPageSizeChange(size: number): void {
    this.pageSize = size;
  }

  viewLogDetails(log: AuditLog): void {
    console.log('View details for:', log);
    // TODO: Open a dialog with detailed log information
  }

  copyLogDetails(log: AuditLog): void {
    const details = JSON.stringify(log, null, 2);
    navigator.clipboard.writeText(details).then(() => {
      console.log('Log details copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}