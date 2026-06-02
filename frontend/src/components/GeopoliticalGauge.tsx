import { useState, useEffect } from 'react';
import { fetchGeopolitical } from '../api';
import type { GeopoliticalData, RiskCategory } from '../types';

export default function GeopoliticalGauge() {
  const [data, setData] = useState<GeopoliticalData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchGeopolitical()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) return <div className="loading-placeholder">加载中...</div>;
  if (!data) return null;

  const risk = data.overall;
  const maxRisk = 10;
  const pct = risk / maxRisk;
  const circumference = 2 * Math.PI * 54;
  const offset = circumference * (1 - pct);

  const getRiskColor = (v: number) => {
    if (v <= 3) return '#10b981';
    if (v <= 5) return '#f59e0b';
    if (v <= 7) return '#f97316';
    return '#ef4444';
  };

  const riskColor = getRiskColor(risk);
  const riskLabel = risk <= 3 ? '低风险' : risk <= 5 ? '中等' : risk <= 7 ? '较高' : '高风险';

  return (
    <div className="geo-gauge">
      <div className="gauge-svg-wrap">
        <svg width="130" height="130" viewBox="0 0 120 120">
          {/* Background circle */}
          <circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke="#1e293b"
            strokeWidth="10"
          />
          {/* Animated fill */}
          <circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke={riskColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 60 60)"
            style={{ transition: 'stroke-dashoffset 1s ease-out, stroke 0.5s' }}
          />
          {/* Center text */}
          <text x="60" y="52" textAnchor="middle" fill={riskColor} fontSize="28" fontWeight="700">
            {risk.toFixed(1)}
          </text>
          <text x="60" y="72" textAnchor="middle" fill="#8b95a8" fontSize="12">
            {riskLabel}
          </text>
        </svg>
      </div>

      <div className="gauge-categories">
        {data.categories.map((cat: RiskCategory) => {
          const catColor = getRiskColor(cat.score);
          const barPct = (cat.score / 10) * 100;
          return (
            <div key={cat.name} className="gauge-cat-row">
              <span className="gauge-cat-name">{cat.name}</span>
              <div className="gauge-cat-bar-track">
                <div
                  className="gauge-cat-bar-fill"
                  style={{ width: `${barPct}%`, backgroundColor: catColor }}
                />
              </div>
              <span className="gauge-cat-score" style={{ color: catColor }}>
                {cat.score.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
