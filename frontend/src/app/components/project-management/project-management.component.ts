import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

// Services
import { ProjectService } from '../../services/project.service';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service'; // <-- NEW: Added ApiService

// Models
import { Project } from '../../models/project.model';

@Component({
  selector: 'app-project-management',
  templateUrl: './project-management.component.html',
  styleUrls: ['./project-management.component.scss']
})
export class ProjectManagementComponent implements OnInit, OnDestroy {

  protected readonly Math = Math;

  projects: Project[] = [];
  filteredProjects: Project[] = [];
  selectedProject: Project | null = null;

  // NEW: Maps to store the real database counts for fast lookup
  projectProgressMap: Map<number, number> = new Map();
  projectTeamCountMap: Map<number, number> = new Map();

  isLoading = false;
  errorMessage = '';

  // Filters
  searchTerm = '';
  statusFilter: 'ALL' | string = 'ALL';
  dateRange = { start: '', end: '' };

  // Pagination
  currentPage = 1;
  itemsPerPage = 10;
  totalItems = 0;

  // User role
  userRole = '';

  // Modal Controls
  showAddModal = false;
  showEditModal = false;
  editingProject: Project | null = null;

  private destroy$ = new Subject<void>();

  constructor(
    private projectService: ProjectService,
    private authService: AuthService,
    private api: ApiService // <-- NEW: Injected ApiService
  ) {}

  ngOnInit(): void {
    this.loadProjects();
    this.loadUserRole();
  }

