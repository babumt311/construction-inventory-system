import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { HttpErrorResponse } from '@angular/common/http';

// Services and Models
import { UserService } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';
import { User, UserRole } from '../../models/user.model';

@Component({
  selector: 'app-user-management',
  templateUrl: './user-management.component.html',
  styleUrls: ['./user-management.component.scss']
})
export class UserManagementComponent implements OnInit, OnDestroy {

  users: User[] = [];
  filteredUsers: User[] = [];
  isLoading = false;
  errorMessage = '';

  // Filters
  searchTerm = '';
  roleFilter: UserRole | 'ALL' = 'ALL';
  statusFilter: 'ALL' | 'ACTIVE' | 'INACTIVE' = 'ALL';

  // Pagination
  currentPage = 1;
  itemsPerPage = 10;
  totalItems = 0;

  // Current user
  currentUser: User | null = null;

  // Modal Control
  showAddModal = false;

  private destroy$ = new Subject<void>();

  constructor(
    private userService: UserService,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    this.loadUsers();

    this.authService.getCurrentUser()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (user: User) => {
          this.currentUser = user;
        },
        error: (err: any) => {
          console.error('Failed to load current user', err);
          this.currentUser = null;
        }
      });
  }

  loadUsers(): void {
    this.isLoading = true;
    this.userService.getUsers()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (users: User[]) => {
          this.users = users;
          this.filteredUsers = [...users];
          this.totalItems = users.length;
          this.applyFilters();
          this.isLoading = false;
        },
        error: (error: HttpErrorResponse) => {
          this.errorMessage = 'Failed to load users';
          console.error('Error loading users:', error);
          this.isLoading = false;
        }
      });
  }

  createUser(userData: Partial<User>): void {
    this.userService.createUser(userData as any)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (newUser: User) => {
          this.users.push(newUser);
          this.filteredUsers = [...this.users];
          this.applyFilters();
          this.closeAddModal(); // Instantly close modal on success
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to create user';
          console.error('Error creating user:', error);
        }
      });
  }

  updateUser(userId: number, updates: Partial<User>): void {
    this.userService.updateUser(userId, updates)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (updatedUser: User) => {
          const index = this.users.findIndex(u => u.id === userId);
          if (index !== -1) {
            this.users[index] = updatedUser;
            this.filteredUsers = [...this.users];
            this.applyFilters();
          }
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to update user';
          console.error('Error updating user:', error);
        }
      });
  }

  deleteUser(userId: number): void {
    if (!confirm('Are you sure you want to delete this user?')) return;

    this.userService.deleteUser(userId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.users = this.users.filter(u => u.id !== userId);
          this.filteredUsers = [...this.users];
          this.applyFilters();
        },
        error: (error: any) => {
          this.errorMessage = 'Failed to delete user';
          console.error('Error deleting user:', error);
        }
      });
  }

  toggleUserStatus(user: User): void {
    const newStatus = !user.is_active;
    this.updateUser(user.id, { is_active: newStatus });
  }

  applyFilters(): void {
    let filtered = [...this.users];

    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      filtered = filtered.filter(user =>
        user.username.toLowerCase().includes(term) ||
        user.full_name?.toLowerCase().includes(term) ||
        user.email.toLowerCase().includes(term)
      );
    }

    if (this.roleFilter !== 'ALL') {
      filtered = filtered.filter(user => user.role === this.roleFilter);
    }

    if (this.statusFilter !== 'ALL') {
      filtered = filtered.filter(user =>
        this.statusFilter === 'ACTIVE'
          ? user.is_active
          : !user.is_active
      );
    }

    this.filteredUsers = filtered;
    this.totalItems = filtered.length;
    this.currentPage = 1;
  }

  clearFilters(): void {
    this.searchTerm = '';
    this.roleFilter = 'ALL';
    this.statusFilter = 'ALL';
    this.applyFilters();
  }

  get paginatedUsers(): User[] {
    const startIndex = (this.currentPage - 1) * this.itemsPerPage;
    return this.filteredUsers.slice(startIndex, startIndex + this.itemsPerPage);
  }

  changePage(page: number): void {
    this.currentPage = page;
  }

  canEditUser(user: User): boolean {
    if (!this.currentUser) return false;
    if (this.currentUser.role === UserRole.ADMIN) return true;
    if (this.currentUser.id === user.id) return true;
    return false;
  }

  canDeleteUser(user: User): boolean {
    if (!this.currentUser) return false;
    if (this.currentUser.role !== UserRole.ADMIN) return false;
    if (this.currentUser.id === user.id) return false;
    return true;
  }

  getUserStats(): { total: number; active: number; admins: number } {
    return {
      total: this.users.length,
      active: this.users.filter(u => u.is_active).length,
      admins: this.users.filter(u => u.role === UserRole.ADMIN).length
    };
  }

  // --- Modal & Form Controls ---
  openAddModal(): void {
    this.showAddModal = true;
  }

  closeAddModal(): void {
    this.showAddModal = false;
  }

  // Updated to require a password!
  submitNewUser(username: string, email: string, role: string, password?: string): void {
    if (!username || !email || !password) {
      alert('Please fill in the username, email, and a password.');
      return;
    }

    const newUserPayload = {
      username: username,
      email: email,
      password: password,
      role: role as UserRole,
      is_active: true
    };

    this.createUser(newUserPayload); 
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
