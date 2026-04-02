import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

export interface Site {
  id: string;
  name: string;
  location: string;
  manager: string;
  status: 'ACTIVE' | 'INACTIVE' | 'COMPLETED';
}

@Component({
  selector: 'app-project-sites',
  templateUrl: './project-sites.component.html',
  styleUrls: ['./project-sites.component.scss']
})
export class ProjectSitesComponent implements OnInit {
  projectId: string = '';
  sites: Site[] = [];
  showAddModal = false;

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    // Grabs the project ID from the URL (e.g., /projects/123/sites)
    this.projectId = this.route.snapshot.paramMap.get('id') || '';
    this.loadMockSites();
  }

  loadMockSites(): void {
    // Fake data so you can see it working immediately
    this.sites = [
      { id: '1', name: 'Main Foundation', location: 'North Wing', manager: 'John Doe', status: 'ACTIVE' },
      { id: '2', name: 'Electrical Hub', location: 'East Wing', manager: 'Jane Smith', status: 'INACTIVE' }
    ];
  }

  openAddModal(): void {
    this.showAddModal = true;
  }

  closeAddModal(): void {
    this.showAddModal = false;
  }

  submitNewSite(name: string, location: string, manager: string): void {
    if (!name || !location) {
      alert('Please provide a Site Name and Location.');
      return;
    }

    const newSite: Site = {
      id: Math.random().toString(),
      name: name,
      location: location,
      manager: manager || 'Unassigned',
      status: 'ACTIVE'
    };

    this.sites.push(newSite);
    this.closeAddModal();
  }

  deleteSite(siteId: string): void {
    if (confirm('Are you sure you want to delete this site?')) {
      this.sites = this.sites.filter(s => s.id !== siteId);
    }
  }
}
