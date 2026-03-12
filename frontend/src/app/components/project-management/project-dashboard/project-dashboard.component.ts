import { Component, OnInit, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

interface ProjectStats {
  totalProjects: number;
  activeProjects: number;
  completedProjects: number;
  delayedProjects: number;
  totalBudget: number;
  spentBudget: number;
}

interface ProjectActivity {
  id: string;
  projectName: string;
  activity: string;
  user: string;
  timestamp: Date;
  type: 'created' | 'updated' | 'completed' | 'delayed';
}

interface ResourceAllocation {
  id: string;
  name: string;
  role: string;
  allocatedHours: number;
  utilizedHours: number;
  projects: string[];
}

interface ProjectStatus {
  status: string;
  count: number;
  color: string;
}

interface BudgetData {
  month: string;
  budget: number;
  spent: number;
}

@Component({
  selector: 'app-project-dashboard',
  templateUrl: './project-dashboard.component.html',
  styleUrls: ['./project-dashboard.component.scss'],
  standalone: false
})
export class ProjectDashboardComponent implements OnInit {
  @Input() stats: ProjectStats = {
    totalProjects: 0,
    activeProjects: 0,
    completedProjects: 0,
    delayedProjects: 0,
    totalBudget: 0,
    spentBudget: 0
  };

  @Input() recentActivities: ProjectActivity[] = [];
  @Input() resourceAllocations: ResourceAllocation[] = [];
  @Input() projectStatusData: ProjectStatus[] = [];
  @Input() budgetUtilizationData: BudgetData[] = [];

  constructor() {}

  ngOnInit(): void {
    this.initializeDefaultData();
  }

  private initializeDefaultData(): void {
    // Only initialize if no data provided
    if (this.recentActivities.length === 0) {
      this.recentActivities = [
        {
          id: '1',
          projectName: 'Website Redesign',
          activity: 'Project milestone completed',
          user: 'Jane Smith',
          timestamp: new Date('2024-12-01T10:30:00'),
          type: 'completed'
        },
        {
          id: '2',
          projectName: 'Mobile App',
          activity: 'New task assigned',
          user: 'John Doe',
          timestamp: new Date('2024-12-01T09:15:00'),
          type: 'updated'
        },
        {
          id: '3',
          projectName: 'API Integration',
          activity: 'Project started',
          user: 'Bob Johnson',
          timestamp: new Date('2024-11-30T14:45:00'),
          type: 'created'
        },
        {
          id: '4',
          projectName: 'Dashboard Revamp',
          activity: 'Deadline extended',
          user: 'Alice Brown',
          timestamp: new Date('2024-11-30T16:20:00'),
          type: 'delayed'
        },
        {
          id: '5',
          projectName: 'Security Audit',
          activity: 'Project completed',
          user: 'Charlie Wilson',
          timestamp: new Date('2024-11-29T11:10:00'),
          type: 'completed'
        }
      ];
    }

    if (this.resourceAllocations.length === 0) {
      this.resourceAllocations = [
        {
          id: '1',
          name: 'John Doe',
          role: 'Project Manager',
          allocatedHours: 160,
          utilizedHours: 145,
          projects: ['Website Redesign', 'Mobile App']
        },
        {
          id: '2',
          name: 'Jane Smith',
          role: 'UI/UX Designer',
          allocatedHours: 120,
          utilizedHours: 110,
          projects: ['Website Redesign', 'Dashboard Revamp']
        },
        {
          id: '3',
          name: 'Bob Johnson',
          role: 'Backend Developer',
          allocatedHours: 180,
          utilizedHours: 165,
          projects: ['Mobile App', 'API Integration']
        },
        {
          id: '4',
          name: 'Alice Brown',
          role: 'Frontend Developer',
          allocatedHours: 140,
          utilizedHours: 120,
          projects: ['Website Redesign', 'Mobile App']
        },
        {
          id: '5',
          name: 'Charlie Wilson',
          role: 'QA Engineer',
          allocatedHours: 100,
          utilizedHours: 90,
          projects: ['API Integration', 'Dashboard Revamp']
        }
      ];
    }

    if (this.projectStatusData.length === 0) {
      this.projectStatusData = [
        { status: 'Planning', count: 2, color: '#9ca3af' },
        { status: 'Active', count: 8, color: '#3b82f6' },
        { status: 'On Hold', count: 1, color: '#f59e0b' },
        { status: 'Completed', count: 3, color: '#10b981' },
        { status: 'Cancelled', count: 0, color: '#ef4444' }
      ];
    }

    if (this.budgetUtilizationData.length === 0) {
      this.budgetUtilizationData = [
        { month: 'Jan', budget: 40000, spent: 32000 },
        { month: 'Feb', budget: 45000, spent: 38000 },
        { month: 'Mar', budget: 50000, spent: 42000 },
        { month: 'Apr', budget: 55000, spent: 48000 },
        { month: 'May', budget: 60000, spent: 52000 },
        { month: 'Jun', budget: 65000, spent: 58000 }
      ];
    }
  }

  getUtilizationPercentage(resource: ResourceAllocation): number {
    if (resource.allocatedHours === 0) return 0;
    return Math.round((resource.utilizedHours / resource.allocatedHours) * 100);
  }

  getBudgetUtilizationPercentage(): number {
    if (this.stats.totalBudget === 0) return 0;
    return Math.round((this.stats.spentBudget / this.stats.totalBudget) * 100);
  }

  getTimeAgo(timestamp: Date): string {
    const now = new Date();
    const diff = now.getTime() - new Date(timestamp).getTime();
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  }

  getActivityIcon(type: ProjectActivity['type']): string {
    const icons = {
      'created': 'add_circle',
      'updated': 'edit',
      'completed': 'check_circle',
      'delayed': 'schedule'
    };
    return icons[type];
  }

  getActivityColor(type: ProjectActivity['type']): string {
    const colors = {
      'created': '#3b82f6',
      'updated': '#f59e0b',
      'completed': '#10b981',
      'delayed': '#ef4444'
    };
    return colors[type];
  }

  getStatusPercentage(status: string): number {
    const total = this.projectStatusData.reduce((sum, item) => sum + item.count, 0);
    if (total === 0) return 0;
    const item = this.projectStatusData.find(item => item.status === status);
    return item ? Math.round((item.count / total) * 100) : 0;
  }

  getResourceInitials(name: string): string {
    if (!name) return '??';
    const names = name.split(' ');
    return (names[0].charAt(0) + (names[1]?.charAt(0) || '')).toUpperCase();
  }
}
