import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

// Services
import { ProjectService } from '../../services/project.service';
import { AuthService } from '../../services/auth.service';

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

  // Modal Control
  showAddModal = false;

  private destroy$ = new Subject<void>();

  constructor(
    private projectService: ProjectService,
    private authService: AuthService
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
          this.selectedProject = null;
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
        project.description?.toLowerCase().includes(term)
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

  // FIXED: Made case-insensitive so the buttons actually appear!
  canEditProject(): boolean {
    if (!this.userRole) return false;
    const role = this.userRole.toLowerCase();
    return ['admin', 'project_manager', 'owner'].includes(role);
  }

  canDeleteProject(): boolean {
    if (!this.userRole) return false;
    return this.userRole.toLowerCase() === 'admin';
  }

  // --- Modal & Form Controls ---
  openAddModal(): void {
    this.showAddModal = true;
  }

  closeAddModal(): void {
    this.showAddModal = false;
  }

  submitNewProject(name: string, client: string, status: string, startDate: string, endDate: string, budget: string, description: string): void {
    if (!name) {
      alert('Please provide at least a Project Name.');
      return;
    }

    const newProjectPayload = {
      name: name,
      client: client || '',
      status: status,
      start_date: startDate ? new Date(startDate).toISOString() : undefined,
      end_date: endDate ? new Date(endDate).toISOString() : undefined,
      budget: budget ? parseFloat(budget) : 0,
      description: description || '',
      progress: 0
    };

    this.createProject(newProjectPayload); 
    this.closeAddModal();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
