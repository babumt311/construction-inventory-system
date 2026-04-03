import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ProjectService } from '../../services/project.service'; // <-- ADDED THIS

export interface Site {
  id?: string | number; // Optional because the DB generates it!
  name: string;
  location: string;
  manager: string;
  status: string;
}

@Component({
  selector: 'app-project-sites',
  templateUrl: './project-sites.component.html',
  styleUrls: ['./project-sites.component.scss']
})
export class ProjectSitesComponent implements OnInit {
  projectId: string = '';
  sites: Site[] = [];
  isLoading = false;
  
  // Modal Controls
  showAddModal = false;

  // We injected the ProjectService here
  constructor(
    private route: ActivatedRoute,
    private projectService: ProjectService
  ) {}

  ngOnInit(): void {
    this.projectId = this.route.snapshot.paramMap.get('id') || '';
    this.loadRealSites();
  }

  // --- REAL DATABASE LOGIC ---
  loadRealSites(): void {
    this.isLoading = true;
    this.projectService.getProjectSites(this.projectId).subscribe({
      next: (dbSites) => {
        this.sites = dbSites;
        this.isLoading = false;
      },
      error: (err) => {
        console.error("Error loading sites from PostgreSQL:", err);
        this.isLoading = false;
      }
    });
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

    const newSite = {
      name: name,
      location: location,
      manager: manager || 'Unassigned',
      status: 'active'
    };

    // Send it to Python to save permanently!
    this.projectService.addProjectSite(this.projectId, newSite).subscribe({
      next: (savedSite) => {
        // Push the newly saved DB site (which now has a real ID) into our array
        this.sites.push(savedSite);
        this.closeAddModal();
      },
      error: (err) => console.error("Error saving site to database:", err)
    });
  }

  deleteSite(siteId: any): void {
    if (confirm('Are you sure you want to permanently delete this site from the database?')) {
      this.projectService.deleteProjectSite(siteId).subscribe({
        next: () => {
          // Remove it from the screen once Python confirms it's deleted
          this.sites = this.sites.filter(s => s.id !== siteId);
        },
        error: (err) => console.error("Error deleting site from database:", err)
      });
    }
  }
}
