import { useState, useEffect } from 'react';
import { fetchSectorAnalysis } from '../api';
import type { SectorAnalysisData } from '../types';

interface Props {
  sectorKey: string;
  onClose: () => void;
  onStockClick: (symbol: string) => void;
}

export default function SectorAnalysisPanel({ sectorKey, onClose, onStockClick }: Props) {
  const [data, setData] = useState<SectorAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    fetchSectorAnalysis(sectorKey)
      .then(setData)
      .catch((err) => setError(err.response?.data?.error || err.message || 'Failed to load sector analysis'))
      .finally(() => setLoading(false));
  }, [sectorKey]);

  // ESC to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="modal-overlay show" onClick={onClose}>
      <div className="sector-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sector-modal-header">
          <h2>{data?.name || sectorKey}</h2>
          <button className="range-clear-btn" onClick={onClose}>✕</button>
        </div>

        {loading ? (
          <div className="sector-modal-body" style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <div className="range-spinner" />
          </div>
        ) : error ? (
          <div className="sector-modal-body">
            <div className="news-empty">{error}</div>
          </div>
        ) : data ? (
          <div className="sector-modal-body">
            {/* Outlook */}
            {data.outlook && (
              <div className="sector-section">
                <h3 className="range-section-title">📊 Outlook</h3>
                {data.outlook.short_term && (
                  <div className="sector-outlook-row">
                    <span className="sector-outlook-label">Short Term</span>
                    <span className="sector-outlook-text">
                      {data.outlook.short_term.view}
                      {data.outlook.short_term.score != null && (
                        <span className="sector-outlook-score"> ({data.outlook.short_term.score}/10)</span>
                      )}
                      {data.outlook.short_term.reason && (
                        <span className="sector-outlook-reason"> — {data.outlook.short_term.reason}</span>
                      )}
                    </span>
                  </div>
                )}
                {data.outlook.medium_term && (
                  <div className="sector-outlook-row">
                    <span className="sector-outlook-label">Medium Term</span>
                    <span className="sector-outlook-text">
                      {data.outlook.medium_term.view}
                      {data.outlook.medium_term.score != null && (
                        <span className="sector-outlook-score"> ({data.outlook.medium_term.score}/10)</span>
                      )}
                      {data.outlook.medium_term.reason && (
                        <span className="sector-outlook-reason"> — {data.outlook.medium_term.reason}</span>
                      )}
                    </span>
                  </div>
                )}
                {data.outlook.long_term && (
                  <div className="sector-outlook-row">
                    <span className="sector-outlook-label">Long Term</span>
                    <span className="sector-outlook-text">
                      {data.outlook.long_term.view}
                      {data.outlook.long_term.score != null && (
                        <span className="sector-outlook-score"> ({data.outlook.long_term.score}/10)</span>
                      )}
                      {data.outlook.long_term.reason && (
                        <span className="sector-outlook-reason"> — {data.outlook.long_term.reason}</span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Drivers */}
            {data.drivers && data.drivers.length > 0 && (
              <div className="sector-section">
                <h3 className="range-section-title">🚀 Drivers</h3>
                <ul className="range-events">
                  {data.drivers.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              </div>
            )}

            {/* Risks */}
            {data.risks && data.risks.length > 0 && (
              <div className="sector-section">
                <h3 className="range-section-title">⚠️ Risks</h3>
                <ul className="range-events">
                  {data.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}

            {/* Stocks */}
            {data.stocks && data.stocks.length > 0 && (
              <div className="sector-section">
                <h3 className="range-section-title">📈 Related Stocks</h3>
                <div className="sector-stocks-grid">
                  {(data.stocks || []).map((stock: any) => {
                    const stockSym = typeof stock === "string" ? stock : stock.symbol;
                    const stockName = typeof stock === "string" ? stock : stock.name;
                    // Handle stock_performance as array or record
                    let perfData: { price?: number; change_pct?: number; change?: number } | undefined;
                    if (data.stock_performance) {
                      if (Array.isArray(data.stock_performance)) {
                        perfData = data.stock_performance.find((p: any) => p.symbol === stockSym);
                      } else {
                        perfData = (data.stock_performance as any)[stockSym];
                      }
                    }
                    const changePct = perfData?.change_pct ?? 0;
                    const price = perfData?.price ?? undefined;
                    const change = perfData?.change;
                    const isUp = changePct >= 0;
                    return (
                      <div
                        key={stockSym}
                        className="sector-stock-card"
                        onClick={() => { onClose(); onStockClick(stockSym); }}
                      >
                        <div className="sector-stock-symbol">{stockSym}</div>
                        <div className="sector-stock-name">{stockName}</div>
                        {price != null && (
                          <div className="sector-stock-price">${price.toFixed(2)}</div>
                        )}
                        <div className={`sector-stock-change ${isUp ? 'up' : 'down'}`}>
                          {isUp ? '+' : ''}{changePct.toFixed(2)}%
                          {change != null && (
                            <span style={{ marginLeft: 4, fontSize: 10, opacity: 0.7 }}>
                              ({change >= 0 ? '+' : ''}{change.toFixed(2)})
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
