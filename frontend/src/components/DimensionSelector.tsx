import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import { DimensionInfo } from '../types';
import './DimensionSelector.css';

interface DimensionSelectorProps {
  metricKey: string;
  startTimestamp: number;
  endTimestamp: number;
  resolution?: string;
  onDimensionChange?: (dimension: string | null) => void;
  onEntityFilterChange?: (entity: string | null) => void;
  onSplitByDimensionChange?: (split: boolean) => void;
  selectedDimension?: string | null;
  selectedEntity?: string | null;
  splitByDimension?: boolean;
}

export const DimensionSelector: React.FC<DimensionSelectorProps> = ({
  metricKey,
  startTimestamp,
  endTimestamp,
  resolution = '1m',
  onDimensionChange,
  onEntityFilterChange,
  onSplitByDimensionChange,
  selectedDimension = null,
  selectedEntity = null,
  splitByDimension = false,
}) => {
  const [dimensions, setDimensions] = useState<DimensionInfo[]>([]);
  const [entityNames, setEntityNames] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDim, setSelectedDim] = useState<string | null>(selectedDimension);
  const [selectedEnt, setSelectedEnt] = useState<string | null>(selectedEntity);
  const [split, setSplit] = useState(splitByDimension);
  const [filteredEntityValues, setFilteredEntityValues] = useState<string[]>([]);

  useEffect(() => {
    loadDimensions();
  }, [metricKey, startTimestamp, endTimestamp, resolution]);

  useEffect(() => {
    // Update filtered entity values when selected dimension changes
    if (selectedDim) {
      const dimension = dimensions.find(d => d.name === selectedDim);
      if (dimension) {
        setFilteredEntityValues(dimension.values);
      }
    }
  }, [selectedDim, dimensions]);

  const loadDimensions = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await DynatraceAPI.getMetricDimensions(
        metricKey,
        startTimestamp,
        endTimestamp,
        resolution
      );

      setDimensions(response.dimensions || []);
      setEntityNames(response.entity_names || []);
    } catch (err) {
      setError(`Failed to load dimensions: ${(err as Error).message}`);
      console.error('Error loading dimensions:', err);
      setDimensions([]);
      setEntityNames([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDimensionChange = (dimensionName: string | null) => {
    setSelectedDim(dimensionName);
    setSelectedEnt(null); // Reset entity selection when dimension changes
    onDimensionChange?.(dimensionName);
  };

  const handleEntityChange = (entityName: string | null) => {
    setSelectedEnt(entityName);
    onEntityFilterChange?.(entityName);
  };

  const handleSplitChange = (splitVal: boolean) => {
    setSplit(splitVal);
    onSplitByDimensionChange?.(splitVal);
  };

  if (isLoading) {
    return <div className="dimension-selector loading">Loading dimensions...</div>;
  }

  if (error) {
    return <div className="dimension-selector error">Error: {error}</div>;
  }

  if (dimensions.length === 0) {
    return <div className="dimension-selector no-data">No dimensions available for this metric</div>;
  }

  return (
    <div className="dimension-selector">
      <div className="dimension-controls">
        <div className="control-group">
          <label htmlFor="dimension-select">Select Dimension:</label>
          <select
            id="dimension-select"
            value={selectedDim || ''}
            onChange={(e) => handleDimensionChange(e.target.value || null)}
            className="dimension-input"
          >
            <option value="">-- All Data --</option>
            {dimensions.map((dim) => (
              <option key={dim.name} value={dim.name}>
                {dim.name}
              </option>
            ))}
          </select>
        </div>

        {selectedDim && filteredEntityValues.length > 0 && (
          <div className="control-group">
            <label htmlFor="entity-select">Filter by Entity:</label>
            <select
              id="entity-select"
              value={selectedEnt || ''}
              onChange={(e) => handleEntityChange(e.target.value || null)}
              className="entity-input"
            >
              <option value="">-- All --</option>
              {filteredEntityValues.map((entity) => (
                <option key={entity} value={entity}>
                  {entity}
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedDim && (
          <div className="control-group checkbox">
            <label htmlFor="split-dimension">
              <input
                id="split-dimension"
                type="checkbox"
                checked={split}
                onChange={(e) => handleSplitChange(e.target.checked)}
                className="split-checkbox"
              />
              Split by Dimension (Multiple Series)
            </label>
          </div>
        )}
      </div>

      {selectedDim && (
        <div className="dimension-info">
          <p className="info-text">
            Showing dimension: <strong>{selectedDim}</strong>
            {selectedEnt && ` (Entity: ${selectedEnt})`}
            {split && ' (Split by dimension values)'}
          </p>
        </div>
      )}
    </div>
  );
};
