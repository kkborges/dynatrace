import React, { useState, useMemo } from 'react';
import './TimeRangeSelector.css';

interface TimeRangeSelectorProps {
  selectedRange: string;
  customStart?: number;
  customEnd?: number;
  onRangeChange: (
    rangeType: string,
    startTime?: number,
    endTime?: number
  ) => void;
}

export const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({
  selectedRange,
  customStart,
  customEnd,
  onRangeChange,
}) => {
  const [showCustom, setShowCustom] = useState(selectedRange === 'custom');

  const presetRanges = [
    { value: '1m', label: '1 Minute' },
    { value: '5m', label: '5 Minutes' },
    { value: '15m', label: '15 Minutes' },
    { value: '30m', label: '30 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: 'today', label: 'Today' },
    { value: 'yesterday', label: 'Yesterday' },
    { value: '30days', label: 'Last 30 Days' },
    { value: 'custom', label: 'Custom Date Range' },
  ];

  const handleRangeChange = (rangeType: string) => {
    if (rangeType === 'custom') {
      setShowCustom(true);
      onRangeChange(rangeType, customStart, customEnd);
    } else {
      setShowCustom(false);
      onRangeChange(rangeType);
    }
  };

  const handleCustomStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const start = e.target.valueAsNumber;
    onRangeChange('custom', start, customEnd);
  };

  const handleCustomEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const end = e.target.valueAsNumber;
    onRangeChange('custom', customStart, end);
  };

  return (
    <div className="time-range-selector">
      <div className="preset-ranges">
        {presetRanges.map((range) => (
          <button
            key={range.value}
            className={`preset-button ${
              selectedRange === range.value ? 'selected' : ''
            }`}
            onClick={() => handleRangeChange(range.value)}
          >
            {range.label}
          </button>
        ))}
      </div>

      {showCustom && selectedRange === 'custom' && (
        <div className="custom-range">
          <div className="custom-input-group">
            <label htmlFor="custom-start">Start Date & Time:</label>
            <input
              id="custom-start"
              type="datetime-local"
              value={
                customStart
                  ? new Date(customStart).toISOString().slice(0, 16)
                  : ''
              }
              onChange={handleCustomStartChange}
            />
          </div>

          <div className="custom-input-group">
            <label htmlFor="custom-end">End Date & Time:</label>
            <input
              id="custom-end"
              type="datetime-local"
              value={
                customEnd
                  ? new Date(customEnd).toISOString().slice(0, 16)
                  : ''
              }
              onChange={handleCustomEndChange}
            />
          </div>
        </div>
      )}
    </div>
  );
};
