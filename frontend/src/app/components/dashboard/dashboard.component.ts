import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { ProjectService } from '../../services/project.service';
import { StockService } from '../../services/stock.service';
import { ReportService } from '../../services/report.service';
import { ApiService } from '../../services/api.service';
import { User, UserRole } from '../../models/user.model';
import { Project } from '../../models/project.model';
import { ToastrService } from 'ngx-toastr';

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
  
  lowStockItems: any[] = [];
  actionableTasks: any[] = [];

  loading = false;

  // Enterprise strict typing for the latest report date
  latestReportDate: string | Date | null = null;

  private subscriptions: Subscription[] = [];
  private pendingCalls = 0;

  constructor(
    private authService: AuthService,
    private userService: UserService,
    private projectService: ProjectService,
    private stockService: StockService,
    private reportService: ReportService,
    private api: ApiService,
    private toastr: ToastrService
  ) {}

  ngOnInit(): void {
    this.currentUser = this.authService.getCurrentUserValue();
    this.loadDashboardData();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  // ===============================
  // DASHBOARD DATA LOADER
  // ===============================
  loadDashboardData(): void {
    this.loading = true;
    this.pendingCalls = 0;

    // Admin user stats
    if (this.isAdmin()) {
      this.trackCall();
      const sub = this.userService.getUserStats().subscribe({
        next: stats => this.userStats = stats,
        complete: () => this.finishCall()
      });
      this.subscriptions.push(sub);
    }

    // Recent projects for the table
    this.trackCall();
    const projectsSub = this.projectService.getProjects({ limit: 5, sort_by: 'created_at', sort_order: 'desc' }).subscribe({
      next: projects => {
        this.recentProjects = projects;
        this.calculateProjectStats(projects);
      },
      complete: () => this.finishCall()
    });
    this.subscriptions.push(projectsSub);

    // Global fetch for widgets (All Projects)
    this.trackCall();
    this.projectService.getProjects().subscribe({
      next: (allProjects) => {
        this.loadActionableTasks(allProjects);
        this.loadLowStockItems(allProjects);
      },
      complete: () => this.finishCall()
    });

    // ==========================================
    // NEW: FETCH LATEST REPORT / ACTIVITY DATE
    // ==========================================
    this.trackCall();
    // We use the generic ApiService to grab the most recent global stock entry
    const reportsSub = this.api.get<any[]>('stock/entries/', { limit: 1 }).subscribe({
      next: (entries) => {
        if (entries && entries.length > 0) {
          // Extracts the most recent transaction date
          this.latestReportDate = entries[0].entry_date || entries[0].created_at; 
        } else {
          this.latestReportDate = null;
        }
      },
      error: (err) => {
        console.error('Failed to load latest activity date', err);
        this.latestReportDate = null; // Failsafe triggers the HTML "No reports" message
      },
      complete: () => this.finishCall()
    });
    this.subscriptions.push(reportsSub);
    // ==========================================

    this.loadStockSummary();
  }
  
  // ===============================
  // WIDGET DATA FETCHERS
  // ===============================
  
  // Fetch Overdue and Review Tasks
  loadActionableTasks(projects: Project[]): void {
    this.actionableTasks = [];
    projects.forEach(p => {
      this.api.get<any[]>(`projects/${p.id}/tasks`).subscribe({
        next: (tasks) => {
          if(!tasks) return;
          const filtered = tasks.filter(t => t.status === 'review' || this.isOverdue(t))
                                .map(t => ({...t, projectName: p.name, projectId: p.id}));
          this.actionableTasks = [...this.actionableTasks, ...filtered];
        }
      });
    });
  }

  // Fetch Low Stock across all sites
  loadLowStockItems(projects: Project[]): void {
    this.lowStockItems = [];
    projects.forEach(p => {
      this.projectService.getProjectSites(p.id).subscribe(sites => {
        if(!sites) return;
        sites.forEach((s: any) => {
          this.stockService.getSiteStockSummary(s.id).subscribe((balances: any) => {
            if(!balances) return;
            const lowStocks = balances.filter((b: any) => b.current_balance < 10)
                                      .map((b: any) => ({...b, projectName: p.name, siteName: s.name}));
            this.lowStockItems = [...this.lowStockItems, ...lowStocks];
          });
        });
      });
    });
  }

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
        }
      });
    });
  }
  
  loadStockSummary(): void {
    if (this.isAdmin() || this.isOwner()) {
      this.trackCall();
      const sub = this.reportService.getStockValuationReport().subscribe({
        next: data => {
          this.stockStats = data.map((d: any) => {
            const val = Number(d.total_value || d.value || 0);
            const qty = Number(d.current_balance || d.quantity || 0);
            const cost = Number(d.standard_cost || d.cost || 0);
            const finalVal = val === 0 && qty > 0 ? qty * cost : val;
            return { ...d, total_value: finalVal };
          });
        },
        complete: () => this.finishCall()
      });
      this.subscriptions.push(sub);
    }
  }

  // ===============================
  // HELPERS & LOADER CONTROL
  // ===============================
  isOverdue(task: any): boolean {
    if (!task.dueDate) return false;
    return new Date(task.dueDate) < new Date() && task.status !== 'completed';
  }

  private trackCall(): void { this.pendingCalls++; }
  private finishCall(): void {
    this.pendingCalls--;
    if (this.pendingCalls <= 0) this.loading = false;
  }

  refreshDashboard(): void {
    this.loadDashboardData();
    this.toastr.info('Dashboard refreshed');
  }

  getTotalStockValue(): number {
    return this.stockStats?.reduce((sum: number, i: any) => sum + (i.total_value || 0), 0) || 0;
  }

  get userRoleText(): string {
    switch (this.currentUser?.role) {
      case UserRole.ADMIN: return 'Administrator';
      case UserRole.OWNER: return 'Project Owner';
      case UserRole.USER: return 'User';
      default: return 'Guest';
    }
  }

  isAdmin(): boolean { return this.authService.isAdmin(); }
  isOwner(): boolean { return this.authService.isOwner(); }
  isUser(): boolean { return this.authService.isUser(); }

  scrollToRecent(): void {
    const element = document.getElementById('recentActivitySection');
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
