// Development environment
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api',
  appName: 'Construction Inventory System',
  appVersion: '1.0.0',
  appDescription: 'Material Inventory Management for Construction Sites',
  tokenKey: 'construction_inventory_token',
  userKey: 'construction_inventory_user',
  refreshTokenKey: 'construction_inventory_refresh_token',
  defaultLanguage: 'en',
  enableDebug: true,
  logLevel: 'debug',
  enableAnalytics: false,
  recaptchaSiteKey: '',
  maxUploadSize: 10 * 1024 * 1024, // 10MB
  sessionTimeout: 60, // minutes
  enableNotifications: true,
  features: {
    excelUpload: true,
    reports: true,
    auditLogs: true,
    realtimeUpdates: false
  }
};
