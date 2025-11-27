import axios, { AxiosInstance, AxiosError } from 'axios';
import config from '../config';
import { Metric, MetricData, AvailabilityMetrics, TestResult } from '../types';

class DynatraceAPI {
  private api: AxiosInstance;

  constructor() {
    const baseURL = config.apiUrl.endsWith('/api') ? config.apiUrl : `${config.apiUrl}/api`;

    this.api = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 300000, // 5 minutes timeout for long-running operations like metrics refresh
    });

    // Add response interceptor for better error handling
    this.api.interceptors.response.use(
      response => response,
      error => {
        this.handleError(error);
        return Promise.reject(error);
      }
    );
  }

  private handleError(error: AxiosError) {
    if (error.response) {
      console.error(`API Error: ${error.response.status}`, error.response.data);
    } else if (error.request) {
      console.error('No response from server:', error.request);
    } else {
      console.error('Error:', error.message);
    }
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.api.get('/health');
    return response.data;
  }

  // Validate Dynatrace connection
  async validateConnection(): Promise<{ status: string; tenant_url: string }> {
    const response = await this.api.get('/dynatrace/validate');
    return response.data;
  }

  // Refresh metrics from Dynatrace
  async refreshMetrics(): Promise<{ status: string; metrics_count: number }> {
    const response = await this.api.post('/metrics/refresh');
    return response.data;
  }

  // Get list of available metrics
  async getMetricsList(): Promise<{ metrics: Metric[]; count: number }> {
    const response = await this.api.get('/metrics/list');
    return response.data;
  }

  // Validate if a metric is queryable
  async validateMetric(metricKey: string): Promise<{ metric_key: string; valid: boolean; message: string }> {
    const response = await this.api.get(`/metrics/validate/${encodeURIComponent(metricKey)}`);
    return response.data;
  }

  // Get metric data
  async getMetricData(
    metricKey: string,
    startTimestamp: number,
    endTimestamp: number,
    resolution: string = '1m'
  ): Promise<MetricData> {
    const response = await this.api.post('/metrics/data', {
      metric_key: metricKey,
      start_timestamp: startTimestamp,
      end_timestamp: endTimestamp,
      resolution,
    });
    return response.data;
  }

  // Get availability metrics for main dashboard
  async getAvailabilityDashboard(): Promise<AvailabilityMetrics> {
    // TODO: Change back to '/availability/dashboard' when .env is configured with Dynatrace credentials
    const response = await this.api.get('/test/availability/dashboard');
    return response.data;
  }

  // Test dashboard configuration
  async testDashboard(config: {
    metrics: Array<{
      metric_key: string;
      chart_type: string;
      start_timestamp: number;
      end_timestamp: number;
      resolution: string;
    }>;
    dashboard_name: string;
  }): Promise<{ test_results: TestResult[] }> {
    const response = await this.api.post('/dashboard/test', config);
    return response.data;
  }

  // Calculate time range
  async calculateTimeRange(
    type: string,
    customStart?: number,
    customEnd?: number
  ): Promise<{
    type: string;
    start_timestamp: number;
    end_timestamp: number;
    start_datetime: string;
    end_datetime: string;
  }> {
    const params = new URLSearchParams({ type });
    if (customStart) params.append('custom_start', customStart.toString());
    if (customEnd) params.append('custom_end', customEnd.toString());

    const response = await this.api.get(`/time-range/calculate?${params}`);
    return response.data;
  }

  // Get available chart types
  async getChartTypes(): Promise<{ chart_types: Array<{ id: string; name: string; category: string }> }> {
    const response = await this.api.get('/chart-types');
    return response.data;
  }

  // Dashboard Management Methods

  // Create a new dashboard
  async createDashboard(dashboard: {
    name: string;
    description?: string;
    metrics: Array<{
      metric_key: string;
      chart_type: string;
      start_timestamp: number;
      end_timestamp: number;
      resolution: string;
      dimension?: string;
      filter_entity?: string;
      split_by_dimension?: boolean;
    }>;
  }): Promise<{ id: string; message: string }> {
    const response = await this.api.post('/dashboards', dashboard);
    return response.data;
  }

  // Get list of all saved dashboards
  async listDashboards(): Promise<{ dashboards: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{
      metric_key: string;
      chart_type: string;
      start_timestamp: number;
      end_timestamp: number;
      resolution: string;
      dimension?: string;
      filter_entity?: string;
      split_by_dimension?: boolean;
    }>;
    created_at?: string;
    updated_at?: string;
  }>; count: number }> {
    const response = await this.api.get('/dashboards');
    return response.data;
  }

  // Get a specific dashboard by ID
  async getDashboard(dashboardId: string): Promise<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{
      metric_key: string;
      chart_type: string;
      start_timestamp: number;
      end_timestamp: number;
      resolution: string;
      dimension?: string;
      filter_entity?: string;
      split_by_dimension?: boolean;
    }>;
    created_at?: string;
    updated_at?: string;
  }> {
    const response = await this.api.get(`/dashboards/${encodeURIComponent(dashboardId)}`);
    return response.data;
  }

  // Update a dashboard
  async updateDashboard(dashboardId: string, dashboard: {
    name: string;
    description?: string;
    metrics: Array<{
      metric_key: string;
      chart_type: string;
      start_timestamp: number;
      end_timestamp: number;
      resolution: string;
      dimension?: string;
      filter_entity?: string;
      split_by_dimension?: boolean;
    }>;
  }): Promise<{ id: string; message: string }> {
    const response = await this.api.put(`/dashboards/${encodeURIComponent(dashboardId)}`, dashboard);
    return response.data;
  }

  // Delete a dashboard
  async deleteDashboard(dashboardId: string): Promise<{ message: string }> {
    const response = await this.api.delete(`/dashboards/${encodeURIComponent(dashboardId)}`);
    return response.data;
  }

  // Export dashboard as JSON
  async exportDashboard(dashboardId: string): Promise<{ data: string; filename: string }> {
    const response = await this.api.get(`/dashboards/${encodeURIComponent(dashboardId)}/export`);
    return response.data;
  }

  // Import dashboard from JSON
  async importDashboard(data: string, overrideId: boolean = true): Promise<{ id: string; message: string }> {
    const response = await this.api.post('/dashboards/import', {
      data,
      override_id: overrideId
    });
    return response.data;
  }

  // Get dimensions for a specific metric
  async getMetricDimensions(
    metricKey: string,
    startTimestamp: number,
    endTimestamp: number,
    resolution: string = '1m'
  ): Promise<{ metric_key: string; dimensions: Array<{ name: string; values: string[] }>; entity_names: string[] }> {
    const response = await this.api.post(`/metrics/${encodeURIComponent(metricKey)}/dimensions`, {}, {
      params: {
        start_timestamp: startTimestamp,
        end_timestamp: endTimestamp,
        resolution
      }
    });
    return response.data;
  }
}

export default new DynatraceAPI();
