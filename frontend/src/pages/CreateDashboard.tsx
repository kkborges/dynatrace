import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import { MetricsSelector } from '../components/MetricsSelector';
import { ChartTypeSelector } from '../components/ChartTypeSelector';
import { TimeRangeSelector } from '../components/TimeRangeSelector';
import { Chart } from '../components/Chart';
import { Metric, MetricData, ChartType } from '../types';
import './CreateDashboard.css';

export const CreateDashboard: React.FC = () => {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [chartTypes, setChartTypes] = useState<ChartType[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [selectedCharts, setSelectedCharts] = useState<{ [metric: string]: string }>({});
  const [selectedTimeRange, setSelectedTimeRange] = useState('1h');
  const [customStart, setCustomStart] = useState<number>();
  const [customEnd, setCustomEnd] = useState<number>();
  const [timeRange, setTimeRange] = useState<{ start_timestamp: number; end_timestamp: number } | null>(null);
  const [metricsData, setMetricsData] = useState<{ [key: string]: MetricData }>({});
  const [testResults, setTestResults] = useState<Array<{ metric_key: string; status: string; data_points?: number; error?: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dashboardName, setDashboardName] = useState('My Dashboard');
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    loadMetricsAndChartTypes();
  }, []);

  useEffect(() => {
    if (selectedTimeRange) {
      calculateTimeRange();
    }
  }, [selectedTimeRange, customStart, customEnd]);

  const loadMetricsAndChartTypes = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Try to refresh metrics from Dynatrace
      try {
        await DynatraceAPI.refreshMetrics();
      } catch (err) {
        console.warn('Could not refresh metrics from Dynatrace', err);
      }

      // Load metrics list
      const metricsResponse = await DynatraceAPI.getMetricsList();
      const metricsWithMetadata = (metricsResponse.metrics || []).map((m: string | Metric) => {
        if (typeof m === 'string') {
          return { key: m, name: m };
        }
        return m;
      });
      setMetrics(metricsWithMetadata);

      // Load chart types
      const chartTypesResponse = await DynatraceAPI.getChartTypes();
      const chartTypesFormatted = (chartTypesResponse.chart_types || []).map(ct => ({
        ...ct,
        category: (ct.category === 'modern' || ct.category === 'common') ? ct.category : 'common'
      })) as ChartType[];
      setChartTypes(chartTypesFormatted);
    } catch (err) {
      setError('Failed to load metrics and chart types. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const calculateTimeRange = async () => {
    try {
      const response = await DynatraceAPI.calculateTimeRange(
        selectedTimeRange,
        customStart,
        customEnd
      );
      setTimeRange({
        start_timestamp: response.start_timestamp,
        end_timestamp: response.end_timestamp,
      });
    } catch (err) {
      setError('Failed to calculate time range.');
      console.error(err);
    }
  };

  const handleMetricsChange = (newMetrics: string[]) => {
    setSelectedMetrics(newMetrics);

    // Initialize chart types for new metrics
    const newCharts = { ...selectedCharts };
    newMetrics.forEach((metric) => {
      if (!newCharts[metric] && chartTypes.length > 0) {
        newCharts[metric] = chartTypes[0].id;
      }
    });
    setSelectedCharts(newCharts);
  };

  const handleChartTypeChange = (metric: string, chartType: string) => {
    setSelectedCharts((prev) => ({
      ...prev,
      [metric]: chartType,
    }));
  };

  const handleTimeRangeChange = (
    rangeType: string,
    startTime?: number,
    endTime?: number
  ) => {
    setSelectedTimeRange(rangeType);
    if (rangeType === 'custom') {
      setCustomStart(startTime);
      setCustomEnd(endTime);
    }
  };

  const handleTestDashboard = async () => {
    if (!timeRange || selectedMetrics.length === 0) {
      setError('Please select at least one metric and a time range.');
      return;
    }

    try {
      setIsTesting(true);
      setError(null);

      // Fetch metric data
      const dataMap: { [key: string]: MetricData } = {};
      const testResults = [];

      for (const metric of selectedMetrics) {
        try {
          const data = await DynatraceAPI.getMetricData(
            metric,
            timeRange.start_timestamp,
            timeRange.end_timestamp,
            '1m'
          );
          dataMap[metric] = {
            metric_key: metric,
            data: (data as unknown) as Record<string, unknown>,
          };
          testResults.push({
            metric_key: metric,
            status: 'success',
            data_points: (((data as unknown) as Record<string, unknown>).result as unknown[])?.length || 0,
          });
        } catch (err) {
          testResults.push({
            metric_key: metric,
            status: 'error',
            error: (err as Error).message,
          });
        }
      }

      setMetricsData(dataMap);
      setTestResults(testResults);
      setStep(4);
    } catch (err) {
      setError('Failed to test dashboard. Please try again.');
      console.error(err);
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="create-dashboard">
      <div className="dashboard-form">
        <div className="form-header">
          <h2>Create Custom Dashboard</h2>
          <div className="step-indicator">
            {[1, 2, 3, 4].map((s) => (
              <div
                key={s}
                className={`step ${step === s ? 'active' : ''} ${step > s ? 'completed' : ''}`}
              >
                {s}
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="alert alert-danger">
            {error}
            <button onClick={() => setError(null)} className="close-alert">×</button>
          </div>
        )}

        <div className="form-content">
          {step === 1 && (
            <div className="form-step">
              <h3>Step 1: Select Metrics</h3>
              <p>Choose one or more metrics to display in your dashboard.</p>
              <MetricsSelector
                metrics={metrics}
                selectedMetrics={selectedMetrics}
                onMetricsChange={handleMetricsChange}
                isLoading={isLoading}
              />
            </div>
          )}

          {step === 2 && (
            <div className="form-step">
              <h3>Step 2: Select Chart Types</h3>
              <p>Choose a chart type for each selected metric.</p>
              <ChartTypeSelector
                chartTypes={chartTypes}
                selectedCharts={selectedCharts}
                selectedMetrics={selectedMetrics}
                onChartTypeChange={handleChartTypeChange}
              />
            </div>
          )}

          {step === 3 && (
            <div className="form-step">
              <h3>Step 3: Select Time Range</h3>
              <p>Choose a time range for your metrics.</p>
              <TimeRangeSelector
                selectedRange={selectedTimeRange}
                customStart={customStart}
                customEnd={customEnd}
                onRangeChange={handleTimeRangeChange}
              />
            </div>
          )}

          {step === 4 && (
            <div className="form-step">
              <h3>Step 4: Review Dashboard</h3>
              <div className="dashboard-preview">
                <div className="test-results">
                  <h4>Test Results</h4>
                  {testResults.map((result) => (
                    <div
                      key={result.metric_key}
                      className={`test-result ${result.status}`}
                    >
                      <span className="metric-name">{result.metric_key}</span>
                      <span className={`status ${result.status}`}>
                        {result.status === 'success'
                          ? `✓ ${result.data_points} data points`
                          : `✗ ${result.error}`}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="charts-preview">
                  <h4>Charts Preview</h4>
                  <div className="charts-grid">
                    {selectedMetrics.map((metric) => (
                      <Chart
                        key={metric}
                        metric={metricsData[metric] || {
                          metric_key: metric,
                          data: {},
                        }}
                        chartType={selectedCharts[metric] || 'line'}
                        title={metric}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="form-actions">
          {step > 1 && (
            <button
              className="btn-secondary"
              onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3 | 4)}
              disabled={isTesting}
            >
              Previous
            </button>
          )}

          {step < 4 ? (
            <button
              className="btn-primary"
              onClick={() => {
                if (step === 1 && selectedMetrics.length === 0) {
                  setError('Please select at least one metric.');
                  return;
                }
                if (step === 2 && Object.keys(selectedCharts).length === 0) {
                  setError('Please select chart types.');
                  return;
                }
                setStep((s) => (s + 1) as 1 | 2 | 3 | 4);
              }}
              disabled={isTesting}
            >
              Next
            </button>
          ) : (
            <button
              className="btn-success"
              onClick={handleTestDashboard}
              disabled={isTesting || selectedMetrics.length === 0}
            >
              {isTesting ? 'Testing...' : 'Test Metrics'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
