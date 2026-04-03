import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

export interface TeamMember {
  id: string;
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

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.projectId = this.route.snapshot.paramMap.get('id') || '';
    this.loadTeam(); // Swapped to our new LocalStorage loader
  }

  // --- LOCAL STORAGE LOGIC ---
  private loadTeam(): void {
    const savedData = localStorage.getItem(`project_team_${this.projectId}`);
    
    if (savedData) {
      // Load saved team from browser storage
      this.teamMembers = JSON.parse(savedData);
    } else {
      // If empty, load mock data and save it
      this.loadMockTeam();
      this.saveTeam();
    }
  }

  private saveTeam(): void {
    // Save the array permanently to the browser
    localStorage.setItem(`project_team_${this.projectId}`, JSON.stringify(this.teamMembers));
  }

  private loadMockTeam(): void {
    this.teamMembers = [
      { id: '1', name: 'John Doe', email: 'john@construction.com', role: 'Project Manager', status: 'ACTIVE' },
      { id: '2', name: 'Jane Smith', email: 'jane@construction.com', role: 'Site Engineer', status: 'ACTIVE' },
      { id: '3', name: 'Mike Johnson', email: 'mike@construction.com', role: 'Safety Officer', status: 'INACTIVE' }
    ];
  }

  // --- MODAL & ACTIONS ---
  openAddModal(): void {
    this.showAddModal = true;
  }

  closeAddModal(): void {
    this.showAddModal = false;
  }

  submitNewMember(name: string, email: string, role: string): void {
    if (!name || !email) {
      alert('Please provide a Name and Email.');
      return;
    }

    const newMember: TeamMember = {
      id: Math.random().toString(),
      name: name,
      email: email,
      role: role || 'Team Member',
      status: 'ACTIVE'
    };

    this.teamMembers.push(newMember);
    this.saveTeam(); // ADDED: Save immediately!
    this.closeAddModal();
  }

  removeMember(memberId: string): void {
    if (confirm('Are you sure you want to remove this user from the project?')) {
      this.teamMembers = this.teamMembers.filter(m => m.id !== memberId);
      this.saveTeam(); // ADDED: Save immediately!
    }
  }
}
