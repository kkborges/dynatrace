import React, { useState } from 'react';
import './SLOManagement.css';

interface SLO {
  id: string;
  name: string;
  metric: string;
  target: number;
  warning: number;
  description: string;
  category: 'availability' | 'performance' | 'reliability' | 'custom';
}

const EXAMPLE_SLOS: SLO[] = [
  {
    id: 'slo-001',
    name: 'Disponibilidade de Host',
    metric: 'builtin:host.availability',
    target: 99.9,
    warning: 99.5,
    description: 'Objetivo de disponibilidade para todos os hosts gerenciados',
    category: 'availability',
  },
  {
    id: 'slo-002',
    name: 'Disponibilidade de Serviço',
    metric: 'builtin:service.requestCount.total',
    target: 99.5,
    warning: 99.0,
    description: 'Objetivo de disponibilidade para serviços críticos',
    category: 'availability',
  },
  {
    id: 'slo-003',
    name: 'Latência de Resposta P95',
    metric: 'builtin:service.response.time',
    target: 200,
    warning: 300,
    description: 'P95 da latência de resposta em milissegundos',
    category: 'performance',
  },
  {
    id: 'slo-004',
    name: 'Taxa de Erro',
    metric: 'builtin:service.errors.total.rate',
    target: 0.5,
    warning: 1.0,
    description: 'Taxa máxima de erro por segundo',
    category: 'reliability',
  },
  {
    id: 'slo-005',
    name: 'Utilização de CPU',
    metric: 'builtin:host.cpu.usage',
    target: 80,
    warning: 85,
    description: 'Limite máximo de utilização de CPU',
    category: 'performance',
  },
  {
    id: 'slo-006',
    name: 'Utilização de Memória',
    metric: 'builtin:host.mem.usage',
    target: 85,
    warning: 90,
    description: 'Limite máximo de utilização de memória',
    category: 'performance',
  },
];

