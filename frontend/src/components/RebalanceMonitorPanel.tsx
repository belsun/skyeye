import { useCallback, useEffect, useState } from 'react';
import { fetchRebalancePlan } from '../api';
import type { RebalancePlan } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function statusClass(status: string | undefined): string {
  return (status || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

export default function RebalanceMonitorPanel({ onStockClick }: Props) {
  const [data, setData] = useState<RebalancePlan | null>(null);
  const [capital, setCapital] = useState('100000');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback((value = Number(capital) || 100000) => {
    setLoading(true);
    setError('');
    fetchRebalancePlan(value)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Rebalance monitor unavailable'))
      .finally(() => setLoading(false));
  }, [capital]);

  useEffect(() => {
    load(100000);
  }, [load]);

  const apply = () => {
    const parsed = Number(capital);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    load(parsed);
  };

  if (error) {
    return (
      <div className="rebalance-monitor">
        <div className="rebalance-header">
          <span className="rebalance-title">Rebalance Monitor</span>
          <span className="rebalance-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rebalance-monitor">
        <div className="rebalance-header">
          <span className="rebalance-title">Rebalance Monitor</span>
          <span className="rebalance-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const rows = data.rows.filter((row) => row.status !== 'excluded').slice(0, 8);

  return (
    <div className={`rebalance-monitor rebalance-${statusClass(data.status)}`}>
      <div className="rebalance-header">
        <div>
          <span className="rebalance-title">Rebalance Monitor</span>
          <span className={`rebalance-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <div className="rebalance-capital">
          <input value={capital} onChange={(event) => setCapital(event.target.value)} inputMode="numeric" />
          <button onClick={apply} disabled={loading}>Apply</button>
        </div>
      </div>

      <div className="rebalance-message">{data.message}</div>

      <div className="rebalance-summary">
        <span><strong>{money(data.summary.actual_market_value)}</strong> Actual</span>
        <span><strong>{money(data.summary.live_target_notional)}</strong> Live Target</span>
        <span><strong>{money(data.summary.paper_target_notional)}</strong> Paper Target</span>
        <span><strong>{data.summary.off_gate}</strong> Off Gate</span>
      </div>

      <div className="rebalance-table-wrap">
        <table className="rebalance-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Status</th>
              <th>Actual</th>
              <th>Live Δ</th>
              <th>Paper Δ</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="rebalance-empty">No rebalance rows yet.</td>
              </tr>
            ) : rows.map((row) => (
              <tr key={row.symbol}>
                <td>
                  <button className="rebalance-symbol" onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                  <span>{money(row.latest_close)}</span>
                </td>
                <td><span className={`rebalance-badge ${statusClass(row.status)}`}>{row.label}</span></td>
                <td>
                  <strong>{money(row.actual_notional)}</strong>
                  <em>{pct(row.actual_weight)}</em>
                </td>
                <td className={row.live_delta_notional >= 0 ? 'up' : 'down'}>
                  <strong>{money(row.live_delta_notional)}</strong>
                  <em>{pct(row.live_delta_weight)}</em>
                </td>
                <td className={row.paper_delta_notional >= 0 ? 'up' : 'down'}>
                  <strong>{money(row.paper_delta_notional)}</strong>
                  <em>{pct(row.paper_delta_weight)}</em>
                </td>
                <td className="rebalance-reason">{row.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
