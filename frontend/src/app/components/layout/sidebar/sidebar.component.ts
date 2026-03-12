import { Component, OnInit } from '@angular/core';
import { AuthService } from '../../../services/auth.service';
import { User, UserRole } from '../../../models/user.model';

interface MenuItem {
  title: string;
  icon: string;
  route: string;
  roles: UserRole[];
  children?: MenuItem[];
  expanded?: boolean;
}

@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.scss']
})
export class SidebarComponent implements OnInit {
  currentUser: User | null = null;
  
  menuItems: MenuItem[] = [
    {
      title: 'Dashboard',
      icon: 'fas fa-tachometer-alt',
      route: '/dashboard',
      roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
    },
    {
      title: 'Projects',
      icon: 'fas fa-project-diagram',
      route: '/projects',
      roles: [UserRole.ADMIN, UserRole.OWNER],
      children: [
        {
          title: 'All Projects',
          icon: 'fas fa-list',
          route: '/projects',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        },
        {
          title: 'Add Project',
          icon: 'fas fa-plus',
          route: '/projects/create',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        },
        {
          title: 'Site Management',
          icon: 'fas fa-map-marker-alt',
          route: '/sites',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        }
      ]
    },
    {
      title: 'Materials',
      icon: 'fas fa-boxes',
      route: '/materials',
      roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER],
      children: [
        {
          title: 'Material List',
          icon: 'fas fa-list',
          route: '/materials',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Categories',
          icon: 'fas fa-tags',
          route: '/materials/categories',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        },
        {
          title: 'Excel Upload',
          icon: 'fas fa-file-excel',
          route: '/materials/upload',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        }
      ]
    },
    {
      title: 'Stock Management',
      icon: 'fas fa-warehouse',
      route: '/stock',
      roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER],
      children: [
        {
          title: 'Stock Entries',
          icon: 'fas fa-edit',
          route: '/stock/entries',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Stock Balance',
          icon: 'fas fa-calculator',
          route: '/stock/balance',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Daily Reports',
          icon: 'fas fa-file-alt',
          route: '/stock/reports',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        }
      ]
    },
    {
      title: 'Purchase Orders',
      icon: 'fas fa-file-invoice-dollar',
      route: '/purchase-orders',
      roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER],
      children: [
        {
          title: 'PO Entries',
          icon: 'fas fa-list',
          route: '/purchase-orders',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Create PO',
          icon: 'fas fa-plus',
          route: '/purchase-orders/create',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Suppliers',
          icon: 'fas fa-truck',
          route: '/suppliers',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        }
      ]
    },
    {
      title: 'Reports',
      icon: 'fas fa-chart-bar',
      route: '/reports',
      roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER],
      children: [
        {
          title: 'Material Reports',
          icon: 'fas fa-box',
          route: '/reports/material',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Supplier Reports',
          icon: 'fas fa-truck',
          route: '/reports/supplier',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        },
        {
          title: 'Period Reports',
          icon: 'fas fa-calendar-alt',
          route: '/reports/period',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        },
        {
          title: 'Custom Reports',
          icon: 'fas fa-cogs',
          route: '/reports/custom',
          roles: [UserRole.ADMIN, UserRole.OWNER]
        }
      ]
    },
    {
      title: 'User Management',
      icon: 'fas fa-users-cog',
      route: '/users',
      roles: [UserRole.ADMIN],
      children: [
        {
          title: 'All Users',
          icon: 'fas fa-users',
          route: '/users',
          roles: [UserRole.ADMIN]
        },
        {
          title: 'Create User',
          icon: 'fas fa-user-plus',
          route: '/users/create',
          roles: [UserRole.ADMIN]
        },
        {
          title: 'Audit Logs',
          icon: 'fas fa-history',
          route: '/audit-logs',
          roles: [UserRole.ADMIN]
        }
      ]
    },
    {
      title: 'Settings',
      icon: 'fas fa-cog',
      route: '/settings',
      roles: [UserRole.ADMIN, UserRole.OWNER],
      children: [
        {
          title: 'Profile',
          icon: 'fas fa-user',
          route: '/profile',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'Change Password',
          icon: 'fas fa-key',
          route: '/change-password',
          roles: [UserRole.ADMIN, UserRole.OWNER, UserRole.USER]
        },
        {
          title: 'System Settings',
          icon: 'fas fa-sliders-h',
          route: '/settings/system',
          roles: [UserRole.ADMIN]
        }
      ]
    }
  ];

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
    });
  }

  toggleMenuItem(item: MenuItem): void {
    if (item.children) {
      item.expanded = !item.expanded;
    }
  }

  hasAccess(item: MenuItem): boolean {
    if (!this.currentUser) return false;
    return item.roles.includes(this.currentUser.role);
  }

  hasAnyChildAccess(item: MenuItem): boolean {
    if (!item.children) return false;
    return item.children.some(child => this.hasAccess(child));
  }

  get filteredMenuItems(): MenuItem[] {
    return this.menuItems.filter(item => 
      this.hasAccess(item) || this.hasAnyChildAccess(item)
    );
  }
}
