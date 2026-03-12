import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

export interface Project {
  id?: string;
  name: string;
  description: string;
  status: 'planning' | 'active' | 'on-hold' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'critical';
  startDate: Date;
  endDate: Date;
  budget: number;
  manager: string;
  teamMembers: string[];
  tags: string[];
}

export interface TeamMember {
  id: string;
  name: string;
  role?: string;
  title?: string;
  email?: string;
}

@Component({
  selector: 'app-project-form',
  templateUrl: './project-form.component.html',
  styleUrls: ['./project-form.component.scss'],
  standalone: false
})
export class ProjectFormComponent implements OnInit {
  @Input() project: Project | null = null;
  @Input() isEditMode: boolean = false;
  @Input() teamMembers: TeamMember[] = [];
  @Input() availableTags: string[] = [];
  @Output() save = new EventEmitter<Project>();
  @Output() cancel = new EventEmitter<void>();

  projectForm!: FormGroup;
  statusOptions = [
    { value: 'planning', label: 'Planning', color: '#9ca3af' },
    { value: 'active', label: 'Active', color: '#3b82f6' },
    { value: 'on-hold', label: 'On Hold', color: '#f59e0b' },
    { value: 'completed', label: 'Completed', color: '#10b981' },
    { value: 'cancelled', label: 'Cancelled', color: '#ef4444' }
  ];

  priorityOptions = [
    { value: 'low', label: 'Low', color: '#10b981' },
    { value: 'medium', label: 'Medium', color: '#f59e0b' },
    { value: 'high', label: 'High', color: '#ef4444' },
    { value: 'critical', label: 'Critical', color: '#dc2626' }
  ];

  constructor(private fb: FormBuilder) {}

  ngOnInit(): void {
    this.initForm();
    
    if (this.project && this.isEditMode) {
      this.projectForm.patchValue({
        ...this.project,
        startDate: this.formatDate(this.project.startDate),
        endDate: this.formatDate(this.project.endDate)
      });
    }
    
    // Initialize with default tags if none provided
    if (this.availableTags.length === 0) {
      this.availableTags = ['Web Development', 'Mobile', 'UI/UX', 'Backend', 'Frontend', 'API', 'Database'];
    }
  }

  private initForm(): void {
    this.projectForm = this.fb.group({
      name: ['', [Validators.required, Validators.minLength(3)]],
      description: ['', [Validators.required, Validators.minLength(10)]],
      status: ['planning', Validators.required],
      priority: ['medium', Validators.required],
      startDate: [this.formatDate(new Date()), Validators.required],
      endDate: ['', Validators.required],
      budget: [0, [Validators.required, Validators.min(0)]],
      manager: ['', Validators.required],
      teamMembers: [[]],
      tags: [[]]
    });
  }

  private formatDate(date: any): string {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = ('0' + (d.getMonth() + 1)).slice(-2);
    const day = ('0' + d.getDate()).slice(-2);
    return `${year}-${month}-${day}`;
  }

  onSubmit(): void {
    if (this.projectForm.valid) {
      const formValue = this.projectForm.value;
      const projectData: Project = {
        ...formValue,
        startDate: new Date(formValue.startDate),
        endDate: new Date(formValue.endDate),
        id: this.project?.id || this.generateId()
      };
      this.save.emit(projectData);
    } else {
      this.markFormGroupTouched(this.projectForm);
    }
  }

  private generateId(): string {
    return 'proj_' + Math.random().toString(36).substr(2, 9);
  }

  private markFormGroupTouched(formGroup: FormGroup): void {
    Object.values(formGroup.controls).forEach(control => {
      control.markAsTouched();
      if (control instanceof FormGroup) {
        this.markFormGroupTouched(control);
      }
    });
  }

  onCancel(): void {
    this.cancel.emit();
  }

  onMemberToggle(memberId: string, event: any): void {
    const teamMembers = this.projectForm.get('teamMembers')?.value || [];
    if (event.target.checked) {
      this.projectForm.get('teamMembers')?.setValue([...teamMembers, memberId]);
    } else {
      this.projectForm.get('teamMembers')?.setValue(
        teamMembers.filter((id: string) => id !== memberId)
      );
    }
  }

  isMemberSelected(memberId: string): boolean {
    const teamMembers = this.projectForm.get('teamMembers')?.value || [];
    return teamMembers.includes(memberId);
  }

  addTag(tag: string): void {
    const tags = this.projectForm.get('tags')?.value || [];
    if (!tags.includes(tag)) {
      this.projectForm.get('tags')?.setValue([...tags, tag]);
    }
  }

  removeTag(tag: string): void {
    const tags = this.projectForm.get('tags')?.value || [];
    this.projectForm.get('tags')?.setValue(tags.filter((t: string) => t !== tag));
  }
}
