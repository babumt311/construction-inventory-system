import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class RoleGuard implements CanActivate {
  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  canActivate(route: ActivatedRouteSnapshot): boolean {
    const expectedRoles = route.data['roles'] as Array<string>;
    const userRole = this.authService.getCurrentUserValue()?.role;
    
    if (userRole && expectedRoles.includes(userRole)) {
      return true;
    }
    
    // Navigate to unauthorized page or home
    this.router.navigate(['/unauthorized']);
    return false;
  }
}
