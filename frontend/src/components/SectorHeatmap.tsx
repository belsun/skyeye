import { useState, useEffect } from 'react';
import { fetchSectors } from '../api';
import type { SectorItem } from '../types';

interface LeadingStock {
  symbol: string;
  name?: string;
  price?: number;
  change_pct?: number;
}

interface Props {
  onSectorClick: (symbol: string) => void;
}

function getHeatColor(pct: number): string {
  if (pct >= 2) return '#10b981';
  if (pct >= 0.5) return '#16a34a';
  if (pct >= 0.1) return '#22c55e';
  if (pct >= -0.1) return '#6b7280';
  if (pct >= -0.5) return '#f97316';
  if (pct >= -2) return '#ef4444';
  return '#dc2626';
}

export default function SectorHeatmap({ onSectorClick }: Props) {
  const [sectors, setSectors] = useState<(SectorItem & { leader?: LeadingStock })[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchSectors()
      .then(setSectors)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading && sectors.length === 0) return <div className="loading-placeholder">加载中...</div>;
  if (sectors.length === 0) return null;

  return (
    <div className="sector-heatmap">
      <div className="heatmap-grid">
        {sectors.slice(0, 10).map((sector) => {
          const color = getHeatColor(sector.change_pct);
          const leader = sector.leader;
          return (
            <div
              key={sector.symbol}
              className="heatmap-tile"
              style={{ backgroundColor: `${color}33`, borderColor: `${color}88` }}
              onClick={() => onSectorClick(sector.symbol)}
            >
              <span className="heatmap-icon">{sector.icon || '📊'}</span>
              <span className="heatmap-name">{sector.name}</span>
              <span className="heatmap-pct" style={{ color }}>
                {sector.change_pct >= 0 ? '+' : ''}{sector.change_pct.toFixed(2)}%
              </span>
              {leader && (
                <div className="heatmap-leader">
                  <span className="leader-symbol">{leader.symbol}</span>
                  {leader.price != null && <span className="leader-price">${leader.price.toFixed(0)}</span>}
                  {leader.change_pct != null && (
                    <span className="leader-change" style={{ color: leader.change_pct >= 0 ? '#10b981' : '#ef4444' }}>
                      {leader.change_pct >= 0 ? '+' : ''}{leader.change_pct.toFixed(1)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
