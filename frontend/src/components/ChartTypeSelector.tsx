import React, { useState, useMemo } from 'react';
import { ChartType } from '../types';
import './ChartTypeSelector.css';

interface ChartTypeSelectorProps {
  chartTypes: ChartType[];
  selectedCharts: { [metric: string]: string };
  selectedMetrics: string[];
  onChartTypeChange: (metric: string, chartType: string) => void;
}

export const ChartTypeSelector: React.FC<ChartTypeSelectorProps> = ({
  chartTypes,
  selectedCharts,
  selectedMetrics,
  onChartTypeChange,
}) => {
  const [expandedMetric, setExpandedMetric] = useState<string | null>(
    selectedMetrics.length > 0 ? selectedMetrics[0] : null
  );

  const commonCharts = useMemo(
    () => chartTypes.filter((c) => c.category === 'common'),
    [chartTypes]
  );

  const modernCharts = useMemo(
    () => chartTypes.filter((c) => c.category === 'modern'),
    [chartTypes]
  );

  return (
    <div className="chart-type-selector">
      {selectedMetrics.length === 0 ? (
        <div className="no-metrics-selected">
          Select metrics first to choose chart types
        </div>
      ) : (
        <div className="metrics-chart-selector">
          {selectedMetrics.map((metric) => (
            <div key={metric} className="metric-chart-section">
              <button
                className="metric-header"
                onClick={() =>
                  setExpandedMetric(expandedMetric === metric ? null : metric)
                }
              >
                <span className="metric-name">{metric}</span>
                <span className="expand-icon">
                  {expandedMetric === metric ? '▼' : '▶'}
                </span>
              </button>

              {expandedMetric === metric && (
                <div className="chart-options">
                  <div className="chart-category">
                    <h4>Common Charts</h4>
                    <div className="chart-buttons">
                      {commonCharts.map((chart) => (
                        <button
                          key={chart.id}
                          className={`chart-button ${
                            selectedCharts[metric] === chart.id
                              ? 'selected'
                              : ''
                          }`}
                          onClick={() =>
                            onChartTypeChange(metric, chart.id)
                          }
                        >
                          {chart.name}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="chart-category">
                    <h4>Modern Charts</h4>
                    <div className="chart-buttons">
                      {modernCharts.map((chart) => (
                        <button
                          key={chart.id}
                          className={`chart-button ${
                            selectedCharts[metric] === chart.id
                              ? 'selected'
                              : ''
                          }`}
                          onClick={() =>
                            onChartTypeChange(metric, chart.id)
                          }
                        >
                          {chart.name}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
