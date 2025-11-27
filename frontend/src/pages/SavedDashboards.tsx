import React, { useState, useEffect } from 'react';
import DynatraceAPI from '../services/api';
import { SavedDashboard } from '../types';
import './SavedDashboards.css';

interface SavedDashboardsProps {
  onNavigate?: (page: 'main' | 'create' | 'saved', dashboardId?: string) => void;
}

export const SavedDashboards: React.FC<SavedDashboardsProps> = ({ onNavigate }) => {
  const [dashboards, setDashboards] = useState<SavedDashboard[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadDashboards();
  }, []);

  const loadDashboards = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await DynatraceAPI.listDashboards();
      setDashboards(response.dashboards || []);
    } catch (err) {
      setError(`Failed to load dashboards: ${(err as Error).message}`);
      console.error('Error loading dashboards:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditDashboard = (dashboardId?: string) => {
    if (dashboardId && onNavigate) {
      onNavigate('create', dashboardId);
    }
  };

  const handleDeleteDashboard = async (dashboardId?: string) => {
    if (!dashboardId) return;

    try {
      await DynatraceAPI.deleteDashboard(dashboardId);
      setDashboards(dashboards.filter(d => d.id !== dashboardId));
      setDeleteConfirm(null);
    } catch (err) {
      setError(`Failed to delete dashboard: ${(err as Error).message}`);
      console.error('Error deleting dashboard:', err);
    }
  };

  const handleExportDashboard = async (dashboardId?: string) => {
    if (!dashboardId) return;

    try {
      const response = await DynatraceAPI.exportDashboard(dashboardId);
      // Create a download link
      const element = document.createElement('a');
      element.setAttribute('href', `data:text/plain;charset=utf-8,${encodeURIComponent(response.data)}`);
      element.setAttribute('download', response.filename);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    } catch (err) {
      setError(`Failed to export dashboard: ${(err as Error).message}`);
      console.error('Error exporting dashboard:', err);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  return (
    <div className="saved-dashboards">
      <div className="page-header">
        <h1>Saved Dashboards</h1>
        <button
          className="btn-primary"
          onClick={() => onNavigate?.('create')}
        >
          + Create New Dashboard
        </button>
      </div>

      {error && (
        <div className="alert alert-danger">
          {error}
          <button onClick={() => setError(null)} className="close-alert">×</button>
        </div>
      )}

      {isLoading ? (
        <div className="loading-state">Loading dashboards...</div>
      ) : dashboards.length === 0 ? (
        <div className="empty-state">
          <h2>No Saved Dashboards</h2>
          <p>You haven't created any dashboards yet.</p>
          <button
            className="btn-primary"
            onClick={() => onNavigate?.('create')}
          >
            Create Your First Dashboard
          </button>
        </div>
      ) : (
        <div className="dashboards-grid">
          {dashboards.map((dashboard) => (
            <div key={dashboard.id} className="dashboard-card">
              <div className="card-header">
                <h3>{dashboard.name}</h3>
                <div className="card-actions">
                  <button
                    className="btn-icon"
                    title="Edit"
                    onClick={() => handleEditDashboard(dashboard.id)}
                  >
                    ✏️
                  </button>
                  <button
                    className="btn-icon"
                    title="Export"
                    onClick={() => handleExportDashboard(dashboard.id)}
                  >
                    ⬇️
                  </button>
                  <button
                    className="btn-icon btn-danger"
                    title="Delete"
                    onClick={() => setDeleteConfirm(dashboard.id || null)}
                  >
                    🗑️
                  </button>
                </div>
              </div>

              {dashboard.description && (
                <p className="card-description">{dashboard.description}</p>
              )}

              <div className="card-metadata">
                <div className="metadata-item">
                  <span className="label">Metrics:</span>
                  <span className="value">{dashboard.metrics?.length || 0}</span>
                </div>
                <div className="metadata-item">
                  <span className="label">Created:</span>
                  <span className="value">{formatDate(dashboard.created_at)}</span>
                </div>
                <div className="metadata-item">
                  <span className="label">Updated:</span>
                  <span className="value">{formatDate(dashboard.updated_at)}</span>
                </div>
              </div>

              <div className="card-metrics">
                <h4>Metrics:</h4>
                <ul className="metrics-list">
                  {dashboard.metrics?.slice(0, 3).map((metric, idx) => (
                    <li key={idx}>
                      {metric.metric_key}
                      {metric.dimension && ` (${metric.dimension})`}
                    </li>
                  )) || []}
                </ul>
                {(dashboard.metrics?.length || 0) > 3 && (
                  <p className="more-metrics">
                    +{(dashboard.metrics?.length || 0) - 3} more...
                  </p>
                )}
              </div>

              {deleteConfirm === dashboard.id && (
                <div className="delete-confirmation">
                  <p>Are you sure you want to delete this dashboard?</p>
                  <div className="confirmation-actions">
                    <button
                      className="btn-secondary"
                      onClick={() => setDeleteConfirm(null)}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn-danger"
                      onClick={() => handleDeleteDashboard(dashboard.id)}
                    >
                      Delete
                    </button>
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
