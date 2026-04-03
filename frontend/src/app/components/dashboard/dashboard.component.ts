import { Component, OnInit, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Subscription } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { ProjectService } from '../../services/project.service';
import { StockService } from '../../services/stock.service';
import { MaterialService } from '../../services/material.service';
import { ReportService } from '../../services/report.service';
import { User, UserRole } from '../../models/user.model';
import { Project, Site } from '../../models/project.model';
import { Material } from '../../models/material.model';
import { ToastrService } from 'ngx-toastr';
import Chart from 'chart.js/auto';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit, OnDestroy {
  currentUser: User | null = null;
  userStats: any = null;
  projectStats: any = null;
  stockStats: any = null;

  recentProjects: Project[] = [];
  materials: Material[] = [];
  entrySites: Site[] = [];
  
  loading = false;
  showEntryModal = false;
  entryForm: FormGroup;

  private subscriptions: Subscription[] = [];
  private pendingCalls = 0;

  // Charts
  projectChart: Chart | null = null;
  stockChart: Chart | null = null;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private userService: UserService,
    private projectService: ProjectService,
    private stockService: StockService,
    private materialService: MaterialService,
    private reportService: ReportService,
    private toastr: ToastrService
  ) {
    // Initialize the Quick Entry Form
    this.entryForm = this.fb.group({
      project_id: ['', Validators.required],
      site_id: ['', Validators.required],
      material_id: ['', Validators.required],
      entry_type: ['received', Validators.required],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      reference: [''],
      remarks: ['']
    });
  }

  ngOnInit(): void {
    this.currentUser = this.authService.getCurrentUserValue();
    this.loadDashboardData();
    this.loadMaterialsList();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    this.destroyCharts();
  }

  // --- DATA LOADING ---
  loadDashboardData(): void {
    this.loading = true;
    this.pendingCalls = 0;

    if (this.isAdmin()) {
      this.trackCall();
      this.userService.getUserStats().subscribe({
        next: stats => this.userStats = stats,
        complete: () => this.finishCall()
      });
    }

    this.trackCall();
    this.projectService.getProjects({ limit: 5 }).subscribe({
      next: projects => {
        this.recentProjects = projects;
        this.calculateProjectStats(projects);
      },
      complete: () => this.finishCall()
    });

    this.trackCall();
    this.reportService.getStockValuationReport().subscribe({
      next: data => {
        this.stockStats = data;
        setTimeout(() => this.createStockChart(data.slice(0, 10)), 100);
      },
      complete: () => this.finishCall()
    });
  }

  loadMaterialsList(): void {
    this.materialService.getMaterials().subscribe(m => this.materials = m);
  }

  calculateProjectStats(projects: Project[]): void {
    this.projectStats = {
      total_projects: projects.length,
      // FIX: Matches the uppercase strings from your FastAPI backend
      active_projects: projects.filter(p => p.status === 'IN_PROGRESS' || p.status === 'PLANNING').length,
      completed_projects: projects.filter(p => p.status === 'COMPLETED').length,
      on_hold_projects: projects.filter(p => p.status === 'ON_HOLD').length,
      total_sites: projects.reduce((sum, p) => sum + (p.sites?.length || 0), 0)
    };
    setTimeout(() => this.createProjectChart(), 100);
  }

  // --- QUICK ENTRY MODAL LOGIC ---
  openEntryModal(): void {
    this.entryForm.reset({ entry_type: 'received' });
    this.showEntryModal = true;
  }

  onEntryProjectChange(projectId: any): void {
    const id = Number(projectId);
    if (id) {
      this.projectService.getProjectSites(id).subscribe(sites => {
        this.entrySites = sites.filter(s => s.status === 'ACTIVE' || s.status === 'active');
      });
    }
  }

  submitStockEntry(): void {
    if (this.entryForm.invalid) return;
    this.stockService.createStockEntry(this.entryForm.value).subscribe({
      next: () => {
        this.toastr.success('Stock recorded successfully!');
        this.showEntryModal = false;
        this.loadDashboardData(); // Refresh graphs immediately
      },
      error: () => this.toastr.error('Failed to record entry')
    });
  }

  // --- CHARTS ---
  createProjectChart(): void {
    this.destroyChart('projectChart');
    const ctx = document.getElementById('projectChart') as HTMLCanvasElement;
    if (!ctx) return;
    this.projectChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Active/Planning', 'Completed', 'On Hold'],
        datasets: [{
          data: [
            this.projectStats?.active_projects || 0,
            this.projectStats?.completed_projects || 0,
            this.projectStats?.on_hold_projects || 0
          ],
          backgroundColor: ['#3b82f6', '#10b981', '#f59e0b']
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  createStockChart(data: any[]): void {
    this.destroyChart('stockChart');
    const ctx = document.getElementById('stockChart') as HTMLCanvasElement;
    if (!ctx) return;
    this.stockChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.map(d => d.material),
        datasets: [{
          label: 'Stock Value (₹)',
          data: data.map(d => d.total_value),
          backgroundColor: '#6366f1'
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  // --- HELPERS ---
  private trackCall(): void { this.pendingCalls++; }
  private finishCall(): void { 
    this.pendingCalls--; 
    if (this.pendingCalls <= 0) this.loading = false; 
  }
  destroyChart(id: string): void {
    const canvas = document.getElementById(id) as HTMLCanvasElement;
    if (canvas) { const chart = Chart.getChart(canvas); if (chart) chart.destroy(); }
  }
  destroyCharts(): void { this.destroyChart('projectChart'); this.destroyChart('stockChart'); }
  getTotalStockValue(): number { return this.stockStats?.reduce((sum: number, i: any) => sum + (i.total_value || 0), 0) || 0; }
  isAdmin(): boolean { return this.authService.isAdmin(); }
  get userRoleText(): string {
    if (this.currentUser?.role === UserRole.ADMIN) return 'Administrator';
    if (this.currentUser?.role === UserRole.OWNER) return 'Project Owner';
    return 'User';
  }
}
