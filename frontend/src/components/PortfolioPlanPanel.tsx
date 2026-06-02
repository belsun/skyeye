import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchPortfolioPlan } from '../api';
import type { PortfolioAllocation, PortfolioPlan } from '../types';

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

function topReason(row: PortfolioAllocation): string {
  return row.reasons[0] || row.blockers[0] || row.label;
}

export default function PortfolioPlanPanel({ onStockClick }: Props) {
  const [data, setData] = useState<PortfolioPlan | null>(null);
  const [capital, setCapital] = useState(100000);
  const [pendingCapital, setPendingCapital] = useState('100000');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback((value: number) => {
    setLoading(true);
    setError('');
    fetchPortfolioPlan(value)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Portfolio plan unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(100000);
  }, [load]);

  const rows = useMemo(() => data?.allocations.slice(0, 8) || [], [data]);

  const applyCapital = () => {
    const parsed = Number(pendingCapital);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    setCapital(parsed);
    load(parsed);
  };

  if (error) {
    return (
      <div className="portfolio-plan">
        <div className="portfolio-header">
          <span className="portfolio-title">Portfolio Plan</span>
          <span className="portfolio-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="portfolio-plan">
        <div className="portfolio-header">
          <span className="portfolio-title">Portfolio Plan</span>
          <span className="portfolio-muted">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`portfolio-plan portfolio-${statusClass(data.status)}`}>
      <div className="portfolio-header">
        <div>
          <span className="portfolio-title">Portfolio Plan</span>
          <span className={`portfolio-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <div className="portfolio-capital">
          <input
            value={pendingCapital}
            inputMode="numeric"
            onChange={(event) => setPendingCapital(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') applyCapital(); }}
            aria-label="Portfolio capital"
          />
          <button onClick={applyCapital} disabled={loading}>Apply</button>
        </div>
      </div>

      <div className="portfolio-message">{data.message}</div>

      <div className="portfolio-summary">
        <span><strong>{money(data.capital)}</strong> Capital</span>
        <span><strong>{pct(data.summary.live_weight)}</strong> Live</span>
        <span><strong>{money(data.summary.live_notional)}</strong> Live $</span>
        <span><strong>{data.summary.watch_count}</strong> Watch</span>
        <span><strong>{pct(data.controls.max_position_risk_pct)}</strong> Max Risk</span>
      </div>

      <div className="portfolio-table-wrap">
        <table className="portfolio-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Status</th>
              <th>Live</th>
              <th>Paper</th>
              <th>Stop</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} onDoubleClick={() => onStockClick(row.symbol)}>
                <td>
                  <button className="portfolio-symbol" onClick={() => onStockClick(row.symbol)}>
                    {row.symbol}
                  </button>
                  <span className="portfolio-price">{money(row.latest_close)}</span>
                </td>
                <td>
                  <span className={`portfolio-badge ${statusClass(row.allocation_status)}`}>{row.label}</span>
                </td>
                <td>
                  <span className="portfolio-weight">{pct(row.live_weight)}</span>
                  <em>{money(row.live_notional)}</em>
                </td>
                <td>
                  <span className="portfolio-weight">{pct(row.paper_weight)}</span>
                  <em>{money(row.paper_notional)}</em>
                </td>
                <td>{pct(row.stop_distance_pct)}</td>
                <td className="portfolio-reason">{topReason(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
