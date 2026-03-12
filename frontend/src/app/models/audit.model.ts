export interface AuditLog {
  id: number;
  action: AuditAction;
  resource: AuditResource;
  description: string;
  user: string;
  created_at: string;
}

export enum AuditAction {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
  DELETE = 'DELETE',
  LOGIN = 'LOGIN'
}

export enum AuditResource {
  USER = 'USER',
  PROJECT = 'PROJECT',
  MATERIAL = 'MATERIAL',
  STOCK = 'STOCK',
  PO = 'PO'
}