  loadProjects(): void {
    this.isLoading = true;

    this.projectService.getProjects()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (projects: Project[]) => {
          this.projects = projects;
          this.filteredProjects = [...projects];
          this.totalItems = projects.length;
          
          // NEW: Loop through all projects and ask the backend for their real Team/Task data!
          this.projects.forEach(p => this.loadProjectDetails(p.id));

          this.applyFilters();
          this.isLoading = false;
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to load projects';
          console.error('Error loading projects:', error);
          this.isLoading = false;
        }
      });
  }

  // --- NEW: Load Real Data from the Backend JSON Persistent Storage ---
  loadProjectDetails(projectId: number): void {
    // Load Team Count
    this.api.get<any[]>(`projects/${projectId}/team`).subscribe({
      next: (team) => {
        this.projectTeamCountMap.set(projectId, team ? team.length : 0);
      },
      error: () => this.projectTeamCountMap.set(projectId, 0)
    });

    // Load Tasks and Calculate Progress %
    this.api.get<any[]>(`projects/${projectId}/tasks`).subscribe({
      next: (tasks) => {
        if (!tasks || tasks.length === 0) {
          this.projectProgressMap.set(projectId, 0);
        } else {
          const completedTasks = tasks.filter(t => t.status === 'completed').length;
          this.projectProgressMap.set(projectId, Math.round((completedTasks / tasks.length) * 100));
        }
      },
      error: () => this.projectProgressMap.set(projectId, 0)
    });
  }

  loadUserRole(): void {
    this.authService.getCurrentUser()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (user) => {
          this.userRole = user?.role || '';
        },
        error: () => {
          this.userRole = '';
        }
      });
  }

  selectProject(project: Project): void {
    this.selectedProject = project;
  }

  createProject(projectData: Partial<Project>): void {
    this.projectService.createProject(projectData as any)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (newProject: Project) => {
          this.projects.push(newProject);
          this.filteredProjects = [...this.projects];
          this.applyFilters();
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to create project';
          console.error('Error creating project:', error);
        }
      });
  }

  updateProject(projectId: number, updates: Partial<Project>): void {
    this.projectService.updateProject(projectId, updates)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (updatedProject: Project) => {
          const index = this.projects.findIndex(p => p.id === projectId);
          if (index !== -1) {
            this.projects[index] = updatedProject;
            this.filteredProjects = [...this.projects];
            this.applyFilters();
            
            if (this.selectedProject?.id === projectId) {
              this.selectedProject = updatedProject;
            }
          }
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to update project';
          console.error('Error updating project:', error);
        }
      });
  }

  deleteProject(projectId: number): void {
    if (!confirm('Are you sure you want to delete this project?')) {
      return;
    }

    this.projectService.deleteProject(projectId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.projects = this.projects.filter(p => p.id !== projectId);
          this.filteredProjects = [...this.projects];
          this.applyFilters();
          if (this.selectedProject?.id === projectId) {
            this.selectedProject = null;
          }
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to delete project';
          console.error('Error deleting project:', error);
        }
      });
  }

  applyFilters(): void {
    let filtered = [...this.projects];

    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      filtered = filtered.filter(project =>
        project.name.toLowerCase().includes(term) ||
        project.description?.toLowerCase().includes(term) ||
        project.code?.toLowerCase().includes(term)
      );
    }

    if (this.statusFilter !== 'ALL') {
      filtered = filtered.filter(
        project => project.status === this.statusFilter
      );
    }

    if (this.dateRange.start) {
      const startDate = new Date(this.dateRange.start);
      filtered = filtered.filter(
        project =>
          project.start_date &&
          new Date(project.start_date) >= startDate
      );
    }

    if (this.dateRange.end) {
      const endDate = new Date(this.dateRange.end);
      filtered = filtered.filter(
        project =>
          project.end_date &&
          new Date(project.end_date) <= endDate
      );
    }

    this.filteredProjects = filtered;
    this.totalItems = filtered.length;
    this.currentPage = 1;
  }

  clearFilters(): void {
    this.searchTerm = '';
    this.statusFilter = 'ALL';
    this.dateRange = { start: '', end: '' };
    this.applyFilters();
  }

  get paginatedProjects(): Project[] {
    const startIndex = (this.currentPage - 1) * this.itemsPerPage;
    return this.filteredProjects.slice(
      startIndex,
      startIndex + this.itemsPerPage
    );
  }

  changePage(page: number): void {
    this.currentPage = page;
  }

  getProjectStats(): {
    total: number;
    active: number;
    completed: number;
    delayed: number;
  } {
    const now = new Date();
    return {
      total: this.projects.length,
      active: this.projects.filter(p => p.status === 'IN_PROGRESS').length,
      completed: this.projects.filter(p => p.status === 'COMPLETED').length,
      delayed: this.projects.filter(
        p =>
          p.status === 'IN_PROGRESS' &&
          p.end_date &&
          new Date(p.end_date) < now
      ).length
    };
  }

  canEditProject(): boolean {
    if (!this.userRole) return false;
    const role = this.userRole.toLowerCase();
    return ['admin', 'project_manager', 'owner'].includes(role);
  }

  canDeleteProject(): boolean {
    if (!this.userRole) return false;
    return this.userRole.toLowerCase() === 'admin';
  }

  // --- Add Project Controls ---
  openAddModal(): void {
    this.showAddModal = true;
  }

  closeAddModal(): void {
    this.showAddModal = false;
  }

  submitNewProject(code: string, name: string, client: string, status: string, startDate: string, endDate: string, budget: string, description: string): void {
    if (!code || !name) {
      alert('Please provide both a Project Code and Project Name.');
      return;
    }

    const newProjectPayload: Partial<Project> = {
      code: code,
      name: name,
      client: client || '',
      status: status,
      start_date: startDate ? new Date(startDate) : undefined,
      end_date: endDate ? new Date(endDate) : undefined,
      budget: budget ? parseFloat(budget) : 0,
      description: description || '',
      progress: 0
    };

    this.createProject(newProjectPayload); 
    this.closeAddModal();
  }

  // --- Edit Project Controls ---
  openEditModal(project: Project): void {
    this.editingProject = project;
    this.showEditModal = true;
  }

  closeEditModal(): void {
    this.showEditModal = false;
    this.editingProject = null;
  }

  submitEditProject(code: string, name: string, client: string, status: string, startDate: string, endDate: string, budget: string, description: string): void {
    if (!this.editingProject || !code || !name) {
      alert('Please provide both a Project Code and Project Name.');
      return;
    }

    const updates: Partial<Project> = {
      code: code,
      name: name,
      client: client || '',
      status: status,
      start_date: startDate ? new Date(startDate) : undefined,
      end_date: endDate ? new Date(endDate) : undefined,
      budget: budget ? parseFloat(budget) : 0,
      description: description || ''
    };

    this.updateProject(this.editingProject.id, updates); 
    this.closeEditModal();
  }

  formatDateForInput(date: Date | string | undefined): string {
    if (!date) return '';
    const d = new Date(date);
    return d.toISOString().split('T')[0];
  }

  // --- UPDATED: Read from our local memory Maps instead of LocalStorage! ---
  getProjectProgress(projectId: any): number {
    return this.projectProgressMap.get(projectId) || 0;
  }

  getProjectTeamCount(projectId: any): number {
    return this.projectTeamCountMap.get(projectId) || 0;
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
