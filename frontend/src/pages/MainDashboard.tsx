import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import { AvailabilityMetrics } from '../types';
import './MainDashboard.css';

export const MainDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<AvailabilityMetrics | null>(null);
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
    console.log('Data keys:', Object.keys(data));

    // Handle the Dynatrace API response structure
    const result = (data.result || []) as Array<{
      data?: Array<{
        values?: Array<(number | null)[]>;
        points?: Array<{ value: number; timestamp: number }>;
        timestamps?: number[];
      }>;
      values?: Array<(number | null)[]>;
      points?: Array<{ value: number; timestamp: number }>;
    }>;

    if (result.length === 0) {
      console.log('No results in data');
      return 'N/A';
    }

    const resultItem = result[0];
    console.log('Result item:', resultItem);
    console.log('Result item keys:', Object.keys(resultItem));

    // Try to get data from nested structure first (result[0].data[0].values)
    if (resultItem.data && Array.isArray(resultItem.data) && resultItem.data.length > 0) {
      const dataItem = resultItem.data[0];
      console.log('Data item:', dataItem);
      console.log('Data item keys:', Object.keys(dataItem));

      // Try new structure (data[].points)
      if (dataItem.points && Array.isArray(dataItem.points) && dataItem.points.length > 0) {
        const lastPoint = dataItem.points[dataItem.points.length - 1];
        console.log('Found points, last point:', lastPoint);
        if (lastPoint && lastPoint.value !== null) {
          return (lastPoint.value as number).toFixed(2);
        }
      }

      // Try old structure (data[].values) - values can be either array of arrays OR array of numbers
      if (dataItem.values && Array.isArray(dataItem.values) && dataItem.values.length > 0) {
        console.log('Found values array, type of first item:', typeof dataItem.values[0]);

        // Find last non-null value (working backwards)
        for (let i = dataItem.values.length - 1; i >= 0; i--) {
          const val = dataItem.values[i];
          console.log(`Checking value at index ${i}:`, val);

          // Handle direct numeric values
          if (typeof val === 'number' && val !== null) {
            return (val as number).toFixed(2);
          }

          // Handle array-wrapped values [[99.5], [99.3], ...]
          if (Array.isArray(val) && val.length > 0 && val[0] !== null) {
            return (val[0] as number).toFixed(2);
          }
        }
      }

      // Try timestamps + values array structure
      if (dataItem.timestamps && Array.isArray(dataItem.timestamps)) {
        console.log('Found timestamps:', dataItem.timestamps);
        // If there are timestamps, there should be corresponding values somewhere
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
      // Try both numeric and array formats
      for (let i = resultItem.values.length - 1; i >= 0; i--) {
        const val = resultItem.values[i];
        if (typeof val === 'number' && val !== null) {
          return (val as number).toFixed(2);
        }
        if (Array.isArray(val) && val.length > 0 && val[0] !== null) {
          return (val[0] as number).toFixed(2);
        }
      }
    }

    console.log('Could not find value in any expected format');
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
