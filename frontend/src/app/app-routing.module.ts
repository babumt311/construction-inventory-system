import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

// Existing Components
import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { MaterialManagementComponent } from './components/material-management/material-management.component';
import { StockBalanceComponent } from './components/stock-balance/stock-balance.component';
import { PurchaseOrderComponent } from './components/purchase-order/purchase-order.component';

// New Components for Dashboard Links
import { UserManagementComponent } from './components/user-management/user-management.component';
import { ProjectManagementComponent } from './components/project-management/project-management.component';
import { ActivityComponent } from './components/activity/activity.component';

// Guards
import { AuthGuard } from './guards/auth.guard';

const routes: Routes = [
  { 
    path: '', 
    redirectTo: '/login', 
    pathMatch: 'full' 
  },
  { 
    path: 'login', 
    component: LoginComponent 
  },
  { 
    path: 'dashboard', 
    component: DashboardComponent,
    canActivate: [AuthGuard]
  },
  // --- NEW ROUTES ADDED HERE ---
  { 
    path: 'users', 
    component: UserManagementComponent,
    canActivate: [AuthGuard]
  },
  { 
    path: 'projects', 
    component: ProjectManagementComponent,
    canActivate: [AuthGuard]
  },
// { 
// path: 'activity', 
//   component: ActivityComponent,
 //   canActivate: [AuthGuard]
 // },
  // -----------------------------
  { 
    path: 'materials', 
    component: MaterialManagementComponent,
    canActivate: [AuthGuard]
  },
  { 
    path: 'stock', 
    component: StockBalanceComponent,
    canActivate: [AuthGuard]
  },
  { 
    path: 'purchase-orders', 
    component: PurchaseOrderComponent,
    canActivate: [AuthGuard]
  },
  // Wildcard route MUST stay at the very bottom
  { 
    path: '**', 
    redirectTo: '/dashboard' 
  }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
