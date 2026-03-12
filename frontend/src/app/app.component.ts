import { Component, OnInit } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  title = 'Construction Inventory System';
  showLayout = false;
  isLoading = true;

  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

ngOnInit(): void {

  // Stop loading after first navigation
  this.router.events.pipe(
    filter(event => event instanceof NavigationEnd)
  ).subscribe(() => {
    this.isLoading = false;
    this.updateLayoutVisibility();
  });

  // Update layout when auth state changes
  this.authService.currentUser$.subscribe(() => {
    this.updateLayoutVisibility();
  });

  // Load current user on app start if token exists
  if (this.authService.isAuthenticated()) {
    this.authService.getCurrentUser().subscribe({
      error: () => {
        this.authService.logout();
      }
    });
  }
}


  updateLayoutVisibility(): void {
    const currentRoute = this.router.url;
    this.showLayout = this.authService.isAuthenticated() && 
                      !currentRoute.includes('/login') && 
                      !currentRoute.includes('/unauthorized');
  }
}
