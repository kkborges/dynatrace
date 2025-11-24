import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import { AvailabilityMetrics } from '../types';
import './MainDashboard.css';

export const MainDashboard: React.FC = () => {
  const [availability, setAvailability] = useState<AvailabilityMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTime, setRefreshTime] = useState<string>(new Date().toLocaleTimeString());

  useEffect(() => {
    loadAvailability();
  }, []);

  const loadAvailability = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await DynatraceAPI.getAvailabilityDashboard();
      setAvailability(data);
      setRefreshTime(new Date().toLocaleTimeString());
    } catch (err) {
      setError('Failed to load availability metrics. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const getMetricValue = (data: Record<string, unknown>): string => {
    if (!data) return 'N/A';
    const result = (data.result || []) as Array<{
      values: Array<(number | null)[]>;
    }>;
    if (result.length > 0 && result[0].values && result[0].values.length > 0) {
      const lastValue = result[0].values[result[0].values.length - 1];
      if (lastValue && lastValue[0] !== null) {
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
        <h2>Availability Dashboard</h2>
        <div className="dashboard-controls">
          <button onClick={loadAvailability} className="refresh-button">
            🔄 Refresh
          </button>
          <span className="last-refresh">Last refresh: {refreshTime}</span>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          {error}
          <button onClick={loadAvailability} className="retry-button">
            Retry
          </button>
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <h3>Host Availability</h3>
            {availability && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(availability.hosts as Record<string, unknown>))}`}>
                {getStatusBadge(getMetricValue(availability.hosts as Record<string, unknown>))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {availability ? getMetricValue(availability.hosts as Record<string, unknown>) : 'N/A'}%
          </div>
          <div className="metric-description">
            Percentage of hosts currently available and responsive
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <h3>Application Availability</h3>
            {availability && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(availability.applications as Record<string, unknown>))}`}>
                {getStatusBadge(getMetricValue(availability.applications as Record<string, unknown>))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {availability ? getMetricValue(availability.applications as Record<string, unknown>) : 'N/A'}%
          </div>
          <div className="metric-description">
            Percentage of applications currently available
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <h3>Service Availability</h3>
            {availability && (
              <span className={`status-badge ${getStatusBadge(getMetricValue(availability.services as Record<string, unknown>))}`}>
                {getStatusBadge(getMetricValue(availability.services as Record<string, unknown>))}
              </span>
            )}
          </div>
          <div className="metric-value">
            {availability ? getMetricValue(availability.services as Record<string, unknown>) : 'N/A'}%
          </div>
          <div className="metric-description">
            Percentage of services currently available and responding
          </div>
        </div>
      </div>
    </div>
  );
};
