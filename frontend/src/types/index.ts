export interface Metric {
  key: string;
  name: string;
  unit?: string;
  description?: string;
}

export interface ChartType {
  id: string;
  name: string;
  category: 'common' | 'modern';
}

export interface DashboardMetric {
  metric_key: string;
  chart_type: string;
  start_timestamp: number;
  end_timestamp: number;
  resolution: string;
}

export interface TimeRange {
  type: string;
  start_time?: number;
  end_time?: number;
}

export interface MetricData {
  metric_key: string;
  data: Record<string, unknown>;
}

export interface AvailabilityMetrics {
  hosts: Record<string, unknown>;
  applications: Record<string, unknown>;
  services: Record<string, unknown>;
}

export interface TestResult {
  metric_key: string;
  status: 'success' | 'error';
  data_points?: number;
  error?: string;
}
