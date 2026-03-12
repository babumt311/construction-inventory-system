import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

// Components
import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { MaterialManagementComponent } from './components/material-management/material-management.component';
import { StockBalanceComponent } from './components/stock-balance/stock-balance.component';
import { PurchaseOrderComponent } from './components/purchase-order/purchase-order.component';
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

