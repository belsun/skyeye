import { useState, useEffect } from 'react';
import axios from 'axios';

interface StockData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

interface SectorData {
  key: string;
  name: string;
  icon: string;
  change_pct: number;
  leader: StockData | null;
  stocks: StockData[];
}

interface Props {
  market: string;
  label: string;
  onStockClick: (symbol: string) => void;
}

function getHeatColor(pct: number): string {
  if (pct >= 2) return '#10b981';
  if (pct >= 0.5) return '#16a34a';
  if (pct >= 0.1) return '#22c55e';
  if (pct >= -0.1) return '#374151';
  if (pct >= -0.5) return '#f97316';
  if (pct >= -2) return '#ef4444';
  return '#dc2626';
}

export default function MarketSectorHeatmap({ market, label, onStockClick }: Props) {
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    axios.get(`/api/market-sectors/${market}`)
      .then(res => setSectors(res.data.sectors || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [market]);

  if (loading) return <div className="loading-placeholder">加载中...</div>;
  if (sectors.length === 0) return null;

  return (
    <div className="section">
      <div className="section-title">📊 {label} 板块热力图</div>
      <div className="heatmap-grid">
        {sectors.map(sector => {
          const color = getHeatColor(sector.change_pct);
          const isExpanded = expanded === sector.key;
          return (
            <div key={sector.key} style={{ position: 'relative' }}>
              <div
                className="heatmap-tile"
                style={{ backgroundColor: `${color}33`, borderColor: `${color}88` }}
                onClick={() => setExpanded(isExpanded ? null : sector.key)}
              >
                <span className="heatmap-icon">{sector.icon}</span>
                <span className="heatmap-name">{sector.name}</span>
                <span className="heatmap-pct" style={{ color }}>
                  {sector.change_pct >= 0 ? '+' : ''}{sector.change_pct.toFixed(2)}%
                </span>
                {sector.leader && (
                  <div className="heatmap-leader">
                    <span className="leader-symbol">{sector.leader.symbol.replace(/\.\w+$/, '')}</span>
                    <span className="leader-price">${sector.leader.price}</span>
                    <span className="leader-change" style={{ color: sector.leader.change_pct >= 0 ? '#10b981' : '#ef4444' }}>
                      {sector.leader.change_pct >= 0 ? '+' : ''}{sector.leader.change_pct.toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              {isExpanded && sector.stocks.length > 0 && (
                <div className="heatmap-expanded">
                  {sector.stocks.map(stock => (
                    <div
                      key={stock.symbol}
                      className="heatmap-stock-item"
                      onClick={(e) => { e.stopPropagation(); onStockClick(stock.symbol); }}
                    >
                      <span className="stock-sym">{stock.symbol.replace(/\.\w+$/, '')}</span>
                      <span className="stock-name">{stock.name}</span>
                      <span className="stock-price">${stock.price}</span>
                      <span className="stock-change" style={{ color: stock.change_pct >= 0 ? '#10b981' : '#ef4444' }}>
                        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
