import React, { useState, useMemo } from 'react';
import { Metric } from '../types';
import './MetricsSelector.css';

interface MetricsSelectorProps {
  metrics: Metric[];
  selectedMetrics: string[];
  onMetricsChange: (metrics: string[]) => void;
  isLoading?: boolean;
}

export const MetricsSelector: React.FC<MetricsSelectorProps> = ({
  metrics,
  selectedMetrics,
  onMetricsChange,
  isLoading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredMetrics = useMemo(() => {
    if (!searchTerm.trim()) return metrics;

    const lowerSearch = searchTerm.toLowerCase();
    return metrics.filter(
      (metric) =>
        metric.key.toLowerCase().includes(lowerSearch) ||
        metric.name.toLowerCase().includes(lowerSearch)
    );
  }, [metrics, searchTerm]);

  const toggleMetric = (metricKey: string) => {
    setSelectedMetrics(
      selectedMetrics.includes(metricKey)
        ? selectedMetrics.filter((m) => m !== metricKey)
        : [...selectedMetrics, metricKey]
    );
  };

  return (
    <div className="metrics-selector">
      <div className="search-box">
        <input
          type="text"
          placeholder="Search metrics..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          disabled={isLoading}
          className="search-input"
        />
      </div>

      <div className="metrics-list">
        {isLoading ? (
          <div className="loading">Loading metrics...</div>
        ) : filteredMetrics.length === 0 ? (
          <div className="no-results">No metrics found</div>
        ) : (
          filteredMetrics.map((metric) => (
            <label key={metric.key} className="metric-item">
              <input
                type="checkbox"
                checked={selectedMetrics.includes(metric.key)}
                onChange={() => toggleMetric(metric.key)}
                disabled={isLoading}
              />
              <div className="metric-content">
                <span className="metric-name">{metric.name || metric.key}</span>
                {metric.description && (
                  <span className="metric-description">{metric.description}</span>
                )}
                {metric.unit && <span className="metric-unit">({metric.unit})</span>}
              </div>
            </label>
          ))
        )}
      </div>

      {selectedMetrics.length > 0 && (
        <div className="selected-metrics">
          <strong>Selected ({selectedMetrics.length}):</strong>
          <div className="selected-tags">
            {selectedMetrics.map((metric) => (
              <span key={metric} className="tag">
                {metric}
                <button
                  type="button"
                  onClick={() => toggleMetric(metric)}
                  className="tag-remove"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
