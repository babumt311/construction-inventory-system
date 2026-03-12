import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Project, Site, ProjectCreateRequest } from '../models/project.model';

@Injectable({
  providedIn: 'root'
})
export class ProjectService {
  constructor(private api: ApiService) {}

  // Project Management
  getProjects(params?: any): Observable<Project[]> {
    return this.api.get<Project[]>('projects', params);
  }

  getProject(id: number): Observable<Project> {
    return this.api.get<Project>(`projects/${id}`);
  }

  createProject(project: ProjectCreateRequest): Observable<Project> {
    return this.api.post<Project>('projects', project);
  }

  updateProject(id: number, project: Partial<Project>): Observable<Project> {
    return this.api.put<Project>(`projects/${id}`, project);
  }

  deleteProject(id: number): Observable<any> {
    return this.api.delete<any>(`projects/${id}`);
  }

  // Site Management
  getProjectSites(projectId: number): Observable<Site[]> {
    return this.api.get<Site[]>(`projects/${projectId}/sites`);
  }

  getSite(id: number): Observable<Site> {
    return this.api.get<Site>(`sites/${id}`);
  }

  createSite(site: Partial<Site>): Observable<Site> {
    return this.api.post<Site>('sites', site);
  }

  updateSite(id: number, site: Partial<Site>): Observable<Site> {
    return this.api.put<Site>(`sites/${id}`, site);
  }

  deleteSite(id: number): Observable<any> {
    return this.api.delete<any>(`sites/${id}`);
  }

  // User Access Management
  addUserToProject(projectId: number, userId: number): Observable<any> {
    return this.api.post<any>(`projects/${projectId}/users/${userId}`, {});
  }

  removeUserFromProject(projectId: number, userId: number): Observable<any> {
    return this.api.delete<any>(`projects/${projectId}/users/${userId}`);
  }
}
