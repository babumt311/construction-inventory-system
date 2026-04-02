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
  
  // Modal Controls
  showAddModal = false;
  showEditModal = false;
  editingSite: Site | null = null;

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.projectId = this.route.snapshot.paramMap.get('id') || '';
    this.loadMockSites();
  }

  loadMockSites(): void {
    this.sites = [
      { id: '1', name: 'Main Foundation', location: 'North Wing', manager: 'John Doe', status: 'ACTIVE' },
      { id: '2', name: 'Electrical Hub', location: 'East Wing', manager: 'Jane Smith', status: 'INACTIVE' }
    ];
  }

  // --- Add Modal Controls ---
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

  // --- Edit Modal Controls ---
  openEditModal(site: Site): void {
    this.editingSite = { ...site }; // Clone it so we don't accidentally edit the table before hitting 'Save'
    this.showEditModal = true;
  }

  closeEditModal(): void {
    this.showEditModal = false;
    this.editingSite = null;
  }

  submitEditSite(name: string, location: string, manager: string, status: string): void {
    if (!this.editingSite || !name || !location) {
      alert('Please provide a Site Name and Location.');
      return;
    }

    const index = this.sites.findIndex(s => s.id === this.editingSite!.id);
    if (index !== -1) {
      this.sites[index] = {
        ...this.editingSite,
        name: name,
        location: location,
        manager: manager || 'Unassigned',
        status: status as 'ACTIVE' | 'INACTIVE' | 'COMPLETED'
      };
    }

    this.closeEditModal();
  }

  deleteSite(siteId: string): void {
    if (confirm('Are you sure you want to delete this site?')) {
      this.sites = this.sites.filter(s => s.id !== siteId);
    }
  }
}
