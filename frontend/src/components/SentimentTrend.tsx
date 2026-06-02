import { useState, useEffect, useRef } from 'react';
import { fetchSentimentTrend } from '../api';
import type { SentimentPoint } from '../types';

export default function SentimentTrend() {
  const [data, setData] = useState<SentimentPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    setLoading(true);
    fetchSentimentTrend()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (data.length === 0) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);

    const padding = { top: 10, bottom: 24, left: 4, right: 4 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    const maxScore = Math.max(1, ...data.map((d) => Math.abs(d.score)));
    const barW = Math.max(8, (chartW / data.length) * 0.6);
    const gap = chartW / data.length;

    data.forEach((point, i) => {
      const x = padding.left + i * gap + (gap - barW) / 2;
      const isPositive = point.score >= 0;
      const barH = (Math.abs(point.score) / maxScore) * (chartH / 2);

      ctx.fillStyle = isPositive ? '#10b981' : '#ef4444';

      if (isPositive) {
        ctx.fillRect(x, padding.top + chartH / 2 - barH, barW, barH);
      } else {
        ctx.fillRect(x, padding.top + chartH / 2, barW, barH);
      }

      // Date label
      ctx.fillStyle = '#5a6577';
      ctx.font = '10px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      const label = point.date.slice(5); // MM-DD
      ctx.fillText(label, x + barW / 2, h - 4);
    });

    // Zero line
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartH / 2);
    ctx.lineTo(w - padding.right, padding.top + chartH / 2);
    ctx.stroke();
  }, [data]);

  if (loading && data.length === 0) return <div className="loading-placeholder">加载中...</div>;

  return (
    <div className="sentiment-trend">
      <canvas ref={canvasRef} style={{ width: '100%', height: '120px' }} />
    </div>
  );
}
