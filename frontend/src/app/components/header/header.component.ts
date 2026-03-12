import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss']
})
export class HeaderComponent implements OnInit {
  currentUser: any = null;

  constructor(
    private router: Router,
    private authService: AuthService
  ) { }

  ngOnInit(): void {
    // Get current user from AuthService
    this.currentUser = this.authService.getCurrentUserValue();
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  get username(): string {
    return this.currentUser?.username || this.currentUser?.email || 'User';
  }
}

