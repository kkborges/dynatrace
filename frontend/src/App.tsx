import React, { useState, useEffect } from 'react';
import DynatraceAPI from './services/api';
import { MainDashboard } from './pages/MainDashboard';
import { CreateDashboard } from './pages/CreateDashboard';
import { SavedDashboards } from './pages/SavedDashboards';
import { SLOManagement } from './pages/SLOManagement';
import './App.css';

type Page = 'main' | 'create' | 'saved' | 'slo';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('main');
  const [editDashboardId, setEditDashboardId] = useState<string | undefined>();
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleNavigate = (page: Page, dashboardId?: string) => {
    setCurrentPage(page);
    setEditDashboardId(dashboardId);
  };

  useEffect(() => {
    validateConnection();
  }, []);

  const validateConnection = async () => {
    try {
      setIsLoading(true);
      setError(null);
      await DynatraceAPI.validateConnection();
      setIsConnected(true);
    } catch (err) {
      setError('Failed to connect to Dynatrace. Please check your credentials.');
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
        <p>Connecting to Dynatrace...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>Dynatrace Metrics Dashboard</h1>
          <nav className="app-nav">
            <button
              className={`nav-button ${currentPage === 'main' ? 'active' : ''}`}
              onClick={() => setCurrentPage('main')}
            >
              Main Dashboard
            </button>
            <button
              className={`nav-button ${currentPage === 'saved' ? 'active' : ''}`}
              onClick={() => setCurrentPage('saved')}
            >
              Saved Dashboards
            </button>
            <button
              className={`nav-button ${currentPage === 'create' ? 'active' : ''}`}
              onClick={() => setCurrentPage('create')}
            >
              Create Dashboard
            </button>
            <button
              className={`nav-button ${currentPage === 'slo' ? 'active' : ''}`}
              onClick={() => setCurrentPage('slo')}
            >
              SLO / KPI
            </button>
          </nav>
          <div className="connection-status">
            <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      {error && (
        <div className="alert alert-danger">
          {error}
          <button onClick={validateConnection} className="retry-button">
            Retry Connection
          </button>
        </div>
      )}

      <main className="app-main">
        {currentPage === 'main' && <MainDashboard />}
        {currentPage === 'saved' && (
          <SavedDashboards onNavigate={handleNavigate} />
        )}
        {currentPage === 'create' && (
          <CreateDashboard onNavigate={handleNavigate} editDashboardId={editDashboardId} />
        )}
        {currentPage === 'slo' && <SLOManagement />}
      </main>
    </div>
  );
}

export default App;
