import { useCallback, useEffect, useState } from 'react';
import { fetchStrategyMonitor } from '../api';
import type { StrategyMonitor } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pp(value: number | null | undefined): string {
  return value == null ? '-' : `${(value * 100).toFixed(1)}pp`;
}

function pct(value: number | null | undefined): string {
  return value == null ? '-' : `${(value * 100).toFixed(0)}%`;
}

function statusClass(value: string | undefined): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

function sourceLabel(source: string, modelSymbol: string): string {
  return source === 'symbol' ? 'Direct' : `${modelSymbol} fallback`;
}

export default function StrategyMonitorPanel({ onStockClick }: Props) {
  const [data, setData] = useState<StrategyMonitor | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchStrategyMonitor()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Strategy monitor unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="strategy-monitor">
        <div className="strategy-header">
          <span className="strategy-title">Strategy Monitor</span>
          <span className="strategy-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="strategy-monitor">
        <div className="strategy-header">
          <span className="strategy-title">Strategy Monitor</span>
          <span className="strategy-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const rows = data.rows
    .filter((row) => row.symbol === 'UNIFIED' || row.horizon === 't1')
    .slice(0, 12);
  const primaryAction = data.actions[0];

  return (
    <div className={`strategy-monitor strategy-${statusClass(data.status)}`}>
      <div className="strategy-header">
        <div>
          <span className="strategy-title">Strategy Monitor</span>
          <span className={`strategy-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="strategy-refresh" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="strategy-message">{data.message}</div>

      <div className="strategy-summary">
        <span><strong>{data.summary.ready}</strong> Ready</span>
        <span><strong>{data.summary.watch}</strong> Watch</span>
        <span><strong>{data.summary.blocked}</strong> Blocked</span>
        <span><strong>{data.summary.unified_fallback}</strong> Fallback</span>
        <span><strong>{pp(data.summary.best_cv_lift)}</strong> Best CV</span>
      </div>

      <div className="strategy-content">
        <div className="strategy-table-wrap">
          <table className="strategy-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>H</th>
                <th>Status</th>
                <th>Source</th>
                <th>CV Lift</th>
                <th>Strict Edge</th>
                <th>Data</th>
                <th>Driver</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.symbol}-${row.horizon}`}>
                  <td>
                    {row.symbol === 'UNIFIED' ? (
                      <span className="strategy-symbol">UNIFIED</span>
                    ) : (
                      <button className="strategy-symbol-button" onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                    )}
                    <span>{row.model_age_days == null ? '-' : `${row.model_age_days}d old`}</span>
                  </td>
                  <td className="mono">{row.horizon.toUpperCase()}</td>
                  <td><span className={`strategy-badge ${statusClass(row.status)}`}>{row.label}</span></td>
                  <td>{sourceLabel(row.source, row.model_symbol)}</td>
                  <td className={(row.cv_lift ?? -1) > 0 ? 'up mono' : 'down mono'}>{pp(row.cv_lift)}</td>
                  <td className={(row.strict_strategy_excess_return ?? -1) > 0 ? 'up mono' : 'down mono'}>{pct(row.strict_strategy_excess_return)}</td>
                  <td>{row.coverage_label || '-'}</td>
                  <td>{row.top_driver_group || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="strategy-side">
          {primaryAction ? (
            <div className={`strategy-action ${statusClass(primaryAction.priority)}`}>
              <span className={`strategy-priority ${statusClass(primaryAction.priority)}`}>{primaryAction.priority}</span>
              <strong>{primaryAction.title}</strong>
              <p>{primaryAction.message}</p>
              <em>{primaryAction.action}</em>
              <div className="strategy-evidence">
                {primaryAction.evidence.slice(0, 3).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </div>
          ) : (
            <div className="strategy-action low">
              <span className="strategy-priority low">low</span>
              <strong>Monitor Clean</strong>
              <p>No immediate model-readiness action.</p>
              <em>Keep paper tracking and periodic backtests.</em>
            </div>
          )}

          <div className="strategy-notes">
            {data.rows
              .filter((row) => row.issues.length > 0)
              .slice(0, 4)
              .map((row) => (
                <div key={`${row.symbol}-${row.horizon}-issue`}>
                  <strong>{row.symbol} {row.horizon.toUpperCase()}</strong>
                  <span>{row.issues.slice(0, 2).join(' · ')}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
