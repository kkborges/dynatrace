/**
 * Application configuration from environment variables
 */

export const config = {
  // API Configuration
  apiUrl: import.meta.env.VITE_API_URL || '/api',

  // App Configuration
  appName: 'Dynatrace Metrics Dashboard',
  appVersion: '1.0.0',
};

export default config;
