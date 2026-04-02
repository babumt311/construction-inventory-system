import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'todo' | 'in-progress' | 'review' | 'completed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  assignee: {
    id: string;
    name: string;
    avatar?: string;
  };
  dueDate: Date;
  estimatedHours: number;
  actualHours: number;
  tags: string[];
  subtasks: Subtask[];
}

export interface Subtask {
  id: string;
  title: string;
  completed: boolean;
}

export interface Project {
  id: string;
  name: string;
}

export interface Assignee {
  id: string;
  name: string;
  avatar?: string;
  role?: string;
}

@Component({
  selector: 'app-task-list',
  templateUrl: './task-list.component.html',
  styleUrls: ['./task-list.component.scss'],
  standalone: false
})
export class TaskListComponent implements OnInit {
  @Input() tasks: Task[] = [];
  @Input() projects: Project[] = [];
  @Input() assignees: Assignee[] = [];
  @Input() showProjectFilter: boolean = true;
  @Input() showAssigneeFilter: boolean = true;
  @Input() showStatusFilter: boolean = true;
  @Output() taskSelected = new EventEmitter<Task>();
  @Output() taskStatusChange = new EventEmitter<{taskId: string, newStatus: Task['status']}>();
  @Output() taskDelete = new EventEmitter<string>();
  @Output() addTask = new EventEmitter<void>();

  filteredTasks: Task[] = [];
  searchQuery: string = '';
  selectedProject: string = 'all';
  selectedAssignee: string = 'all';
  selectedStatus: string = 'all';
  
  statusOptions = [
    { value: 'todo', label: 'To Do', color: '#9ca3af', icon: 'radio_button_unchecked' },
    { value: 'in-progress', label: 'In Progress', color: '#3b82f6', icon: 'refresh' },
    { value: 'review', label: 'Review', color: '#f59e0b', icon: 'visibility' },
    { value: 'completed', label: 'Completed', color: '#10b981', icon: 'check_circle' }
  ] as const;

  priorityOptions = [
    { value: 'low', label: 'Low', color: '#10b981' },
    { value: 'medium', label: 'Medium', color: '#f59e0b' },
    { value: 'high', label: 'High', color: '#ef4444' },
    { value: 'critical', label: 'Critical', color: '#dc2626' }
  ];

  constructor() {}

  ngOnInit(): void {
    this.filteredTasks = [...this.tasks];
    this.initializeMockTasks();
  }

  private initializeMockTasks(): void {
    if (this.tasks.length === 0) {
      this.tasks = [
        {
          id: '1',
          title: 'Design Homepage Layout',
          description: 'Create wireframes and mockups for the new homepage',
          status: 'in-progress',
          priority: 'high',
          assignee: { id: '2', name: 'Jane Smith', avatar: 'JS' },
          dueDate: new Date('2024-12-20'),
          estimatedHours: 8,
          actualHours: 6,
          tags: ['Design', 'UI/UX'],
          subtasks: [
            { id: '1-1', title: 'Wireframe creation', completed: true },
            { id: '1-2', title: 'Mockup design', completed: true },
            { id: '1-3', title: 'Client review', completed: false }
          ]
        },
        {
          id: '2',
          title: 'Implement User Authentication',
          description: 'Set up JWT-based authentication system',
          status: 'todo',
          priority: 'critical',
          assignee: { id: '3', name: 'Bob Johnson', avatar: 'BJ' },
          dueDate: new Date('2024-12-15'),
          estimatedHours: 16,
          actualHours: 0,
          tags: ['Backend', 'Security'],
          subtasks: [
            { id: '2-1', title: 'Setup JWT middleware', completed: false },
            { id: '2-2', title: 'Create login endpoint', completed: false },
            { id: '2-3', title: 'Implement refresh tokens', completed: false }
          ]
        },
        {
          id: '3',
          title: 'Write Unit Tests',
          description: 'Cover critical functionality with unit tests',
          status: 'review',
          priority: 'medium',
          assignee: { id: '4', name: 'Alice Brown', avatar: 'AB' },
          dueDate: new Date('2024-12-18'),
          estimatedHours: 12,
          actualHours: 14,
          tags: ['Testing', 'Quality'],
          subtasks: [
            { id: '3-1', title: 'User service tests', completed: true },
            { id: '3-2', title: 'API endpoint tests', completed: true },
            { id: '3-3', title: 'Code review', completed: false }
          ]
        },
        {
          id: '4',
          title: 'Database Optimization',
          description: 'Optimize queries and add indexes',
          status: 'completed',
          priority: 'low',
          assignee: { id: '1', name: 'John Doe', avatar: 'JD' },
          dueDate: new Date('2024-12-10'),
          estimatedHours: 10,
          actualHours: 8,
          tags: ['Database', 'Performance'],
          subtasks: [
            { id: '4-1', title: 'Query analysis', completed: true },
            { id: '4-2', title: 'Index creation', completed: true },
            { id: '4-3', title: 'Performance testing', completed: true }
          ]
        }
      ];
      this.filteredTasks = [...this.tasks];
    }
  }

