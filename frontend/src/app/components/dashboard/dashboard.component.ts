import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { ProjectService } from '../../services/project.service';
import { StockService } from '../../services/stock.service';
import { ReportService } from '../../services/report.service';
import { User, UserRole } from '../../models/user.model';
import { Project } from '../../models/project.model';
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
  recentStockEntries: any[] = [];

  loading = false;

  private subscriptions: Subscription[] = [];
  private pendingCalls = 0;

  // Charts
  projectChart: Chart | null = null;
  stockChart: Chart | null = null;
  materialChart: Chart | null = null;

  constructor(
    private authService: AuthService,
    private userService: UserService,
    private projectService: ProjectService,
    private stockService: StockService,
    private reportService: ReportService,
    private toastr: ToastrService
  ) {}

  ngOnInit(): void {
    this.currentUser = this.authService.getCurrentUserValue();
    this.loadDashboardData();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    this.destroyCharts();
  }

  // ===============================
  // DASHBOARD DATA LOADER
  // ===============================
  loadDashboardData(): void {
    this.loading = true;
    this.pendingCalls = 0;

    if (this.isAdmin()) {
      this.trackCall();
      const sub = this.userService.getUserStats().subscribe({
        next: stats => this.userStats = stats,
        error: err => console.error('User stats error:', err),
        complete: () => this.finishCall()
      });
      this.subscriptions.push(sub);
    }

    this.trackCall();
    const projectsSub = this.projectService.getProjects({ limit: 5, sort_by: 'created_at', sort_order: 'desc' }).subscribe({
      next: projects => {
        this.recentProjects = projects;
        this.calculateProjectStats(projects);
      },
      error: err => console.error('Projects error:', err),
      complete: () => this.finishCall()
    });
    this.subscriptions.push(projectsSub);

    this.trackCall();
    const stockSub = this.stockService.getStockEntries({ limit: 10, sort_by: 'entry_date', sort_order: 'desc' }).subscribe({
      next: entries => {
        this.recentStockEntries = entries;
        this.loadStockSummary();
      },
      error: err => {
        console.error('Stock entries error:', err);
        this.finishCall();
      },
      complete: () => this.finishCall()
    });
    this.subscriptions.push(stockSub);
  }
  
  // ===============================
  // PROJECT STATS + CHART
  // ===============================
  calculateProjectStats(projects: Project[]): void {
    this.projectStats = {
      total_projects: projects.length,
      active_projects: projects.filter(p => p.status === 'IN_PROGRESS' || p.status === 'PLANNING').length,
      completed_projects: projects.filter(p => p.status === 'COMPLETED').length,
      on_hold_projects: projects.filter(p => p.status === 'ON_HOLD').length,
      total_sites: 0
    };

    projects.forEach(p => {
      this.projectService.getProjectSites(p.id).subscribe({
        next: (sites) => {
          p.sites = sites; 
          this.projectStats.total_sites += (sites ? sites.length : 0);
        },
        error: (err) => console.error(`Error loading sites for project ${p.id}`, err)
      });
    });

    setTimeout(() => this.createProjectChart(), 100);
  }
  
  // ===============================
  // STOCK SUMMARY + CHARTS
  // ===============================
  loadStockSummary(): void {
    if (this.isAdmin() || this.isOwner()) {
      this.trackCall();
      const sub = this.reportService.getStockValuationReport().subscribe({
        next: data => {
          // DEBUG TOOL: Press F12 in your browser to see exactly what fields the backend is sending
          console.log("Raw Stock Report Data from Backend:", data);

          this.stockStats = data.map((d: any) => {
            // Aggressive Data Sniffer: Look for ANY metric we can plot
            const val = Number(d.total_value || d.value || d.stock_value || 0);
            const qty = Number(d.current_balance || d.quantity || d.balance || d.total_quantity || 0);
            const cost = Number(d.standard_cost || d.cost || d.price || 0);
            
            let finalChartValue = val;
            
            // If total value is 0, try to manually multiply quantity * cost
            if (finalChartValue === 0 && qty > 0) {
                finalChartValue = qty * cost;
            }
            
            // If cost was ₹0, fallback to plotting the raw physical quantity!
            if (finalChartValue === 0 && qty > 0) {
                finalChartValue = qty; 
            }
            
            return {
              ...d,
              calculated_chart_value: finalChartValue,
              total_value: finalChartValue // Overwrite this so the top summary card updates too
            };
          });
          
          setTimeout(() => {
            this.createStockChart(this.stockStats.slice(0, 10));
            this.createMaterialChart(this.stockStats.slice(0, 8));
          }, 100);
        },
        error: err => console.error('Stock summary error:', err),
        complete: () => this.finishCall()
      });
      this.subscriptions.push(sub);
    }
  }

  // ===============================
  // CHARTS
  // ===============================
  createProjectChart(): void {
    this.destroyChart('projectChart');
    const ctx = document.getElementById('projectChart') as HTMLCanvasElement;
    if (!ctx) return;

    this.projectChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Active', 'Completed', 'On Hold'],
        datasets: [{
          data: [
            this.projectStats?.active_projects || 0,
            this.projectStats?.completed_projects || 0,
            this.projectStats?.on_hold_projects || 0
          ],
          backgroundColor: ['#0d6efd', '#198754', '#ffc107']
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
        labels: data.map(d => d.material || d.material_name || 'Item'),
        datasets: [{
          label: 'Stock Metric (Value or Qty)',
          data: data.map(d => d.calculated_chart_value || 0),
          backgroundColor: 'rgba(13, 110, 253, 0.7)',
          borderColor: 'rgb(13, 110, 253)',
          borderWidth: 1,
          borderRadius: 4,
          minBarLength: 10 // <-- BULLETPROOF FIX: Forces a visible bar even if the data evaluates to exactly 0
        }]
      },
      options: { 
        responsive: true, 
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }

  createMaterialChart(data: any[]): void {
    this.destroyChart('materialChart');
    const ctx = document.getElementById('materialChart') as HTMLCanvasElement;
    if (!ctx) return;

    const categories: { [key: string]: number } = {};
    data.forEach(d => {
      const key = d.category || 'Uncategorized';
      categories[key] = (categories[key] || 0) + 1;
    });

    this.materialChart = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: Object.keys(categories),
        datasets: [{
          data: Object.values(categories)
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  destroyChart(chartId: string): void {
    const canvas = document.getElementById(chartId) as HTMLCanvasElement;
    if (!canvas) return;
    const chart = Chart.getChart(canvas);
    if (chart) chart.destroy();
  }

  destroyCharts(): void {
    this.destroyChart('projectChart');
    this.destroyChart('stockChart');
    this.destroyChart('materialChart');
  }

  // ===============================
  // LOADER CONTROL
  // ===============================
  private trackCall(): void {
    this.pendingCalls++;
  }

  private finishCall(): void {
    this.pendingCalls--;
    if (this.pendingCalls <= 0) {
      this.loading = false;
    }
  }

  refreshDashboard(): void {
    this.destroyCharts();
    this.loadDashboardData();
    this.toastr.info('Dashboard refreshed');
  }

  // ===============================
  // HELPERS
  // ===============================
  getTotalStockValue(): number {
    return this.stockStats?.reduce(
      (sum: number, i: any) => sum + (i.calculated_chart_value || 0), 0
    ) || 0;
  }

  get userRoleText(): string {
    switch (this.currentUser?.role) {
      case UserRole.ADMIN: return 'Administrator';
      case UserRole.OWNER: return 'Project Owner';
      case UserRole.USER: return 'User';
      default: return 'Guest';
    }
  }

  isAdmin(): boolean {
    return this.authService.isAdmin();
  }

  isOwner(): boolean {
    return this.authService.isOwner();
  }

  isUser(): boolean {
    return this.authService.isUser();
  }

  scrollToRecent(): void {
    const element = document.getElementById('recentActivitySection');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
}
