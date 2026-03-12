import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

// Services and Models
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { User, ChangePasswordRequest } from '../../models/user.model';

@Component({
  selector: 'app-profile',
  templateUrl: './profile.component.html',
  styleUrls: ['./profile.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule]
})
export class ProfileComponent implements OnInit, OnDestroy {
  user: User | null = null;
  isLoading = false;
  isEditing = false;
  isChangingPassword = false;
  successMessage = '';
  errorMessage = '';
  
  profileForm: FormGroup;
  passwordForm: FormGroup;
  
  private destroy$ = new Subject<void>();

  constructor(
    private authService: AuthService,
    private userService: UserService,
    private fb: FormBuilder
  ) {
    this.profileForm = this.fb.group({
      username: ['', [Validators.required]],
      full_name: ['', [Validators.required]],
      email: ['', [Validators.required, Validators.email]],
      role: ['']
    });

    this.passwordForm = this.fb.group({
      currentPassword: ['', [Validators.required]],
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', [Validators.required]]
    }, { validators: this.passwordMatchValidator });
  }

  ngOnInit(): void {
    this.loadUserProfile();
  }

  loadUserProfile(): void {
    this.isLoading = true;
    this.authService.getCurrentUser()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (user) => {
          this.user = user;
          this.profileForm.patchValue({
            username: user.username,
            full_name: user.full_name || '',
            email: user.email,
            role: user.role
          });
          this.isLoading = false;
        },
        error: (error) => {
          this.errorMessage = 'Failed to load profile';
          console.error('Error loading profile:', error);
          this.isLoading = false;
        }
      });
  }

  updateProfile(): void {
    if (this.profileForm.invalid || !this.user) return;

    this.isLoading = true;
    this.userService.updateUser(this.user.id, this.profileForm.value)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (updatedUser) => {
          this.user = updatedUser;
          this.authService.getCurrentUser()
            .pipe(takeUntil(this.destroy$))
            .subscribe({
              next: () => {
                this.isEditing = false;
                this.successMessage = 'Profile updated successfully';
                this.isLoading = false;
                setTimeout(() => this.successMessage = '', 3000);
              },
              error: () => {
                this.isLoading = false;
              }
            });
        },
        error: (error) => {
          this.errorMessage = 'Failed to update profile';
          console.error('Error updating profile:', error);
          this.isLoading = false;
        }
      });
  }

  changePassword(): void {
    if (this.passwordForm.invalid || !this.user) return;

    this.isLoading = true;
    const { currentPassword, newPassword } = this.passwordForm.value;
    
    const request: ChangePasswordRequest = {
      old_password: currentPassword,
      new_password: newPassword
    };
    
    this.authService.changePassword(request)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.isChangingPassword = false;
          this.passwordForm.reset();
          this.successMessage = 'Password changed successfully';
          this.isLoading = false;
          setTimeout(() => this.successMessage = '', 3000);
        },
        error: (error) => {
          this.errorMessage = error.message || 'Failed to change password';
          console.error('Error changing password:', error);
          this.isLoading = false;
        }
      });
  }

  uploadAvatar(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) return;

    // TODO: Avatar upload not yet implemented in UserService
    console.warn('Avatar upload functionality is not yet implemented');
    this.errorMessage = 'Avatar upload functionality is not yet implemented';
  }

  cancelEdit(): void {
    this.isEditing = false;
    this.profileForm.patchValue({
      username: this.user?.username,
      full_name: this.user?.full_name || '',
      email: this.user?.email,
      role: this.user?.role
    });
  }

  cancelPasswordChange(): void {
    this.isChangingPassword = false;
    this.passwordForm.reset();
  }

  private passwordMatchValidator(g: FormGroup): { [key: string]: boolean } | null {
    const newPassword = g.get('newPassword')?.value;
    const confirmPassword = g.get('confirmPassword')?.value;
    
    if (newPassword !== confirmPassword) {
      return { passwordMismatch: true };
    }
    return null;
  }

  getAvatarInitials(): string {
    if (!this.user?.full_name) return '?';
    return this.user.full_name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  }

  getAvatarColor(): string {
    if (!this.user?.id) return '#007bff';
    
    const colors = [
      '#007bff', '#6f42c1', '#e83e8c', '#fd7e14',
      '#20c997', '#17a2b8', '#ffc107', '#dc3545'
    ];
    
    const hash = String(this.user.id).split('').reduce((acc, char) => {
      return char.charCodeAt(0) + ((acc << 5) - acc);
    }, 0);
    
    return colors[Math.abs(hash) % colors.length];
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}