  filterTasks(): void {
    this.filteredTasks = this.tasks.filter(task => {
      const matchesSearch = !this.searchQuery || 
        task.title.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        task.description.toLowerCase().includes(this.searchQuery.toLowerCase());
      
      const matchesProject = this.selectedProject === 'all' || true; // Implement project filtering if needed
      const matchesAssignee = this.selectedAssignee === 'all' || task.assignee.id === this.selectedAssignee;
      const matchesStatus = this.selectedStatus === 'all' || task.status === this.selectedStatus;
      
      return matchesSearch && matchesProject && matchesAssignee && matchesStatus;
    });
  }

  onSearchChange(): void {
    this.filterTasks();
  }

  onFilterChange(): void {
    this.filterTasks();
  }

  onAddTask(): void {
    this.addTask.emit();
  }

  getStatusColor(status: Task['status']): string {
    const statusOption = this.statusOptions.find(opt => opt.value === status);
    return statusOption?.color || '#9ca3af';
  }

  getStatusLabel(status: Task['status']): string {
    const statusOption = this.statusOptions.find(opt => opt.value === status);
    return statusOption?.label || 'Unknown';
  }

  getPriorityColor(priority: Task['priority']): string {
    const priorityOption = this.priorityOptions.find(opt => opt.value === priority);
    return priorityOption?.color || '#9ca3af';
  }

  getProgressPercentage(task: Task): number {
    if (!task.subtasks || task.subtasks.length === 0) return 0;
    const completed = task.subtasks.filter(st => st.completed).length;
    return Math.round((completed / task.subtasks.length) * 100);
  }

  getDaysUntilDue(dueDate: Date): number {
    const today = new Date();
    const due = new Date(dueDate);
    const diffTime = due.getTime() - today.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  }

  getAssigneeInitials(assignee: any): string {
    if (assignee.avatar) return assignee.avatar;
    if (!assignee.name) return '??';
    const names = assignee.name.split(' ');
    return (names[0].charAt(0) + (names[1]?.charAt(0) || '')).toUpperCase();
  }

  onTaskClick(task: Task): void {
    this.taskSelected.emit(task);
  }

  onStatusChange(taskId: string, newStatus: Task['status']): void {
    this.taskStatusChange.emit({ taskId, newStatus });
    const task = this.tasks.find(t => t.id === taskId);
    if (task) {
      task.status = newStatus;
    }
    this.filterTasks();
  }

  onDeleteTask(taskId: string): void {
    if (confirm('Are you sure you want to delete this task?')) {
      this.taskDelete.emit(taskId);
      this.tasks = this.tasks.filter(t => t.id !== taskId);
      this.filterTasks();
    }
  }

  getCompletedSubtasksCount(task: Task): number {
    if (!task.subtasks) return 0;
    return task.subtasks.filter(st => st.completed).length;
  }

  getFilteredTasksByStatus(status: string): Task[] {
    return this.filteredTasks.filter(task => task.status === status);
  }
}
