import { useCallback, useEffect, useState } from 'react';
import { fetchInvestmentBrief } from '../api';
import type { InvestmentBrief } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function pct(value: number | null | undefined, digits = 0): string {
  return value == null ? '-' : `${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function statusClass(value: string | undefined | null): string {
  return (value || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
}

export default function InvestmentBriefPanel({ onStockClick }: Props) {
  const [data, setData] = useState<InvestmentBrief | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    fetchInvestmentBrief()
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Investment brief unavailable'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="investment-brief">
        <div className="investment-header">
          <span className="investment-title">Investment Brief</span>
          <span className="investment-error">{error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="investment-brief">
        <div className="investment-header">
          <span className="investment-title">Investment Brief</span>
          <span className="investment-muted">Loading...</span>
        </div>
      </div>
    );
  }

  const priorities = data.priorities.slice(0, 4);
  const queue = data.research_queue.slice(0, 5);
  const allocations = data.allocation_snapshot.slice(0, 4);

  return (
    <div className={`investment-brief investment-${statusClass(data.status)}`}>
      <div className="investment-header">
        <div>
          <span className="investment-title">Investment Brief</span>
          <span className={`investment-status ${statusClass(data.status)}`}>{data.label}</span>
          <span className="investment-mode">{data.mode}</span>
        </div>
        <button className="investment-refresh" onClick={load} disabled={loading}>Refresh</button>
      </div>

      <div className="investment-message">{data.message}</div>

      <div className="investment-summary">
        <span><strong>{data.summary.live_ready_horizons}</strong> Ready</span>
        <span><strong>{data.summary.watch_horizons}</strong> Watch</span>
        <span><strong>{pct(data.summary.live_weight)}</strong> Live</span>
        <span><strong>{pct(data.summary.paper_weight)}</strong> Paper</span>
        <span><strong>{data.summary.top_symbol || '-'}</strong> Top</span>
      </div>

      <div className="investment-content">
        <div className="investment-main">
          <div className="investment-block-title">Priority Queue</div>
          <div className="investment-priorities">
            {priorities.length === 0 ? (
              <div className="investment-empty">No priority items.</div>
            ) : priorities.map((item) => (
              <div className={`investment-priority ${statusClass(item.priority)}`} key={`${item.source}-${item.title}-${item.symbol || ''}`}>
                <div className="investment-priority-top">
                  <span className={`investment-priority-badge ${statusClass(item.priority)}`}>{item.priority}</span>
                  <span>{item.category}</span>
                  {item.symbol && (
                    <button onClick={() => onStockClick(item.symbol || '')}>{item.symbol}</button>
                  )}
                </div>
                <strong>{item.title}</strong>
                <p>{item.message}</p>
                <em>{item.action}</em>
                {item.evidence.length > 0 && (
                  <div className="investment-evidence">
                    {item.evidence.slice(0, 3).map((evidence) => (
                      <span key={evidence}>{evidence}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="investment-side">
          <div>
            <div className="investment-block-title">Research Queue</div>
            <div className="investment-research-list">
              {queue.map((row) => (
                <div className="investment-research-row" key={row.symbol}>
                  <button onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                  <span>{row.label}</span>
                  <strong>{row.score}</strong>
                  <em className={statusClass(row.strategy_status)}>{row.strategy_status || '-'}</em>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="investment-block-title">Paper Snapshot</div>
            <div className="investment-allocation-list">
              {allocations.length === 0 ? (
                <div className="investment-empty">No allocation rows.</div>
              ) : allocations.map((row) => (
                <div className="investment-allocation-row" key={row.symbol}>
                  <button onClick={() => onStockClick(row.symbol)}>{row.symbol}</button>
                  <span>{row.label}</span>
                  <strong>{pct(row.paper_weight, 1)}</strong>
                  <em>{money(row.paper_notional)}</em>
                </div>
              ))}
            </div>
          </div>

          <div className="investment-notes">
            {data.notes.slice(0, 4).map((note) => (
              <span key={note}>{note}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
