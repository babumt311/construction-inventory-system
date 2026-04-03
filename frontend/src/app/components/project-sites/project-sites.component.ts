import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ProjectService } from '../../services/project.service';
import { Site } from '../../models/project.model'; // <-- Using the official model to fix the type errors!

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
  showEditModal = false;
  editingSite: Site | null = null;

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

  // --- ADD MODAL ---
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

    const newSite: Partial<Site> = {
      name: name,
      location: location,
      manager: manager || 'Unassigned',
      status: 'active'
    };

    this.projectService.addProjectSite(this.projectId, newSite).subscribe({
      next: (savedSite) => {
        this.sites.push(savedSite);
        this.closeAddModal();
      },
      error: (err) => console.error("Error saving site to database:", err)
    });
  }

  // --- EDIT MODAL ---
  openEditModal(site: Site): void {
    this.editingSite = { ...site }; 
    this.showEditModal = true;
  }

  closeEditModal(): void {
    this.showEditModal = false;
    this.editingSite = null;
  }

  submitEditSite(name: string, location: string, manager: string, status: string): void {
    if (!this.editingSite || !this.editingSite.id) {
      alert('Error: Cannot edit this site.');
      return;
    }

    const updatedData: Partial<Site> = {
      name: name,
      location: location,
      manager: manager || 'Unassigned',
      status: status
    };

    this.projectService.updateSite(this.editingSite.id, updatedData).subscribe({
      next: (savedSite) => {
        // Find the old site in the array and replace it with the updated one from the DB
        const index = this.sites.findIndex(s => s.id === savedSite.id);
        if (index !== -1) {
          this.sites[index] = savedSite;
        }
        this.closeEditModal();
      },
      error: (err) => console.error("Error updating site:", err)
    });
  }

  // --- DELETE ---
  deleteSite(siteId: any): void {
    if (confirm('Are you sure you want to permanently delete this site from the database?')) {
      this.projectService.deleteProjectSite(siteId).subscribe({
        next: () => {
          this.sites = this.sites.filter(s => s.id !== siteId);
        },
        error: (err) => console.error("Error deleting site from database:", err)
      });
    }
  }
}
