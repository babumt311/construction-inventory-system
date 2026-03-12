import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.scss']
})
export class SidebarComponent implements OnInit {
  currentUser: any = null;
  menuItems = [
    {
      title: 'Dashboard',
      icon: 'bi-speedometer2',
      route: '/dashboard',
      roles: ['admin', 'owner', 'user']
    },
    {
      title: 'Materials',
      icon: 'bi-box-seam',
      route: '/materials',
      roles: ['admin', 'owner', 'user']
    },
    {
      title: 'Stock Balance',
      icon: 'bi-stack',
      route: '/stock',
      roles: ['admin', 'owner', 'user']
    },
    {
      title: 'Purchase Orders',
      icon: 'bi-cart-check',
      route: '/purchase-orders',
      roles: ['admin', 'owner']
    }
  ];

  constructor(
    private router: Router,
    private authService: AuthService
  ) { }

  ngOnInit(): void {
    this.currentUser = this.authService.getCurrentUserValue();
  }

  hasAccess(roles: string[]): boolean {
    if (!this.currentUser) return false;
    return roles.includes(this.currentUser.role);
  }

  isActive(route: string): boolean {
    return this.router.url === route;
  }
}

