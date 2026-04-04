import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../services/api.service'; // <-- Added API Service

export interface TeamMember {
  id?: string;
  name: string;
  email: string;
  role: string;
  status: 'ACTIVE' | 'INACTIVE';
}

@Component({
  selector: 'app-project-team',
  templateUrl: './project-team.component.html',
  styleUrls: ['./project-team.component.scss']
})
export class ProjectTeamComponent implements OnInit {
  projectId: string = '';
  teamMembers: TeamMember[] = [];
  showAddModal = false;

  constructor(
    private route: ActivatedRoute,
    private api: ApiService // <-- Injected API Service
  ) {}

  ngOnInit(): void {
    this.projectId = this.route.snapshot.paramMap.get('id') || '';
    this.loadTeam(); 
  }

  // --- REAL BACKEND LOGIC ---
  private loadTeam(): void {
    this.api.get<TeamMember[]>(`projects/${this.projectId}/team`).subscribe({
      next: (data) => this.teamMembers = data,
      error: (err) => console.error("Error loading team", err)
    });
  }

  openAddModal(): void { this.showAddModal = true; }
  closeAddModal(): void { this.showAddModal = false; }

  submitNewMember(name: string, email: string, role: string): void {
    if (!name || !email) {
      alert('Please provide a Name and Email.');
      return;
    }

    const newMember: TeamMember = {
      name: name,
      email: email,
      role: role || 'Team Member',
      status: 'ACTIVE'
    };

    // Send permanently to Backend!
    this.api.post<TeamMember>(`projects/${this.projectId}/team`, newMember).subscribe({
      next: (savedMember) => {
        this.teamMembers.push(savedMember);
        this.closeAddModal();
      },
      error: (err) => console.error("Error adding member", err)
    });
  }

  removeMember(memberId: any): void {
    if (confirm('Are you sure you want to remove this user from the project?')) {
      this.api.delete(`projects/${this.projectId}/team/${memberId}`).subscribe({
        next: () => {
          this.teamMembers = this.teamMembers.filter(m => m.id !== memberId);
        },
        error: (err) => console.error("Error removing member", err)
      });
    }
  }
}
