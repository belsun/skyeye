import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchDecisionBoard } from '../api';
import type { DecisionBoard, DecisionBoardRow } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  return value == null ? '-' : `$${value.toFixed(2)}`;
}

function statusClass(status: string | undefined): string {
  return (status || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

function gateSummary(row: DecisionBoardRow): string {
  if (!row.gates.length) return '-';
  return row.gates
    .map((gate) => `${gate.horizon.toUpperCase()} ${gate.gate_label || gate.gate_status || '-'}`)
    .join(' / ');
}

export default function DecisionBoardPanel({ onStockClick }: Props) {
  const [data, setData] = useState<DecisionBoard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeSymbol, setActiveSymbol] = useState<string>('');

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchDecisionBoard()
      .then((result) => {
        setData(result);
        setActiveSymbol((current) => current || result.rows[0]?.symbol || '');
      })
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Decision board unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const activeRow = useMemo(() => {
    if (!data?.rows.length) return null;
    return data.rows.find((row) => row.symbol === activeSymbol) || data.rows[0];
  }, [activeSymbol, data]);

  if (error) {
    return (
      <div className="decision-board">
        <div className="decision-header">
          <span className="decision-title">Decision Board</span>
          <span className="decision-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="decision-board decision-loading">
        <div className="decision-header">
          <span className="decision-title">Decision Board</span>
          <span className="decision-muted">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="decision-board">
      <div className="decision-header">
        <div>
          <span className="decision-title">Decision Board</span>
          <span className="decision-muted">{data.lookback_days}D signals</span>
        </div>
        <button className="decision-refresh" onClick={load} disabled={loading} title="Refresh">
          Refresh
        </button>
      </div>

      <div className="decision-summary">
        <span><strong>{data.summary.total}</strong> Universe</span>
        <span><strong>{data.summary.candidates}</strong> Candidate</span>
        <span><strong>{data.summary.watch}</strong> Watch</span>
        <span><strong>{data.summary.blocked}</strong> Blocked</span>
        <span><strong>{data.summary.best_symbol || '-'}</strong> Top</span>
      </div>

      <div className="decision-content">
        <div className="decision-table-wrap">
          <table className="decision-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Symbol</th>
                <th>Status</th>
                <th>Score</th>
                <th>Trend</th>
                <th>Sentiment</th>
                <th>Risk</th>
                <th>Gate</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr
                  key={row.symbol}
                  className={activeRow?.symbol === row.symbol ? 'active' : ''}
                  onClick={() => setActiveSymbol(row.symbol)}
                  onDoubleClick={() => onStockClick(row.symbol)}
                >
                  <td className="mono">#{row.rank}</td>
                  <td>
                    <span className="decision-symbol">{row.symbol}</span>
                    <span className="decision-price">{money(row.latest_close)}</span>
                  </td>
                  <td>
                    <span className={`decision-badge ${statusClass(row.decision_status)}`}>{row.label}</span>
                  </td>
                  <td>
                    <div className="decision-score">
                      <span>{row.score}</span>
                      <div className="decision-score-bar">
                        <i style={{ width: `${row.score}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className={(row.trend_20d ?? 0) >= 0 ? 'up mono' : 'down mono'}>
                    {pct(row.trend_20d)}
                  </td>
                  <td className={(row.sentiment_ratio_30d ?? 0) >= 0 ? 'up mono' : 'down mono'}>
                    {pct(row.sentiment_ratio_30d)}
                    <span className="decision-mini"> {row.news_count_30d}n</span>
                  </td>
                  <td className="mono">{pct(row.annualized_volatility_20d)}</td>
                  <td className="decision-gate-cell">{gateSummary(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {activeRow && (
          <div className="decision-detail">
            <div className="decision-detail-top">
              <div>
                <span className="decision-detail-symbol">{activeRow.symbol}</span>
                <span className={`decision-badge ${statusClass(activeRow.decision_status)}`}>{activeRow.label}</span>
              </div>
              <button className="decision-open" onClick={() => onStockClick(activeRow.symbol)}>
                Open
              </button>
            </div>
            <div className="decision-action">{activeRow.action}</div>
            <div className="decision-detail-grid">
              <span>Data <strong>{activeRow.data_quality_label}</strong></span>
              <span>Drawdown <strong className={(activeRow.drawdown_60d ?? 0) < -0.12 ? 'down' : ''}>{pct(activeRow.drawdown_60d)}</strong></span>
              <span>ATR <strong>{pct(activeRow.atr_pct)}</strong></span>
              <span>Labels <strong>{activeRow.coverage.analyzed_news}</strong></span>
            </div>
            {activeRow.blockers.length > 0 && (
              <div className="decision-tags">
                {activeRow.blockers.slice(0, 5).map((blocker) => (
                  <span key={blocker}>{blocker}</span>
                ))}
              </div>
            )}
            {activeRow.headlines.length > 0 && (
              <div className="decision-headlines">
                {activeRow.headlines.slice(0, 2).map((headline) => (
                  <div key={`${headline.date}-${headline.title}`} className={`decision-headline ${headline.sentiment}`}>
                    <span>{headline.date}</span>
                    <strong>{headline.title}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
