import React, { useState, useMemo } from 'react';
import { Metric } from '../types';
import DynatraceAPI from '../services/api';
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
  const [validatingMetric, setValidatingMetric] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<{ [key: string]: string }>({});

  const filteredMetrics = useMemo(() => {
    if (!searchTerm.trim()) return metrics;

    const lowerSearch = searchTerm.toLowerCase();
    return metrics.filter(
      (metric) =>
        (metric.key && metric.key.toLowerCase().includes(lowerSearch)) ||
        (metric.name && metric.name.toLowerCase().includes(lowerSearch))
    );
  }, [metrics, searchTerm]);

  const toggleMetric = async (metricKey: string) => {
    // If adding a metric, validate it first
    if (!selectedMetrics.includes(metricKey)) {
      setValidatingMetric(metricKey);
      try {
        await DynatraceAPI.validateMetric(metricKey);
        // Validation passed, add the metric
        setValidationErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors[metricKey];
          return newErrors;
        });
        onMetricsChange([...selectedMetrics, metricKey]);
      } catch (error: any) {
        // Validation failed, show error
        const errorMessage = error.response?.data?.detail || 'Metric validation failed';
        setValidationErrors(prev => ({
          ...prev,
          [metricKey]: errorMessage
        }));
      } finally {
        setValidatingMetric(null);
      }
    } else {
      // Removing a metric, no validation needed
      onMetricsChange(selectedMetrics.filter((m) => m !== metricKey));
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[metricKey];
        return newErrors;
      });
    }
  };

  return (
    <div className="metrics-selector">
      <div className="search-box">
        <input
          type="text"
          placeholder="Search metrics... (e.g., cpu, memory, availability)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          disabled={isLoading}
          className="search-input"
        />
        <span className="search-hint">
          {filteredMetrics.length} metric{filteredMetrics.length !== 1 ? 's' : ''} found
        </span>
      </div>

      <div className="metrics-list">
        {isLoading ? (
          <div className="loading">Loading metrics...</div>
        ) : metrics.length === 0 ? (
          <div className="no-results">
            <p>No metrics available</p>
            <p className="hint">Click "Refresh Metrics" button to load metrics from Dynatrace</p>
          </div>
        ) : filteredMetrics.length === 0 ? (
          <div className="no-results">No metrics match your search</div>
        ) : (
          filteredMetrics.map((metric, index) => {
            const metricKey = metric.key || metric.name || '';
            const uniqueKey = metricKey ? `${metricKey}-${index}` : `metric-${index}`;
            const hasError = validationErrors[metricKey];
            const isValidating = validatingMetric === metricKey;
            const isSelected = selectedMetrics.includes(metricKey);

            return (
              <div key={uniqueKey} className={`metric-item ${hasError ? 'error' : ''}`}>
                <label className="metric-label">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleMetric(metricKey)}
                    disabled={isLoading || isValidating}
                  />
                  <div className="metric-content">
                    <div className="metric-name" title={metricKey}>
                      {metric.name || metricKey}
                    </div>
                    {metricKey !== (metric.name || metricKey) && (
                      <div className="metric-key" title={metricKey}>
                        Key: {metricKey}
                      </div>
                    )}
                    {metric.description && (
                      <span className="metric-description">{metric.description}</span>
                    )}
                    {metric.unit && <span className="metric-unit">Unit: {metric.unit}</span>}
                  </div>
                  {isValidating && <span className="validating">Validating...</span>}
                </label>
                {hasError && (
                  <div className="error-message">
                    ⚠️ {hasError}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {selectedMetrics.length > 0 && (
        <div className="selected-metrics">
          <strong>Selected Metrics ({selectedMetrics.length}):</strong>
          <div className="selected-tags">
            {selectedMetrics.map((metric) => (
              <div key={metric} className="tag" title={metric}>
                <span className="tag-text">{metric}</span>
                <button
                  type="button"
                  onClick={() => toggleMetric(metric)}
                  className="tag-remove"
                  title="Remove metric"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
