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
      timeout: 30000,
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
    const response = await this.api.get('/availability/dashboard');
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
}

export default new DynatraceAPI();