export const SLOManagement: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<'availability' | 'performance' | 'reliability' | 'custom'>('availability');
  const [slos, setSlos] = useState<SLO[]>(EXAMPLE_SLOS);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newSLO, setNewSLO] = useState<Partial<SLO>>({});
  const [selectedSLO, setSelectedSLO] = useState<SLO | null>(null);

  const filteredSlos = slos.filter(slo => slo.category === selectedCategory);

  const handleAddSLO = () => {
    if (newSLO.name && newSLO.metric && newSLO.target) {
      const slo: SLO = {
        id: `slo-${Date.now()}`,
        name: newSLO.name,
        metric: newSLO.metric,
        target: newSLO.target,
        warning: newSLO.warning || newSLO.target * 0.95,
        description: newSLO.description || '',
        category: selectedCategory,
      };
      setSlos([...slos, slo]);
      setNewSLO({});
      setIsAddingNew(false);
    }
  };

  const handleDeleteSLO = (id: string) => {
    setSlos(slos.filter(slo => slo.id !== id));
    setSelectedSLO(null);
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      availability: 'Disponibilidade',
      performance: 'Performance',
      reliability: 'Confiabilidade',
      custom: 'Customizado',
    };
    return labels[category] || category;
  };

  const getStatusColor = (current: number, target: number, warning: number) => {
    if (current >= target) return 'success';
    if (current >= warning) return 'warning';
    return 'danger';
  };

  return (
    <div className="slo-management">
      <div className="slo-header">
        <div className="header-content">
          <h1>Gestão de SLOs / KPIs / SREs / SLAs</h1>
          <p>Configure e monitore seus Objetivos de Nível de Serviço</p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setIsAddingNew(!isAddingNew)}
        >
          {isAddingNew ? '✕ Cancelar' : '+ Adicionar SLO'}
        </button>
      </div>

      <div className="slo-content">
        <aside className="slo-sidebar">
          <h3>Categorias</h3>
          <nav className="category-nav">
            {['availability', 'performance', 'reliability', 'custom'].map((cat) => (
              <button
                key={cat}
                className={`category-btn ${selectedCategory === cat ? 'active' : ''}`}
                onClick={() => {
                  setSelectedCategory(cat as any);
                  setIsAddingNew(false);
                }}
              >
                {getCategoryLabel(cat)}
                <span className="count">
                  {slos.filter(s => s.category === cat).length}
                </span>
              </button>
            ))}
          </nav>

          <div className="sidebar-info">
            <h4>Próximos Passos</h4>
            <ol>
              <li>Configure seus SLOs</li>
              <li>Crie um token no Dynatrace</li>
              <li>Integre com APIs de SLO</li>
              <li>Configure alertas</li>
            </ol>
          </div>
        </aside>

        <main className="slo-main">
          {isAddingNew ? (
            <div className="slo-form">
              <h3>Novo SLO - {getCategoryLabel(selectedCategory)}</h3>
              <div className="form-group">
                <label>Nome do SLO</label>
                <input
                  type="text"
                  value={newSLO.name || ''}
                  onChange={(e) => setNewSLO({ ...newSLO, name: e.target.value })}
                  placeholder="Ex: Disponibilidade de Host"
                />
              </div>

              <div className="form-group">
                <label>Métrica Dynatrace</label>
                <input
                  type="text"
                  value={newSLO.metric || ''}
                  onChange={(e) => setNewSLO({ ...newSLO, metric: e.target.value })}
                  placeholder="Ex: builtin:host.availability"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Alvo (%/ms)</label>
                  <input
                    type="number"
                    value={newSLO.target || ''}
                    onChange={(e) => setNewSLO({ ...newSLO, target: parseFloat(e.target.value) })}
                    placeholder="99.9"
                    step="0.1"
                  />
                </div>
                <div className="form-group">
                  <label>Aviso (%/ms)</label>
                  <input
                    type="number"
                    value={newSLO.warning || ''}
                    onChange={(e) => setNewSLO({ ...newSLO, warning: parseFloat(e.target.value) })}
                    placeholder="99.5"
                    step="0.1"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Descrição</label>
                <textarea
                  value={newSLO.description || ''}
                  onChange={(e) => setNewSLO({ ...newSLO, description: e.target.value })}
                  placeholder="Descrição do objetivo"
                  rows={3}
                />
              </div>

              <button className="btn-success" onClick={handleAddSLO}>
                Criar SLO
              </button>
            </div>
          ) : (
            <div className="slo-list">
              <h3>{getCategoryLabel(selectedCategory)}</h3>

              {filteredSlos.length === 0 ? (
                <div className="empty-state">
                  <p>Nenhum SLO nesta categoria.</p>
                  <button onClick={() => setIsAddingNew(true)}>
                    Crie o primeiro SLO
                  </button>
                </div>
              ) : (
                <div className="slo-grid">
                  {filteredSlos.map((slo) => (
                    <div
                      key={slo.id}
                      className={`slo-card ${selectedSLO?.id === slo.id ? 'selected' : ''}`}
                      onClick={() => setSelectedSLO(slo)}
                    >
                      <div className="slo-card-header">
                        <h4>{slo.name}</h4>
                        <button
                          className="btn-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteSLO(slo.id);
                          }}
                        >
                          ✕
                        </button>
                      </div>

                      <p className="slo-metric">{slo.metric}</p>

                      <div className="slo-targets">
                        <div className="target-item">
                          <span className="label">Alvo</span>
                          <span className="value">{slo.target}</span>
                        </div>
                        <div className="target-item">
                          <span className="label">Aviso</span>
                          <span className="value">{slo.warning}</span>
                        </div>
                      </div>

                      {slo.description && (
                        <p className="slo-description">{slo.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {selectedSLO && !isAddingNew && (
            <div className="slo-details">
              <h3>Detalhes do SLO</h3>
              <div className="details-content">
                <div className="detail-item">
                  <span className="label">Nome:</span>
                  <span className="value">{selectedSLO.name}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Métrica:</span>
                  <span className="value">{selectedSLO.metric}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Categoria:</span>
                  <span className="value">{getCategoryLabel(selectedSLO.category)}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Alvo:</span>
                  <span className="value">{selectedSLO.target}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Aviso:</span>
                  <span className="value">{selectedSLO.warning}</span>
                </div>
                {selectedSLO.description && (
                  <div className="detail-item">
                    <span className="label">Descrição:</span>
                    <span className="value">{selectedSLO.description}</span>
                  </div>
                )}

                <div className="detail-actions">
                  <button className="btn-secondary">
                    📝 Editar
                  </button>
                  <button
                    className="btn-danger"
                    onClick={() => handleDeleteSLO(selectedSLO.id)}
                  >
                    🗑️ Deletar
                  </button>
                  <button className="btn-primary">
                    ⚙️ Configurar Token
                  </button>
                </div>

                <div className="token-info">
                  <p>
                    <strong>Nota:</strong> Para integrar este SLO com o Dynatrace,
                    você precisará criar um token de API no seu ambiente Dynatrace
                    e configurá-lo nesta interface.
                  </p>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
