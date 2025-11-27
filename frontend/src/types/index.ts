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
  availability: Record<string, unknown>;
  cpu_usage: Record<string, unknown>;
  memory_usage: Record<string, unknown>;
  network_connectivity: Record<string, unknown>;
}

export interface TestResult {
  metric_key: string;
  status: 'success' | 'error';
  data_points?: number;
  error?: string;
}

export interface DimensionInfo {
  name: string;
  values: string[];
}

export interface SavedDashboard {
  id?: string;
  name: string;
  description?: string;
  metrics: DashboardMetric[];
  created_at?: string;
  updated_at?: string;
}
