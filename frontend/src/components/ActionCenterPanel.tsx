import { useCallback, useEffect, useState } from 'react';
import { fetchActionCenter } from '../api';
import type { ActionCenter } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function statusClass(value: string | undefined): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

export default function ActionCenterPanel({ onStockClick }: Props) {
  const [data, setData] = useState<ActionCenter | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchActionCenter()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Action center unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="action-center">
        <div className="action-center-header">
          <span className="action-center-title">Action Center</span>
          <span className="action-center-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="action-center">
        <div className="action-center-header">
          <span className="action-center-title">Action Center</span>
          <span className="action-center-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const visible = data.actions.slice(0, 5);

  return (
    <div className={`action-center action-center-${statusClass(data.status)}`}>
      <div className="action-center-header">
        <div>
          <span className="action-center-title">Action Center</span>
          <span className={`action-center-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="action-center-refresh" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="action-center-message">{data.message}</div>

      <div className="action-center-summary">
        <span><strong>{data.summary.total}</strong> Items</span>
        <span><strong>{data.summary.high + data.summary.critical}</strong> High</span>
        <span><strong>{data.summary.medium}</strong> Medium</span>
        <span><strong>{data.summary.decision_best_symbol || '-'}</strong> Top</span>
      </div>

      <div className="action-center-list">
        {visible.length === 0 ? (
          <div className="action-center-empty">No action items.</div>
        ) : visible.map((item) => (
          <div className={`action-item ${statusClass(item.priority)}`} key={item.key}>
            <div className="action-item-top">
              <span className={`action-priority ${statusClass(item.priority)}`}>{item.priority}</span>
              <span className="action-category">{item.category}</span>
              {item.symbol && (
                <button className="action-symbol" onClick={() => onStockClick(item.symbol || '')}>
                  {item.symbol}
                </button>
              )}
            </div>
            <div className="action-title">{item.title}</div>
            <div className="action-message">{item.message}</div>
            <div className="action-next">{item.action}</div>
            {item.evidence.length > 0 && (
              <div className="action-evidence">
                {item.evidence.slice(0, 3).map((evidence) => (
                  <span key={evidence}>{evidence}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
