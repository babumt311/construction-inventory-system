import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { User, UserRole, RegisterRequest } from '../models/user.model';
import { Project } from '../models/project.model';

@Injectable({
  providedIn: 'root'
})
export class UserService {
 // resetPassword(userId: string) {
    //throw new Error('Method not implemented.');
  //}
  constructor(private api: ApiService) {}

  // User Management
  getUsers(params?: any): Observable<User[]> {
    return this.api.get<User[]>('users', params);
  }

  getUser(id: number): Observable<User> {
    return this.api.get<User>(`users/${id}`);
  }

  createUser(user: RegisterRequest): Observable<User> {
    return this.api.post<User>('users', user);
  }

  updateUser(id: number, user: Partial<User>): Observable<User> {
    return this.api.put<User>(`users/${id}`, user);
  }

  deleteUser(id: number): Observable<any> {
    return this.api.delete<any>(`users/${id}`);
  }

  activateUser(id: number): Observable<any> {
    return this.api.post<any>(`users/${id}/activate`, {});
  }

  deactivateUser(id: number): Observable<any> {
    return this.api.post<any>(`users/${id}/deactivate`, {});
  }

  // Project Access
  getUserProjects(userId: number): Observable<Project[]> {
    return this.api.get<Project[]>(`users/${userId}/projects`);
  }

  // Statistics
  getUserStats(): Observable<any> {
    return this.api.get<any>('users/stats');
  }
}
