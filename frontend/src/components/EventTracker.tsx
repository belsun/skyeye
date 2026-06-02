import { useState, useEffect } from 'react';
import { fetchEvents } from '../api';
import type { EventsData, CalendarEvent, IPOItem, SupplyChainTheme } from '../types';

interface Props {
  onStockClick: (symbol: string) => void;
}

function getImpactColor(category: string): string {
  if (category.includes('政策') || category.includes('policy')) return '#f59e0b';
  if (category.includes('财报') || category.includes('earnings')) return '#10b981';
  if (category.includes('宏观') || category.includes('macro')) return '#3b82f6';
  if (category.includes('地缘') || category.includes('geo')) return '#ef4444';
  return '#8b5cf6';
}

export default function EventTracker({ onStockClick }: Props) {
  const [data, setData] = useState<EventsData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchEvents()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) return <div className="loading-placeholder">加载中...</div>;
  if (!data) return null;

  return (
    <div className="event-tracker">
      {/* Events */}
      <div className="events-list">
        {data.events.slice(0, 8).map((evt: CalendarEvent, i: number) => {
          const color = getImpactColor(evt.category);
          return (
            <div key={i} className="event-item" style={{ cursor: 'pointer' }}>
              <div className="event-header">
                <span className="event-category" style={{ color, borderColor: `${color}55` }}>
                  {evt.category}
                </span>
                <span className="event-date">{evt.date}</span>
              </div>
              <div
                className="event-title"
                style={{ cursor: 'pointer' }}
                onClick={() => window.open(`https://www.google.com/search?q=${encodeURIComponent(evt.title)}`, '_blank')}
                title="Google search"
              >
                {evt.title}
              </div>
              <div className="event-summary">{evt.summary}</div>
              {(evt.source || evt.watch_points?.length) && (
                <div className="event-watch-box">
                  {evt.source && <span>来源：{evt.source}</span>}
                  {evt.watch_points?.slice(0, 3).map((point) => (
                    <span key={point}>盯：{point}</span>
                  ))}
                </div>
              )}
              {evt.related_stocks && evt.related_stocks.length > 0 && (
                <div className="event-stocks">
                  {evt.related_stocks.map((sym) => (
                    <span
                      key={sym}
                      className="event-stock-tag"
                      onClick={(e) => { e.stopPropagation(); onStockClick(sym); }}
                      title={`Deep analysis: ${sym}`}
                    >
                      {sym}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* IPOs */}
      {data.ipos && data.ipos.length > 0 && (
        <div className="ipos-section">
          <div className="ipos-title">🚀 即将 IPO</div>
          {data.ipos.slice(0, 5).map((ipo: IPOItem, i: number) => (
            <div key={i} className="ipo-item">
              <div
                className="ipo-name"
                style={{ cursor: 'pointer' }}
                onClick={() => window.open(`https://www.google.com/search?q=${encodeURIComponent(ipo.name + ' IPO')}`, '_blank')}
                title="Google search"
              >
                {ipo.name}
              </div>
              <div className="ipo-meta">
                {ipo.status && <span>{ipo.status}</span>}
                <span>{ipo.expected_date}</span>
                <span>{ipo.sector}</span>
                <span className="ipo-valuation">{ipo.valuation}</span>
              </div>
              <div className="ipo-desc">{ipo.description}</div>
              {ipo.watch_points && ipo.watch_points.length > 0 && (
                <div className="event-watch-box">
                  {ipo.watch_points.slice(0, 4).map((point) => (
                    <span key={point}>盯：{point}</span>
                  ))}
                </div>
              )}
              {ipo.related_tickers && ipo.related_tickers.length > 0 && (
                <div className="event-stocks">
                  {ipo.related_tickers.map((sym) => (
                    <span key={sym} className="event-stock-tag" onClick={() => onStockClick(sym)} title={`Deep analysis: ${sym}`}>
                      {sym}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {data.supply_chains && data.supply_chains.length > 0 && (
        <div className="chain-section">
          <div className="ipos-title">风口产业链 / Supply Chain</div>
          {data.supply_chains.slice(0, 4).map((chain: SupplyChainTheme) => (
            <div key={chain.theme} className="chain-item">
              <div className="chain-top">
                <strong>{chain.theme}</strong>
                <span>{chain.trigger}</span>
              </div>
              <div className="chain-layers">
                <span>上游 {chain.upstream.slice(0, 3).join(' / ')}</span>
                <span>中游 {chain.midstream.slice(0, 3).join(' / ')}</span>
                <span>下游 {chain.downstream.slice(0, 3).join(' / ')}</span>
              </div>
              <div className="event-stocks">
                {[...chain.hk_tickers, ...chain.us_tickers].slice(0, 8).map((sym) => (
                  <span key={sym} className="event-stock-tag" onClick={() => onStockClick(sym)} title={`Deep analysis: ${sym}`}>
                    {sym}
                  </span>
                ))}
              </div>
              <div className="chain-risk">{chain.watch_signals.slice(0, 3).join(' · ')} · {chain.risk}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
