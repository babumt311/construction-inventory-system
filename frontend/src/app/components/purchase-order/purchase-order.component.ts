import { Component, OnInit, ViewChild, TemplateRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { MatDialog } from '@angular/material/dialog';
import { PoService } from '../../services/po.service';
import { ProjectService } from '../../services/project.service';
import { MaterialService } from '../../services/material.service';
import { POEntry, POEntryCreateRequest } from '../../models/po.model';
import { Project } from '../../models/project.model';
import { Material } from '../../models/material.model';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-purchase-order',
  templateUrl: './purchase-order.component.html',
  styleUrls: ['./purchase-order.component.scss']
})
export class PurchaseOrderComponent implements OnInit {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;
  @ViewChild('poDialog') poDialog!: TemplateRef<any>;
  @ViewChild('supplierDialog') supplierDialog!: TemplateRef<any>;

  // Data
  projects: Project[] = [];
  materials: Material[] = [];
  poEntries: POEntry[] = [];
  suppliers: string[] = [];
  selectedPO: POEntry | null = null;
  
  // Forms
  poForm: FormGroup;
  filterForm: FormGroup;
  supplierForm: FormGroup;
  
  // Table
  displayedColumns: string[] = ['po_date', 'invoice_no', 'project', 'material', 'quantity', 'unit_price', 'total_cost', 'supplier', 'actions'];
  dataSource = new MatTableDataSource<POEntry>();
  
  // UI State
  loading = false;
  isEditing = false;
  currentPOId?: number;
  selectedProjectId?: number;
  selectedMaterialId?: number;
  viewMode: 'all' | 'pending' | 'received' = 'all';

  constructor(
    private fb: FormBuilder,
    private poService: PoService,
    private projectService: ProjectService,
    private materialService: MaterialService,
    public dialog: MatDialog, //changed now to public
    private toastr: ToastrService
  ) {
    this.poForm = this.fb.group({
      project_id: ['', Validators.required],
      material_id: ['', Validators.required],
      supplier_name: ['', [Validators.required, Validators.minLength(2)]],
      invoice_no: ['', [Validators.required, Validators.minLength(2)]],
      quantity: ['', [Validators.required, Validators.min(0.01)]],
      unit_price: ['', [Validators.required, Validators.min(0)]],
      total_cost: [{ value: '', disabled: true }],
      po_date: [new Date()],
      delivery_date: [''],
      remarks: ['']
    });

    this.filterForm = this.fb.group({
      project_id: [''],
      supplier_name: [''],
      start_date: [''],
      end_date: [''],
      status: ['all']
    });

    this.supplierForm = this.fb.group({
      name: ['', Validators.required],
      contact_person: [''],
      phone: [''],
      email: ['', Validators.email],
      address: [''],
      tax_id: ['']
    });

    // Calculate total cost when quantity or unit price changes
    this.poForm.get('quantity')?.valueChanges.subscribe(() => this.calculateTotal());
    this.poForm.get('unit_price')?.valueChanges.subscribe(() => this.calculateTotal());
  }

  ngOnInit(): void {
    this.loadProjects();
    this.loadMaterials();
    this.loadPOEntries();
    this.loadSuppliers();
  }

  loadProjects(): void {
    this.projectService.getProjects({ status: 'active' }).subscribe({
      next: (projects) => {
        this.projects = projects;
      },
      error: (error) => {
        this.toastr.error('Failed to load projects', 'Error');
      }
    });
  }

  loadMaterials(): void {
    this.materialService.getMaterials().subscribe({
      next: (materials) => {
        this.materials = materials;
      },
      error: (error) => {
        this.toastr.error('Failed to load materials', 'Error');
      }
    });
  }

  loadPOEntries(params?: any): void {
    this.loading = true;
    this.poService.getPOEntries(params).subscribe({
      next: (entries) => {
        this.poEntries = entries;
        this.dataSource.data = entries;
        this.dataSource.paginator = this.paginator;
        this.dataSource.sort = this.sort;
        this.loading = false;
      },
      error: (error) => {
        this.toastr.error('Failed to load purchase orders', 'Error');
        this.loading = false;
      }
    });
  }

  loadSuppliers(): void {
    this.poService.getSuppliers().subscribe({
      next: (suppliers) => {
        this.suppliers = suppliers.map(s => s.supplier_name).filter((v, i, a) => a.indexOf(v) === i);
      },
      error: (error) => {
        this.toastr.error('Failed to load suppliers', 'Error');
      }
    });
  }

  calculateTotal(): void {
    const quantity = parseFloat(this.poForm.get('quantity')?.value) || 0;
    const unitPrice = parseFloat(this.poForm.get('unit_price')?.value) || 0;
    const total = quantity * unitPrice;
    
    this.poForm.patchValue({ total_cost: total.toFixed(2) }, { emitEvent: false });
  }

  createPO(): void {
    if (this.poForm.invalid) {
      this.markFormGroupTouched(this.poForm);
      return;
    }

    const poData: POEntryCreateRequest = {
      ...this.poForm.value,
      total_cost: parseFloat(this.poForm.get('total_cost')?.value)
    };

    this.loading = true;
    this.poService.createPOEntry(poData).subscribe({
      next: () => {
        this.toastr.success('Purchase order created successfully', 'Success');
        this.loadPOEntries();
        this.resetForm();
        this.dialog.closeAll();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to create purchase order', 'Error');
        this.loading = false;
      }
    });
  }

