import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Project, Site, ProjectCreateRequest } from '../models/project.model';

@Injectable({
  providedIn: 'root'
})
export class ProjectService {
  constructor(private api: ApiService) {}

  // ==========================================
  // PROJECT MANAGEMENT
  // ==========================================
  
  getProjects(params?: any): Observable<Project[]> {
    return this.api.get<Project[]>('projects', params);
  }

  getProject(id: number | string): Observable<Project> {
    return this.api.get<Project>(`projects/${id}`);
  }

  createProject(project: ProjectCreateRequest): Observable<Project> {
    return this.api.post<Project>('projects', project);
  }

  updateProject(id: number | string, project: Partial<Project>): Observable<Project> {
    return this.api.put<Project>(`projects/${id}`, project);
  }

  deleteProject(id: number | string): Observable<any> {
    return this.api.delete<any>(`projects/${id}`);
  }


  // ==========================================
  // SITE MANAGEMENT
  // ==========================================

  getProjectSites(projectId: number | string): Observable<Site[]> {
    return this.api.get<Site[]>(`projects/${projectId}/sites`);
  }

  getSite(id: number | string): Observable<Site> {
    return this.api.get<Site>(`sites/${id}`);
  }

  // NEW: Directly links a new site to a specific project
  addProjectSite(projectId: number | string, siteData: any): Observable<Site> {
    const payload = {
      ...siteData,
      project_id: typeof projectId === 'string' ? parseInt(projectId, 10) : projectId
    };
    return this.api.post<Site>(`projects/${projectId}/sites`, payload);
  }

  updateSite(id: number | string, site: Partial<Site>): Observable<Site> {
    return this.api.put<Site>(`sites/${id}`, site);
  }

  // NEW: Deletes the site via the projects router
  deleteProjectSite(siteId: number | string): Observable<any> {
    return this.api.delete<any>(`projects/sites/${siteId}`);
  }

  // (Kept for backwards compatibility if used elsewhere)
  createSite(site: Partial<Site>): Observable<Site> {
    return this.api.post<Site>('sites', site);
  }

  // (Kept for backwards compatibility if used elsewhere)
  deleteSite(id: number | string): Observable<any> {
    return this.api.delete<any>(`sites/${id}`);
  }


  // ==========================================
  // USER ACCESS / TEAM MANAGEMENT
  // ==========================================

  // NEW: Fetch all users currently assigned to a project
  getProjectUsers(projectId: number | string): Observable<any[]> {
    return this.api.get<any[]>(`projects/${projectId}/users`);
  }

  addUserToProject(projectId: number | string, userId: number | string): Observable<any> {
    return this.api.post<any>(`projects/${projectId}/users/${userId}`, {});
  }

  removeUserFromProject(projectId: number | string, userId: number | string): Observable<any> {
    return this.api.delete<any>(`projects/${projectId}/users/${userId}`);
  }
}
