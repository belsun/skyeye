import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchPaperPerformance } from '../api';
import type { PaperPerformance } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

const WINDOWS = [5, 20, 60];

function pct(value: number | null | undefined, digits = 1, signed = false): string {
  if (value == null) return '-';
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function statusClass(value: string | undefined | null): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

function valueClass(value: number | null | undefined): string {
  if (value == null || Math.abs(value) < 0.00005) return 'flat';
  return value > 0 ? 'up' : 'down';
}

export default function PaperPerformancePanel({ onStockClick }: Props) {
  const [data, setData] = useState<PaperPerformance | null>(null);
  const [windowDays, setWindowDays] = useState(60);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback((days: number) => {
    setLoading(true);
    setError('');
    fetchPaperPerformance(100000, days)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Paper performance unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(60);
  }, [load]);

  const switchWindow = (days: number) => {
    setWindowDays(days);
    load(days);
  };

  const curveScale = useMemo(() => {
    const points = data?.curve || [];
    const values = points.map((point) => point.paper_value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    return { min: Number.isFinite(min) ? min : 0, max: Number.isFinite(max) ? max : 0 };
  }, [data]);

  if (error) {
    return (
      <div className="paper-performance">
        <div className="paper-header">
          <span className="paper-title">Paper Performance</span>
          <span className="paper-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="paper-performance">
        <div className="paper-header">
          <span className="paper-title">Paper Performance</span>
          <span className="paper-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const range = Math.max(curveScale.max - curveScale.min, 1);
  const contributions = data.contributions.slice(0, 6);

  return (
    <div className={`paper-performance paper-${statusClass(data.status)}`}>
      <div className="paper-header">
        <div>
          <span className="paper-title">Paper Performance</span>
          <span className={`paper-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <div className="paper-window-tabs">
          {WINDOWS.map((days) => (
            <button
              key={days}
              className={windowDays === days ? 'active' : ''}
              onClick={() => switchWindow(days)}
              disabled={loading}
            >
              {days}D
            </button>
          ))}
        </div>
      </div>

      <div className="paper-message">{data.message}</div>

      <div className="paper-summary">
        <span><strong className={valueClass(data.summary.total_return)}>{pct(data.summary.total_return, 1, true)}</strong> Paper</span>
        <span><strong>{pct(data.summary.benchmark_return, 1, true)}</strong> Equal Wt</span>
        <span><strong className={valueClass(data.summary.active_return)}>{pct(data.summary.active_return, 1, true)}</strong> Active</span>
        <span><strong className={valueClass(data.summary.max_drawdown)}>{pct(data.summary.max_drawdown, 1)}</strong> Max DD</span>
        <span><strong>{pct(data.summary.annualized_volatility, 1)}</strong> Vol</span>
      </div>

      <div className="paper-grid">
        <div className="paper-block">
          <div className="paper-block-title">Static Paper Equity</div>
          <div className="paper-curve">
            {data.curve.length === 0 ? (
              <span className="paper-empty">No curve yet.</span>
            ) : data.curve.map((point) => {
              const height = 12 + ((point.paper_value - curveScale.min) / range) * 36;
              return (
                <span
                  key={point.date}
                  className={valueClass(point.paper_return)}
                  style={{ height: `${height}px` }}
                  title={`${point.date} ${money(point.paper_value)} ${pct(point.paper_return, 1, true)}`}
                />
              );
            })}
          </div>
          <div className="paper-window-list">
            {data.windows.map((row) => (
              <div className="paper-window-row" key={row.window_days}>
                <span>{row.window_days}D</span>
                <strong className={valueClass(row.total_return)}>{pct(row.total_return, 1, true)}</strong>
                <em>vs {pct(row.benchmark_return, 1, true)}</em>
                <b className={valueClass(row.active_return)}>{pct(row.active_return, 1, true)}</b>
              </div>
            ))}
          </div>
        </div>

        <div className="paper-block">
          <div className="paper-block-title">Contribution</div>
          <div className="paper-table-wrap">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Weight</th>
                  <th>Return</th>
                  <th>Contrib</th>
                  <th>Notional</th>
                </tr>
              </thead>
              <tbody>
                {contributions.length === 0 ? (
                  <tr><td colSpan={5} className="paper-empty">No contribution rows.</td></tr>
                ) : contributions.map((row) => (
                  <tr key={row.symbol} onDoubleClick={() => onStockClick(row.symbol)}>
                    <td>
                      <button className="paper-symbol" onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                      <span>{row.label || row.allocation_status || '-'}</span>
                    </td>
                    <td>{pct(row.weight, 1)}</td>
                    <td className={valueClass(row.total_return)}>{pct(row.total_return, 1, true)}</td>
                    <td className={valueClass(row.contribution)}>{pct(row.contribution, 1, true)}</td>
                    <td>{money(row.paper_notional)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