  updatePO(): void {
    if (this.poForm.invalid || !this.currentPOId) {
      return;
    }

    const poData = {
      ...this.poForm.value,
      total_cost: parseFloat(this.poForm.get('total_cost')?.value)
    };

    this.loading = true;
    this.poService.updatePOEntry(this.currentPOId, poData).subscribe({
      next: () => {
        this.toastr.success('Purchase order updated successfully', 'Success');
        this.loadPOEntries();
        this.resetForm();
        this.dialog.closeAll();
      },
      error: (error) => {
        this.toastr.error(error.message || 'Failed to update purchase order', 'Error');
        this.loading = false;
      }
    });
  }

  deletePO(id: number): void {
    if (confirm('Are you sure you want to delete this purchase order?')) {
      this.poService.deletePOEntry(id).subscribe({
        next: () => {
          this.toastr.success('Purchase order deleted successfully', 'Success');
          this.loadPOEntries();
        },
        error: (error) => {
          this.toastr.error(error.message || 'Failed to delete purchase order', 'Error');
        }
      });
    }
  }

  editPO(po: POEntry): void {
    this.isEditing = true;
    this.currentPOId = po.id;
    this.selectedPO = po;
    
    this.poForm.patchValue({
      project_id: po.project_id,
      material_id: po.material_id,
      supplier_name: po.supplier_name,
      invoice_no: po.invoice_no,
      quantity: po.quantity,
      unit_price: po.unit_price,
      total_cost: po.total_cost,
      po_date: new Date(po.po_date),
      delivery_date: po.delivery_date ? new Date(po.delivery_date) : null,
      remarks: po.remarks
    });

    this.openPODialog();
  }

  viewPODetails(po: POEntry): void {
    this.selectedPO = po;
    this.dialog.open(this.poDialog, {
      width: '700px',
      data: { po }
    });
  }

  openPODialog(): void {
    this.dialog.open(this.poDialog, {
      width: '800px',
      data: { isEditing: this.isEditing }
    });
  }

  openSupplierDialog(): void {
    this.supplierForm.reset();
    this.dialog.open(this.supplierDialog, {
      width: '500px'
    });
  }

  addSupplier(): void {
    if (this.supplierForm.invalid) {
      this.markFormGroupTouched(this.supplierForm);
      return;
    }

    const supplierData = this.supplierForm.value;
    // Here you would typically call a supplier service
    this.toastr.success('Supplier added successfully', 'Success');
    this.dialog.closeAll();
  }

  applyFilters(): void {
    const filters = this.filterForm.value;
    const params: any = {};
    
    if (filters.project_id) params.project_id = filters.project_id;
    if (filters.supplier_name) params.supplier_name = filters.supplier_name;
    if (filters.start_date) params.start_date = filters.start_date.toISOString().split('T')[0];
    if (filters.end_date) params.end_date = filters.end_date.toISOString().split('T')[0];
    if (filters.status !== 'all') params.status = filters.status;
    
    this.loadPOEntries(params);
  }

  clearFilters(): void {
    this.filterForm.reset({ status: 'all' });
    this.loadPOEntries();
  }

  getTotalCost(): number {
    return this.poEntries.reduce((sum, po) => sum + po.total_cost, 0);
  }

  getPendingDeliveryCount(): number {
  return this.poEntries ? this.poEntries.filter(po => !po.delivery_date).length : 0;
  }

  getMaterialName(materialId: number): string {
    const material = this.materials.find(m => m.id === materialId);
    return material ? material.name : 'Unknown';
  }

  getProjectName(projectId: number): string {
    const project = this.projects.find(p => p.id === projectId);
    return project ? project.name : 'Unknown';
  }

  getDeliveryStatus(po: POEntry): string {
    if (!po.delivery_date) return 'pending';
    const deliveryDate = new Date(po.delivery_date);
    const today = new Date();
    return deliveryDate <= today ? 'received' : 'scheduled';
  }

  markAsReceived(poId: number): void {
    if (confirm('Mark this purchase order as received?')) {
      this.poService.updatePOEntry(poId, { 
        delivery_date: new Date()
      }).subscribe({
        next: () => {
          this.toastr.success('Purchase order marked as received', 'Success');
          this.loadPOEntries();
        },
        error: (error) => {
          this.toastr.error(error.message || 'Failed to update status', 'Error');
        }
      });
    }
  }

  resetForm(): void {
    this.poForm.reset({
      project_id: '',
      material_id: '',
      supplier_name: '',
      invoice_no: '',
      quantity: '',
      unit_price: '',
      total_cost: '',
      po_date: new Date(),
      delivery_date: '',
      remarks: ''
    });
    this.poForm.enable();
    this.isEditing = false;
    this.currentPOId = undefined;
    this.selectedPO = null;
    this.loading = false;
  }

  private markFormGroupTouched(formGroup: FormGroup): void {
    Object.values(formGroup.controls).forEach(control => {
      control.markAsTouched();
      if (control instanceof FormGroup) {
        this.markFormGroupTouched(control);
      }
    });
  }

  onMaterialChange(materialId: number): void {
    const material = this.materials.find(m => m.id === materialId);
    if (material && material.standard_cost) {
      this.poForm.patchValue({ unit_price: material.standard_cost });
    }
  }

  exportPOReport(): void {
    const data = this.dataSource.data;
    if (data.length === 0) {
      this.toastr.warning('No data to export', 'Warning');
      return;
    }

    // Create CSV content
    const headers = ['Date', 'Invoice No', 'Project', 'Material', 'Quantity', 'Unit Price', 'Total Cost', 'Supplier', 'Status'];
    const rows = data.map(item => [
      new Date(item.po_date).toLocaleDateString(),
      item.invoice_no,
      this.getProjectName(item.project_id),
      this.getMaterialName(item.material_id),
      item.quantity,
      item.unit_price,
      item.total_cost,
      item.supplier_name,
      this.getDeliveryStatus(item)
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `purchase-orders-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    
    this.toastr.success('Purchase orders exported', 'Success');
  }
}
