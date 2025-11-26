/**
 * Application configuration from environment variables
 */

interface ImportMeta {
  readonly env: {
    readonly VITE_API_URL?: string;
    [key: string]: string | undefined;
  };
}

export const config = {
  // API Configuration
  apiUrl: (import.meta as any).env.VITE_API_URL || '/api',

  // App Configuration
  appName: 'Dynatrace Metrics Dashboard',
  appVersion: '1.0.0',
};

export default config;
