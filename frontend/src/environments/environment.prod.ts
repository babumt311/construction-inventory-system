// Production environment
export const environment = {
  production: true,
  apiUrl: '/api', // Proxy through Nginx
  appName: 'Construction Inventory System',
  appVersion: '1.0.0',
  appDescription: 'Material Inventory Management for Construction Sites',
  tokenKey: 'construction_inventory_token',
  userKey: 'construction_inventory_user',
  refreshTokenKey: 'construction_inventory_refresh_token',
  defaultLanguage: 'en',
  enableDebug: false,
  logLevel: 'error',
  enableAnalytics: true,
  recaptchaSiteKey: 'your-recaptcha-site-key',
  maxUploadSize: 10 * 1024 * 1024, // 10MB
  sessionTimeout: 30, // minutes
  enableNotifications: true,
  features: {
    excelUpload: true,
    reports: true,
    auditLogs: true,
    realtimeUpdates: true
  }
};
