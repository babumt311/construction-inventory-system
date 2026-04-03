import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

// Third-party
import { JwtModule } from '@auth0/angular-jwt';
import { ToastrModule } from 'ngx-toastr';

// Angular Material
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSortModule } from '@angular/material/sort';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatDialogModule } from '@angular/material/dialog';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatRadioModule } from '@angular/material/radio';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatBadgeModule } from '@angular/material/badge';
import { MatChipsModule } from '@angular/material/chips';
import { MatStepperModule } from '@angular/material/stepper';

// Core
import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';

// Components
import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { HeaderComponent } from './components/layout/header/header.component';
import { SidebarComponent } from './components/layout/sidebar/sidebar.component';
import { MaterialManagementComponent } from './components/material-management/material-management.component';
import { StockEntryComponent } from './components/stock-entry/stock-entry.component';
import { ReportsComponent } from './components/reports/reports.component';
import { ProjectManagementComponent } from './components/project-management/project-management.component';
import { UserManagementComponent } from './components/user-management/user-management.component';
import { ProfileComponent } from './components/profile/profile.component';
import { NotFoundComponent } from './components/not-found/not-found.component';
import { UnauthorizedComponent } from './components/unauthorized/unauthorized.component';
import { PurchaseOrderComponent } from './components/purchase-order/purchase-order.component';
import { StockBalanceComponent } from './components/stock-balance/stock-balance.component';
import { AuditLogsComponent } from './components/audit-logs/audit-logs.component';
import { TaskListComponent } from './components/task-list/task-list.component';
import { ProjectSitesComponent } from './components/project-sites/project-sites.component';
import { ProjectTeamComponent } from './components/project-team/project-team.component';

// Pipes
import { TruncatePipe } from './pipes/truncate.pipe';
import { FilesizePipe } from './pipes/filesize.pipe';

// Services / Guards / Interceptors
import { AuthService } from './services/auth.service';
import { ApiService } from './services/api.service';
import { UserService } from './services/user.service';
import { ProjectService } from './services/project.service';
import { MaterialService } from './services/material.service';
import { StockService } from './services/stock.service';
import { PoService } from './services/po.service';
import { ReportService } from './services/report.service';
import { AuthGuard } from './guards/auth.guard';
import { RoleGuard } from './guards/role.guard';
import { JwtInterceptor } from './interceptors/jwt.interceptor';
import { ErrorInterceptor } from './interceptors/error.interceptor';

// Environment
import { environment } from '../environments/environment';

export function tokenGetter() {
  return localStorage.getItem(environment.tokenKey);
}

@NgModule({
  declarations: [
    AppComponent,
    LoginComponent,
    DashboardComponent,
    HeaderComponent,
    SidebarComponent,
    MaterialManagementComponent,
    StockEntryComponent,
    ReportsComponent,
    ProjectManagementComponent,
    ProjectSitesComponent,
    UserManagementComponent,
    TaskListComponent,
  //  ProfileComponent,
    NotFoundComponent,
  //  UnauthorizedComponent,
    PurchaseOrderComponent,
    StockBalanceComponent,
  //  AuditLogsComponent,
  //  TruncatePipe,
    FilesizePipe
  ],
  imports: [
    BrowserModule,
    BrowserAnimationsModule,
    HttpClientModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    AppRoutingModule,
    ProfileComponent,
    UnauthorizedComponent,
    AuditLogsComponent,
    TruncatePipe,

    // Material
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatCardModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatDialogModule,
    MatProgressBarModule,
    MatSnackBarModule,
    MatTabsModule,
    MatExpansionModule,
    MatTooltipModule,
    MatCheckboxModule,
    MatRadioModule,
    MatProgressSpinnerModule,
    MatBadgeModule,
    MatChipsModule,
    MatStepperModule,

    // Third-party
    JwtModule.forRoot({
      config: {
        tokenGetter,
        allowedDomains: ['localhost:8000', 'localhost'],
        disallowedRoutes: [
          'localhost:8000/api/auth/login',
          'localhost/api/auth/login'
        ]
      }
    }),
    ToastrModule.forRoot({
      positionClass: 'toast-top-right',
      preventDuplicates: true,
      timeOut: 3000,
      closeButton: true,
      progressBar: true
    })
  ],
  providers: [
    AuthService,
    ApiService,
    UserService,
    ProjectService,
    MaterialService,
    StockService,
    PoService,
    ReportService,
    AuthGuard,
    RoleGuard,
    { provide: HTTP_INTERCEPTORS, useClass: JwtInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: ErrorInterceptor, multi: true }
  ],
  bootstrap: [AppComponent]
})
export class AppModule {}
