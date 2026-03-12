import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { UserRole } from '../../models/user.model';
import { Location } from '@angular/common';

@Component({
  selector: 'app-unauthorized',
  templateUrl: './unauthorized.component.html',
  styleUrls: ['./unauthorized.component.scss'],
  standalone: true,
  imports: [CommonModule, RouterModule]
})
export class UnauthorizedComponent implements OnInit {
  errorCode = 403;
  errorMessage = 'Access Denied';
  suggestion = 'You do not have permission to access this page.';
  userRole = '';
  requiredRole = '';

  constructor(private authService: AuthService, private location: Location) {}

  ngOnInit(): void {
    const user = this.authService.getCurrentUserValue();
    this.userRole = user?.role || 'GUEST';
    
    // Extract required role from URL or query params if available
    const url = window.location.pathname;
    this.setRequiredRoleBasedOnUrl(url);
  }

  private setRequiredRoleBasedOnUrl(url: string): void {
    if (url.includes('/admin')) {
      this.requiredRole = 'ADMIN';
    } else if (url.includes('/manager')) {
      this.requiredRole = 'PROJECT_MANAGER';
    } else if (url.includes('/user-management')) {
      this.requiredRole = 'ADMIN';
    } else if (url.includes('/audit-logs')) {
      this.requiredRole = 'ADMIN';
    } else {
      this.requiredRole = 'AUTHENTICATED_USER';
    }
  }

  getRoleDisplayName(role: string): string {
    switch (role) {
      case 'admin': return 'Administrator';
      case 'owner': return 'Owner';
      case 'user': return 'User';
      default: return role;
    }
  }

  contactSupport(): void {
    window.location.href = 'mailto:support@example.com?subject=Access Request';
  }

  requestAccess(): void {
    // Implement access request logic
    alert('Access request has been submitted to administrators.');
  }

  goBack(): void {
    this.location.back();
  }

}
