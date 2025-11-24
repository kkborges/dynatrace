import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import './MainDashboard.css';

interface HostMetrics {
  availability: Record<string, unknown>;
  cpu_usage: Record<string, unknown>;
  memory_usage: Record<string, unknown>;
  network_connectivity: Record<string, unknown>;
}

export const MainDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<HostMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTime, setRefreshTime] = useState<string>(new Date().toLocaleTimeString());

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await DynatraceAPI.getAvailabilityDashboard();
      console.log('Dashboard metrics received:', data);
      setMetrics(data);
      setRefreshTime(new Date().toLocaleTimeString());
    } catch (err) {
      setError('Failed to load dashboard metrics. Please try again.');
      console.error('Error loading metrics:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const getMetricValue = (data: Record<string, unknown>): string => {
    if (!data) return 'N/A';

    console.log('Processing metric data:', data);

    // Handle the Dynatrace API response structure
    const result = (data.result || []) as Array<{
      data?: Array<{
        values?: Array<(number | null)[]>;
        points?: Array<{ value: number; timestamp: number }>;
      }>;
      values?: Array<(number | null)[]>;
      points?: Array<{ value: number; timestamp: number }>;
    }>;

    if (result.length === 0) {
      return 'N/A';
    }

    const resultItem = result[0];

    // Try to get data from nested structure first (result[0].data[0].values)
    if (resultItem.data && Array.isArray(resultItem.data) && resultItem.data.length > 0) {
      const dataItem = resultItem.data[0];

      // Try new structure (data[].points)
      if (dataItem.points && Array.isArray(dataItem.points) && dataItem.points.length > 0) {
        const lastPoint = dataItem.points[dataItem.points.length - 1];
        if (lastPoint && lastPoint.value !== null) {
          return (lastPoint.value as number).toFixed(2);
        }
      }

      // Try old structure (data[].values)
      if (dataItem.values && Array.isArray(dataItem.values) && dataItem.values.length > 0) {
        const lastValue = dataItem.values[dataItem.values.length - 1];
        if (lastValue && Array.isArray(lastValue) && lastValue[0] !== null) {
          return (lastValue[0] as number).toFixed(2);
        }
      }
    }

    // Try direct structure (result[0].values or result[0].points) if nested not found
    if (resultItem.points && Array.isArray(resultItem.points) && resultItem.points.length > 0) {
      const lastPoint = resultItem.points[resultItem.points.length - 1];
      if (lastPoint && lastPoint.value !== null) {
        return (lastPoint.value as number).toFixed(2);
      }
    }

    if (resultItem.values && Array.isArray(resultItem.values) && resultItem.values.length > 0) {
      const lastValue = resultItem.values[resultItem.values.length - 1];
      if (lastValue && Array.isArray(lastValue) && lastValue[0] !== null) {
        return (lastValue[0] as number).toFixed(2);
      }
    }

    return 'N/A';
  };

  const getStatusBadge = (value: string): string => {
    if (value === 'N/A') return 'unknown';
    const numValue = parseFloat(value);
    if (numValue >= 95) return 'healthy';
    if (numValue >= 80) return 'warning';
    return 'critical';
  };

  if (isLoading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading availability metrics...</p>
      </div>
    );
  }

  return (
    <div className="main-dashboard">
      <div className="dashboard-header">
        <h2>Host Metrics Dashboard</h2>
        <div className="dashboard-controls">
          <button onClick={loadMetrics} className="refresh-button">
            🔄 Refresh
          </button>
          <span className="last-refresh">Last refresh: {refreshTime}</span>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          {error}
          <button onClick={loadMetrics} className="retry-button">
            Retry
          </button>
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <h3>Host Availability</h3>
            {metrics && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(metrics.availability))}`}>
                {getStatusBadge(getMetricValue(metrics.availability))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {metrics ? getMetricValue(metrics.availability) : 'N/A'}%
          </div>
          <div className="metric-description">
            Percentage of hosts currently available
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <h3>CPU Usage</h3>
            {metrics && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(metrics.cpu_usage))}`}>
                {getStatusBadge(getMetricValue(metrics.cpu_usage))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {metrics ? getMetricValue(metrics.cpu_usage) : 'N/A'}%
          </div>
          <div className="metric-description">
            Average CPU usage across all hosts
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <h3>Memory Usage</h3>
            {metrics && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(metrics.memory_usage))}`}>
                {getStatusBadge(getMetricValue(metrics.memory_usage))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {metrics ? getMetricValue(metrics.memory_usage) : 'N/A'}%
          </div>
          <div className="metric-description">
            Average memory usage across all hosts
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <h3>Network Connectivity</h3>
            {metrics && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(metrics.network_connectivity))}`}>
                {getStatusBadge(getMetricValue(metrics.network_connectivity))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {metrics ? getMetricValue(metrics.network_connectivity) : 'N/A'}%
          </div>
          <div className="metric-description">
            Network interface connectivity status
          </div>
        </div>
      </div>
    </div>
  );
};
