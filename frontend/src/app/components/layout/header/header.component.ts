import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { User } from '../../../models/user.model';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss']
})
export class HeaderComponent implements OnInit {
  currentUser: User | null = null;
  isMenuCollapsed = true;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
    });
  }

  logout(): void {
    this.authService.logout();
  }

  toggleMenu(): void {
    this.isMenuCollapsed = !this.isMenuCollapsed;
  }

  hasRole(role: string): boolean {
    return this.authService.hasRole(role);
  }

  getUserInitials(): string {
    if (!this.currentUser?.full_name) {
      return this.currentUser?.username?.charAt(0).toUpperCase() || 'U';
    }
    return this.currentUser.full_name
      .split(' ')
      .map(name => name.charAt(0))
      .join('')
      .toUpperCase();
  }
}
