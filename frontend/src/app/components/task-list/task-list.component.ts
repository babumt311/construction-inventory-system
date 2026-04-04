import { Component, OnInit, Input } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../services/api.service'; // <-- Added API Service

export interface Task {
  id?: string;
  title: string;
  description: string;
  status: 'todo' | 'in-progress' | 'review' | 'completed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  assignee: { id: string; name: string; avatar?: string; };
  dueDate: Date | string;
  estimatedHours: number;
  actualHours: number;
  tags: string[];
  subtasks: Subtask[];
}

export interface Subtask { id: string; title: string; completed: boolean; }
export interface Project { id: string; name: string; }
export interface Assignee { id: string; name: string; avatar?: string; role?: string; }

@Component({
  selector: 'app-task-list',
  templateUrl: './task-list.component.html',
  styleUrls: ['./task-list.component.scss']
})
export class TaskListComponent implements OnInit {
  projectId: string = '';
  @Input() tasks: Task[] = [];
  @Input() projects: Project[] = [];
  @Input() assignees: Assignee[] = [];
  @Input() showProjectFilter: boolean = true;
  @Input() showAssigneeFilter: boolean = true;
  @Input() showStatusFilter: boolean = true;

  filteredTasks: Task[] = [];
  searchQuery: string = '';
  selectedProject: string = 'all';
  selectedAssignee: string = 'all';
  selectedStatus: string = 'all';
  
  showAddModal = false;
  showEditModal = false;
  selectedTask: Task | null = null;
  
  statusOptions = [
    { value: 'todo', label: 'To Do', color: '#9ca3af' },
    { value: 'in-progress', label: 'In Progress', color: '#3b82f6' },
    { value: 'review', label: 'Review', color: '#f59e0b' },
    { value: 'completed', label: 'Completed', color: '#10b981' }
  ] as const;

  priorityOptions = [
    { value: 'low', label: 'Low', color: '#10b981' },
    { value: 'medium', label: 'Medium', color: '#f59e0b' },
    { value: 'high', label: 'High', color: '#ef4444' },
    { value: 'critical', label: 'Critical', color: '#dc2626' }
  ];

  constructor(
    private route: ActivatedRoute,
    private api: ApiService // <-- Injected API Service
  ) {}

  ngOnInit(): void {
    this.projectId = this.route.snapshot.paramMap.get('id') || 'default';
    this.loadTasks(); 
  }

  // --- REAL BACKEND LOGIC ---
  private loadTasks(): void {
    this.api.get<Task[]>(`projects/${this.projectId}/tasks`).subscribe({
      next: (data) => {
        this.tasks = data;
        this.filterTasks();
      },
      error: (err) => console.error("Error loading tasks", err)
    });
  }

  filterTasks(): void {
    this.filteredTasks = this.tasks.filter(task => {
      const matchesSearch = !this.searchQuery || 
        task.title.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        task.description.toLowerCase().includes(this.searchQuery.toLowerCase());
      
      const matchesStatus = this.selectedStatus === 'all' || task.status === this.selectedStatus;
      return matchesSearch && matchesStatus;
    });
  }

  onAddTask(): void { this.showAddModal = true; }
  closeAddModal(): void { this.showAddModal = false; }

  submitNewTask(title: string, description: string, priority: string, dueDate: string, estHours: string): void {
    if (!title) return alert('Task title is required');

    const newTask: Task = {
      title: title,
      description: description,
      status: 'todo',
      priority: priority as any,
      assignee: { id: '0', name: 'Unassigned', avatar: 'UN' },
      dueDate: dueDate ? new Date(dueDate) : new Date(),
      estimatedHours: parseInt(estHours) || 0,
      actualHours: 0,
      tags: [],
      subtasks: []
    };

    // Send permanently to Backend!
    this.api.post<Task>(`projects/${this.projectId}/tasks`, newTask).subscribe({
      next: (savedTask) => {
        this.tasks.push(savedTask);
        this.filterTasks();
        this.closeAddModal();
      },
      error: (err) => console.error("Error adding task", err)
    });
  }

  onTaskClick(task: Task): void {
    this.selectedTask = { ...task };
    this.showEditModal = true;
  }

  closeEditModal(): void {
    this.showEditModal = false;
    this.selectedTask = null;
  }

  submitEditTask(title: string, description: string, status: string, priority: string): void {
    if (!this.selectedTask || !this.selectedTask.id) return;
    
    const updatedData = { title, description, status, priority };

    this.api.put<any>(`projects/${this.projectId}/tasks/${this.selectedTask.id}`, updatedData).subscribe({
      next: () => {
        const index = this.tasks.findIndex(t => t.id === this.selectedTask!.id);
        if (index > -1) {
          this.tasks[index].title = title;
          this.tasks[index].description = description;
          this.tasks[index].status = status as any;
          this.tasks[index].priority = priority as any;
        }
        this.filterTasks();
        this.closeEditModal();
      },
      error: (err) => console.error("Error updating task", err)
    });
  }

  onDeleteTask(taskId: any): void {
    if (confirm('Are you sure you want to delete this task?')) {
      this.api.delete(`projects/${this.projectId}/tasks/${taskId}`).subscribe({
        next: () => {
          this.tasks = this.tasks.filter(t => t.id !== taskId);
          this.filterTasks();
        },
        error: (err) => console.error("Error deleting task", err)
      });
    }
  }

  // --- Helpers ---
  getFilteredTasksByStatus(status: string): Task[] { return this.filteredTasks.filter(task => task.status === status); }
  getCompletedSubtasksCount(task: Task): number { return task.subtasks ? task.subtasks.filter(st => st.completed).length : 0; }
  getPriorityColor(priority: Task['priority']): string { return this.priorityOptions.find(opt => opt.value === priority)?.color || '#9ca3af'; }
  getProgressPercentage(task: Task): number {
    if (!task.subtasks || task.subtasks.length === 0) return 0;
    const completed = task.subtasks.filter(st => st.completed).length;
    return Math.round((completed / task.subtasks.length) * 100);
  }
  getDaysUntilDue(dueDate: Date | string): number {
    const today = new Date();
    const diffTime = new Date(dueDate).getTime() - today.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  }
  getAssigneeInitials(assignee: any): string {
    if (assignee.avatar) return assignee.avatar;
    if (!assignee.name) return '??';
    const names = assignee.name.split(' ');
    return (names[0].charAt(0) + (names[1]?.charAt(0) || '')).toUpperCase();
  }
}
