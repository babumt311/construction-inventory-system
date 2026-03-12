// Staging environment
export const environment = {
  production: false,
  apiUrl: 'https://staging.your-domain.com/api',
  appName: 'Construction Inventory System (Staging)',
  appVersion: '1.0.0',
  appDescription: 'Material Inventory Management for Construction Sites - Staging',
  tokenKey: 'construction_inventory_token_staging',
  userKey: 'construction_inventory_user_staging',
  refreshTokenKey: 'construction_inventory_refresh_token_staging',
  defaultLanguage: 'en',
  enableDebug: true,
  logLevel: 'warn',
  enableAnalytics: false,
  recaptchaSiteKey: 'staging-recaptcha-key',
  maxUploadSize: 10 * 1024 * 1024, // 10MB
  sessionTimeout: 60, // minutes
  enableNotifications: true,
  features: {
    excelUpload: true,
    reports: true,
    auditLogs: true,
    realtimeUpdates: true
  }
};
