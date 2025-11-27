import React, { useState, useMemo, useEffect } from 'react';
import { Chart } from './Chart';
import { MetricData } from '../types';
import './EnhancedChart.css';

interface EnhancedChartProps {
  metric: MetricData;
  chartType: string;
  title: string;
  onDimensionChange?: (dimension: string | null, entity: string | null, split: boolean) => void;
}

interface DimensionData {
  [key: string]: {
    [entity: string]: Array<[number, number]>;
  };
}

export const EnhancedChart: React.FC<EnhancedChartProps> = ({
  metric,
  chartType,
  title,
  onDimensionChange,
}) => {
  const [selectedDimension, setSelectedDimension] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [splitByDimension, setSplitByDimension] = useState(false);
  const [entityFilter, setEntityFilter] = useState('');
  const [availableDimensions, setAvailableDimensions] = useState<string[]>([]);
  const [availableEntities, setAvailableEntities] = useState<string[]>([]);

  // Extract dimensions from the metric data
  useEffect(() => {
    const dimensions = extractDimensions();
    setAvailableDimensions(dimensions);
  }, [metric]);

  const extractDimensions = (): string[] => {
    try {
      const data = metric.data as any;
      if (!data?.result?.[0]) return [];

      const resultItem = data.result[0];
      const dataItems = resultItem.data || [resultItem];

      const dimensionSet = new Set<string>();

      for (const dataItem of dataItems) {
        if (dataItem.dimensionMap) {
          Object.keys(dataItem.dimensionMap).forEach(dim => dimensionSet.add(dim));
        }
      }

      return Array.from(dimensionSet);
    } catch (err) {
      console.error('Error extracting dimensions:', err);
      return [];
    }
  };

  const filteredEntities = useMemo(() => {
    if (!selectedDimension || entityFilter === '') return availableEntities;

    return availableEntities.filter(entity =>
      entity.toLowerCase().includes(entityFilter.toLowerCase())
    );
  }, [selectedDimension, entityFilter, availableEntities]);

  const processedMetric = useMemo(() => {
    if (!selectedDimension) {
      return metric;
    }

    try {
      const data = metric.data as any;
      if (!data?.result?.[0]) return metric;

      const resultItem = data.result[0];
      const dataItems = resultItem.data || [resultItem];

      let timestamps: number[] = [];
      let values: any[] = [];

      for (const dataItem of dataItems) {
        if (dataItem.dimensionMap && dataItem.dimensionMap[selectedDimension]) {
          const dimensionMap = dataItem.dimensionMap[selectedDimension];

          // Filter by entity if selected
          if (selectedEntity && dimensionMap[selectedEntity] !== undefined) {
            // Get the index of this entity
            const entityIndex = Object.keys(dimensionMap).indexOf(selectedEntity);
            timestamps = dataItem.timestamps || [];

            if (splitByDimension) {
              // Return multi-series data
              values = Object.entries(dimensionMap).map(([entity, index]) => ({
                name: entity,
                data: (dataItem.values || []).map((v: any) => {
                  if (Array.isArray(v)) return v[index as number] ?? null;
                  return null;
                }),
              }));
            } else {
              // Return single series for selected entity
              values = (dataItem.values || []).map((v: any) => {
                if (Array.isArray(v)) return [v[entityIndex]];
                return v;
              });
            }
            break;
          } else if (!selectedEntity && !splitByDimension) {
            // No entity filter, aggregate all
            timestamps = dataItem.timestamps || [];
            const entityCount = Object.keys(dimensionMap).length;

            values = (dataItem.values || []).map((v: any) => {
              if (Array.isArray(v) && v.length > 0) {
                const sum = v.reduce((acc: number, val: number) => acc + (val || 0), 0);
                return [sum / entityCount]; // Average
              }
              return [0];
            });
            break;
          } else if (!selectedEntity && splitByDimension) {
            // Split by all entities
            timestamps = dataItem.timestamps || [];
            values = Object.entries(dimensionMap).map(([entity, index]) => ({
              name: entity,
              data: (dataItem.values || []).map((v: any) => {
                if (Array.isArray(v)) return v[index as number] ?? null;
                return null;
              }),
            }));
            break;
          }
        }
      }

      return {
        ...metric,
        data: {
          ...data,
          result: [
            {
              ...resultItem,
              data: [{
                timestamps,
                values,
                dimensions: Object.keys(
                  resultItem.data?.[0]?.dimensionMap?.[selectedDimension] || {}
                ),
              }],
            },
          ],
        },
      };
    } catch (err) {
      console.error('Error processing metric with dimensions:', err);
      return metric;
    }
  }, [metric, selectedDimension, selectedEntity, splitByDimension]);

  const handleDimensionChange = (dimension: string | null) => {
    setSelectedDimension(dimension);
    setSelectedEntity(null);
    setEntityFilter('');

    // Update available entities
    if (dimension) {
      try {
        const data = metric.data as any;
        const resultItem = data?.result?.[0];
        const dataItems = resultItem?.data || [resultItem];

        const entities = new Set<string>();
        for (const dataItem of dataItems) {
          if (dataItem.dimensionMap?.[dimension]) {
            Object.keys(dataItem.dimensionMap[dimension]).forEach(e => entities.add(e));
          }
        }
        setAvailableEntities(Array.from(entities));
      } catch (err) {
        console.error('Error updating entities:', err);
        setAvailableEntities([]);
      }
    }

    onDimensionChange?.(dimension, null, false);
  };

  const handleEntityChange = (entity: string | null) => {
    setSelectedEntity(entity);
    onDimensionChange?.(selectedDimension, entity, splitByDimension);
  };

  const handleSplitChange = (split: boolean) => {
    setSplitByDimension(split);
    onDimensionChange?.(selectedDimension, selectedEntity, split);
  };

  return (
    <div className="enhanced-chart-container">
      {availableDimensions.length > 0 && (
        <div className="dimension-controls">
          <div className="control-group">
            <label htmlFor={`dim-${title}`}>Dimensão:</label>
            <select
              id={`dim-${title}`}
              value={selectedDimension || ''}
              onChange={(e) => handleDimensionChange(e.target.value || null)}
              className="dimension-select"
            >
              <option value="">-- Todas as Entidades --</option>
              {availableDimensions.map((dim) => (
                <option key={dim} value={dim}>
                  {dim}
                </option>
              ))}
            </select>
          </div>

          {selectedDimension && availableEntities.length > 0 && (
            <div className="control-group">
              <label htmlFor={`entity-${title}`}>Filtro de Entidade:</label>
              <input
                id={`entity-${title}`}
                type="text"
                placeholder="Pesquisar por nome..."
                value={entityFilter}
                onChange={(e) => setEntityFilter(e.target.value)}
                className="entity-filter"
              />
              {entityFilter && filteredEntities.length > 0 && (
                <select
                  value={selectedEntity || ''}
                  onChange={(e) => handleEntityChange(e.target.value || null)}
                  className="entity-select"
                  size={Math.min(5, filteredEntities.length)}
                >
                  <option value="">-- Selecionar --</option>
                  {filteredEntities.map((entity) => (
                    <option key={entity} value={entity}>
                      {entity}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {selectedDimension && (
            <div className="control-group checkbox">
              <label htmlFor={`split-${title}`}>
                <input
                  id={`split-${title}`}
                  type="checkbox"
                  checked={splitByDimension}
                  onChange={(e) => handleSplitChange(e.target.checked)}
                  className="split-checkbox"
                />
                Split por Dimensão
              </label>
            </div>
          )}
        </div>
      )}

      <Chart
        metric={processedMetric}
        chartType={chartType}
        title={
          selectedDimension
            ? `${title} - ${selectedDimension}${selectedEntity ? ` (${selectedEntity})` : ''}`
            : title
        }
      />
    </div>
  );
};
