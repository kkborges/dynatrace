import React, { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts';
import { MetricData } from '../types';
import './Chart.css';

interface ChartProps {
  metric: MetricData;
  chartType: string;
  title?: string;
}

export const Chart: React.FC<ChartProps> = ({
  metric,
  chartType,
  title,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const chartOption = useMemo(() => {
    const data = metric.data as Record<string, unknown>;
    const result = (data.result || []) as Array<{
      dimensions?: string[];
      timestamps?: number[];
      values?: Array<(number | null)[]>;
      data?: Array<{
        dimensions: string[];
        timestamps: number[];
        values: Array<(number | null)[]>;
      }>;
      dimensionMap?: Record<string, unknown>;
    }>;

    if (result.length === 0) {
      return getEmptyChartOption(chartType);
    }

    const firstResult = result[0];
    let timestamps: number[] = [];
    let values: Array<(number | null)[]> = [];

    // Try to get data from nested structure first (result[0].data[0])
    if (firstResult.data && Array.isArray(firstResult.data) && firstResult.data.length > 0) {
      const dataItem = firstResult.data[0];
      timestamps = dataItem.timestamps || [];
      values = dataItem.values || [];
    } else {
      // Try direct structure (result[0].timestamps and result[0].values)
      timestamps = firstResult.timestamps || [];
      values = firstResult.values || [];
    }

    if (timestamps.length === 0 || values.length === 0) {
      return getEmptyChartOption(chartType);
    }

    const xAxisData = timestamps.map((t) =>
      new Date(t).toLocaleTimeString()
    );
    const yAxisData = values.map((v) => Array.isArray(v) ? v[0] : v);

    return generateChartOption(chartType, xAxisData, yAxisData, metric.metric_key);
  }, [metric, chartType]);

  useEffect(() => {
    if (!containerRef.current) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }

    chartRef.current.setOption(chartOption);

    const handleResize = () => {
      chartRef.current?.resize();
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [chartOption]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  return (
    <div className="chart-container">
      {title && <h3 className="chart-title">{title}</h3>}
      <div ref={containerRef} className="chart-content" />
    </div>
  );
};

function getEmptyChartOption(chartType: string): echarts.EChartsOption {
  return {
    title: {
      text: 'No Data Available',
      left: 'center',
      top: 'center',
    },
    xAxis: { type: 'category' } as any,
    yAxis: {} as any,
    series: [],
  };
}

function generateChartOption(
  chartType: string,
  xAxisData: string[],
  yAxisData: (number | null)[],
  metricName: string
): echarts.EChartsOption {
  // Calculate max value for percentage formatting
  const maxValue = Math.max(...yAxisData.filter(v => v !== null) as number[]);
  const isPercentage = metricName.toLowerCase().includes('availability') ||
                        metricName.toLowerCase().includes('cpu') ||
                        metricName.toLowerCase().includes('memory');

  const baseOption = {
    title: {
      text: metricName,
      left: 'center',
    },
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        if (Array.isArray(params) && params.length > 0) {
          let html = `<div style="padding: 8px; background: rgba(0,0,0,0.8); border-radius: 4px; color: #fff;">`;
          html += `<p style="margin: 0 0 8px 0; font-weight: bold;">${params[0].axisValue}</p>`;

          params.forEach((param: any) => {
            let value = param.value;
            let formattedValue = '';

            if (value === null || value === undefined) {
              formattedValue = 'N/A';
            } else if (isPercentage && maxValue <= 100) {
              formattedValue = `${parseFloat(value).toFixed(2)}%`;
            } else {
              formattedValue = `${parseFloat(value).toFixed(2)}`;
            }

            html += `<p style="margin: 4px 0; color: ${param.color};">
              <strong>${param.seriesName || 'Value'}:</strong> ${formattedValue}
            </p>`;
          });

          html += `</div>`;
          return html;
        }
        return '';
      },
    },
    legend: {
      top: 40,
    },
  };

  switch (chartType) {
    case 'line':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value' },
        series: [
          {
            data: yAxisData,
            type: 'line',
            smooth: true,
            areaStyle: { opacity: 0.3 },
          },
        ],
      };

    case 'bar':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value' },
        series: [
          {
            data: yAxisData,
            type: 'bar',
            itemStyle: { color: '#007bff' },
          },
        ],
      };

    case 'area':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value' },
        series: [
          {
            data: yAxisData,
            type: 'line',
            areaStyle: { color: '#007bff', opacity: 0.5 },
            lineStyle: { color: '#0056b3' },
          },
        ],
      };

    case 'scatter':
      return {
        ...baseOption,
        xAxis: { type: 'value' },
        yAxis: { type: 'value' },
        series: [
          {
            data: yAxisData.map((y, i) => [i, y]),
            type: 'scatter',
            symbolSize: 8,
            itemStyle: { color: '#007bff' },
          },
        ],
      };

    case 'pie':
      return {
        ...baseOption,
        tooltip: { trigger: 'item' },
        series: [
          {
            data: xAxisData.map((x, i) => ({
              value: yAxisData[i],
              name: x,
            })),
            type: 'pie',
            radius: '50%',
          },
        ],
      };

    case 'gauge':
      const gaugeValue = yAxisData.filter((v) => v !== null).pop() || 0;
      return {
        ...baseOption,
        series: [
          {
            type: 'gauge',
            startAngle: 225,
            endAngle: -45,
            min: 0,
            max: 100,
            splitNumber: 8,
            axisLine: {
              lineStyle: {
                width: 30,
                color: [
                  [0.3, '#67ee22'],
                  [0.7, '#ffde33'],
                  [1, '#ff6e40'],
                ],
              },
            },
            pointer: {
              itemStyle: {
                color: 'auto',
              },
            },
            axisTick: {
              distance: -30,
              length: 8,
              lineStyle: {
                color: '#fff',
                width: 2,
              },
            },
            splitLine: {
              distance: -30,
              length: 30,
              lineStyle: {
                color: '#fff',
                width: 4,
              },
            },
            axisLabel: {
              color: 'auto',
              distance: 40,
              fontSize: 16,
            },
            detail: {
              valueAnimation: true,
              formatter: '{value}',
              color: 'auto',
            },
            data: [{ value: Math.min(100, Math.max(0, gaugeValue as number)), name: metricName }],
          },
        ],
      };

    case 'candlestick':
      // Convert to OHLC format
      const candleData = yAxisData.map((y, i) => {
        const val = y || 0;
        return [val * 0.8, val * 1.2, val * 0.9, val * 1.1];
      });
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value' },
        series: [
          {
            data: candleData,
            type: 'candlestick',
          },
        ],
      };

    case 'heatmap':
      const heatmapData = yAxisData.map((y, i) => [i % 10, Math.floor(i / 10), y]);
      return {
        ...baseOption,
        xAxis: { type: 'category', data: Array.from({ length: 10 }, (_, i) => `${i}`) },
        yAxis: { type: 'category', data: Array.from({ length: Math.ceil(yAxisData.length / 10) }, (_, i) => `${i}`) },
        series: [
          {
            data: heatmapData,
            type: 'heatmap',
            label: { show: false },
            emphasis: {
              itemStyle: {
                borderColor: '#333',
                borderWidth: 1,
              },
            },
          },
        ],
      };

    default:
      return getEmptyChartOption('line');
  }
}
