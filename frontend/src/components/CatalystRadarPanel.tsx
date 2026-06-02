import { useCallback, useEffect, useState } from 'react';
import { fetchCatalystRadar } from '../api';
import type { CatalystRadar, CatalystRow } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pct(value: number | null | undefined, digits = 1, signed = false): string {
  if (value == null) return '-';
  const sign = signed && value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function statusClass(value: string | undefined | null): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

function valueClass(value: number | null | undefined): string {
  if (value == null || Math.abs(value) < 0.00005) return 'flat';
  return value > 0 ? 'up' : 'down';
}

function topHeadline(row: CatalystRow): string {
  return row.headlines[0]?.title || row.message;
}

export default function CatalystRadarPanel({ onStockClick }: Props) {
  const [data, setData] = useState<CatalystRadar | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchCatalystRadar()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Catalyst radar unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="catalyst-radar">
        <div className="catalyst-header">
          <span className="catalyst-title">Catalyst Radar</span>
          <span className="catalyst-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="catalyst-radar">
        <div className="catalyst-header">
          <span className="catalyst-title">Catalyst Radar</span>
          <span className="catalyst-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const rows = data.rows.slice(0, 6);
  const spotlight = rows[0];

  return (
    <div className={`catalyst-radar catalyst-${statusClass(data.status)}`}>
      <div className="catalyst-header">
        <div>
          <span className="catalyst-title">Catalyst Radar</span>
          <span className={`catalyst-status ${statusClass(data.status)}`}>{data.label}</span>
        </div>
        <button className="catalyst-refresh" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="catalyst-message">{data.message}</div>

      <div className="catalyst-summary">
        <span><strong>{data.summary.hot}</strong> Hot</span>
        <span><strong>{data.summary.total_articles}</strong> Articles</span>
        <span><strong>{data.summary.bullish}</strong> Bullish</span>
        <span><strong>{data.summary.bearish}</strong> Bearish</span>
        <span><strong>{data.summary.pending_labels}</strong> Pending</span>
      </div>

      <div className="catalyst-grid">
        <div className="catalyst-spotlight">
          {spotlight ? (
            <>
              <div className="catalyst-spotlight-top">
                <button onClick={() => onStockClick(spotlight.symbol)}>{spotlight.symbol}</button>
                <span className={`catalyst-bias ${statusClass(spotlight.bias)}`}>{spotlight.bias_label}</span>
                <strong>{spotlight.score}</strong>
              </div>
              <div className="catalyst-spotlight-headline">{topHeadline(spotlight)}</div>
              <div className="catalyst-spotlight-action">{spotlight.action}</div>
              <div className="catalyst-chip-row">
                <span>{spotlight.news_count} articles</span>
                <span>{pct(spotlight.sentiment_ratio, 0, true)} sentiment</span>
                <span>{pct(spotlight.avg_abs_ret_t0, 1)} t0 reaction</span>
                <span>{pct(spotlight.trend_5d, 1, true)} 5D</span>
              </div>
            </>
          ) : (
            <div className="catalyst-empty">No active catalysts.</div>
          )}
        </div>

        <div className="catalyst-table-wrap">
          <table className="catalyst-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Score</th>
                <th>Bias</th>
                <th>News</th>
                <th>Reaction</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.symbol} onDoubleClick={() => onStockClick(row.symbol)}>
                  <td>
                    <button className="catalyst-symbol" onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                    <span>{money(row.latest_close)}</span>
                  </td>
                  <td><strong>{row.score}</strong></td>
                  <td>
                    <span className={`catalyst-bias ${statusClass(row.bias)}`}>{row.bias_label}</span>
                  </td>
                  <td>
                    <strong>{row.news_count}</strong>
                    <span>{row.positive}/{row.negative} pos/neg</span>
                  </td>
                  <td className={valueClass(row.avg_ret_t0)}>
                    {pct(row.avg_abs_ret_t0, 1)}
                    <span>{pct(row.avg_ret_t0, 1, true)} avg</span>
                  </td>
                  <td className={valueClass(row.trend_5d)}>
                    {pct(row.trend_5d, 1, true)}
                    <span>{pct(row.trend_20d, 1, true)} 20D</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
