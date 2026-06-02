import { useEffect, useRef, useState, useCallback, memo } from 'react';
import * as d3 from 'd3';
import { fetchOHLC, fetchKline, fetchParticles } from '../api';
import type { OHLCRow, Particle, HoverData, RangeSelection, ArticleSelection } from '../types';

export type ChartPeriod = '1d' | '5d' | '1mo' | '3mo' | '1y' | '5y';
export const PERIOD_OPTIONS: { key: ChartPeriod; label: string }[] = [
  { key: '1d', label: '1分' },
  { key: '5d', label: '15分' },
  { key: '1mo', label: '日' },
  { key: '3mo', label: '周' },
  { key: '1y', label: '月' },
  { key: '5y', label: '5年' },
];

interface Props {
  symbol: string;
  period?: ChartPeriod;
  lockedNewsId?: string | null;
  highlightedArticleIds?: string[] | null;
  highlightColor?: string | null;
  onHover: (date: string | null, ohlc?: HoverData) => void;
  onRangeSelect?: (range: RangeSelection | null) => void;
  onArticleSelect?: (article: ArticleSelection | null) => void;
  onDayClick?: (date: string) => void;
}

const SENTIMENT_COLOR: Record<string, string> = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#06b6d4',
};
const SENTIMENT_COLOR_DEFAULT = '#5a6577';

function getSentimentColor(s: string | null): string {
  return (s && SENTIMENT_COLOR[s]) || SENTIMENT_COLOR_DEFAULT;
}

function getParticleRadius(relevance: string | null, rt1: number | null): number {
  let r = 2;
  if (relevance === 'relevant') r += 0.8;
  if (rt1 !== null) r += Math.min(Math.abs(rt1) * 20, 1.5);
  return Math.min(r, 4.5);
}

function getParticleAlpha(relevance: string | null): number {
  return relevance === 'relevant' ? 0.7 : 0.3;
}

function getCurrencySymbol(symbol: string): string {
  if (symbol.endsWith('.HK')) return 'HK$';
  if (symbol.endsWith('.SS') || symbol.endsWith('.SZ')) return '¥';
  if (symbol === '^N225') return '¥';
  if (/-USD$/.test(symbol) || symbol === 'BTC' || symbol === 'ETH') return '';
  // Commodities
  if (/^(GC|CL|SI|HG|NG|PA|PL)=F$/.test(symbol)) return '$';
  return '$';
}

interface PlacedParticle extends Particle {
  px: number;
  py: number;
  radius: number;
  color: string;
  alpha: number;
}

export default memo(function CandlestickChart({
  symbol, period = '1mo', lockedNewsId, highlightedArticleIds, highlightColor,
  onHover, onRangeSelect, onArticleSelect, onDayClick,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [chartHeight, setChartHeight] = useState(500);
  const [zoomLevel, setZoomLevel] = useState(1); // 1 = show all data

  const placedRef = useRef<PlacedParticle[]>([]);
  const quadtreeRef = useRef<d3.Quadtree<PlacedParticle> | null>(null);
  const hoveredParticleRef = useRef<PlacedParticle | null>(null);
  const lockedNewsIdRef = useRef<string | null>(null);
  const highlightedIdsRef = useRef<Set<string> | null>(null);
  const highlightColorRef = useRef<string | null>(null);
  const marginRef = useRef({ top: 16, right: 50, bottom: 24, left: 48 });
  const rawDataRef = useRef<OHLCRow[]>([]);
  const particlesRef = useRef<Particle[]>([]);
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null);

  useEffect(() => {
    lockedNewsIdRef.current = lockedNewsId ?? null;
    drawParticles(hoveredParticleRef.current);
  }, [lockedNewsId]);

  useEffect(() => {
    highlightedIdsRef.current = highlightedArticleIds && highlightedArticleIds.length > 0
      ? new Set(highlightedArticleIds)
      : null;
    highlightColorRef.current = highlightColor ?? null;
    drawParticles(hoveredParticleRef.current);
  }, [highlightedArticleIds, highlightColor]);

  const drawParticles = useCallback((highlight: PlacedParticle | null = null) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const locked = lockedNewsIdRef.current;
    const hlSet = highlightedIdsRef.current;
    const hlColor = highlightColorRef.current;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const placed = placedRef.current;
    if (placed.length === 0) return;

    for (const p of placed) {
      const isLocked = locked != null && p.id === locked;
      const isHover = p === highlight;
      const isCategoryMatch = hlSet != null && hlSet.has(p.id);
      const hasCategoryFilter = hlSet != null;

      if (hasCategoryFilter && !isCategoryMatch && !isLocked && !isHover) continue;

      let alpha = p.alpha;
      if (isCategoryMatch && hasCategoryFilter) alpha = 1;
      if (isHover || isLocked) alpha = 1;
      ctx.globalAlpha = alpha;

      let radius = p.radius;
      if (isCategoryMatch && hasCategoryFilter) radius = Math.max(p.radius, 3.5);

      ctx.fillStyle = (isCategoryMatch && hasCategoryFilter && hlColor) ? hlColor : p.color;

      if (isHover || isLocked || (isCategoryMatch && hasCategoryFilter)) {
        const glowColor = isLocked ? '#3b82f6' : (isCategoryMatch && hlColor) ? hlColor : p.color;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = (isLocked || isHover ? 14 : 8) * dpr;
      } else {
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
      }

      ctx.beginPath();
      ctx.arc(p.px * dpr, p.py * dpr, radius * dpr, 0, Math.PI * 2);
      ctx.fill();

      if (isLocked) {
        ctx.shadowColor = '#3b82f6';
        ctx.shadowBlur = 10 * dpr;
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 1.5 * dpr;
        ctx.beginPath();
        ctx.arc(p.px * dpr, p.py * dpr, (radius + 3) * dpr, 0, Math.PI * 2);
        ctx.stroke();
      }

      if (isCategoryMatch && hasCategoryFilter && !isLocked) {
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.strokeStyle = hlColor ? `${hlColor}99` : 'rgba(59, 130, 246, 0.6)';
        ctx.lineWidth = 1 * dpr;
        ctx.beginPath();
        ctx.arc(p.px * dpr, p.py * dpr, (radius + 2) * dpr, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    ctx.globalAlpha = 1;
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
  }, []);

  // Redraw on zoom change
  useEffect(() => {
    if (rawDataRef.current.length > 0) {
      drawChart(rawDataRef.current, particlesRef.current);
    }
  }, [zoomLevel]);

  // Reset zoom when period changes
  useEffect(() => {
    setZoomLevel(1);
  }, [period]);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    let cancelled = false;

    const loadOHLC = (): Promise<OHLCRow[]> => {
      return fetchKline(symbol, period)
        .then((resp: any) => {
          const rows: OHLCRow[] = resp.data || resp;
          if (!Array.isArray(rows) || rows.length === 0) throw new Error('empty kline');
          return rows;
        })
        .catch(() => {
          if (period === '1mo') return fetchOHLC(symbol);
          return fetchOHLC(symbol);
        });
    };

    loadOHLC()
      .then((ohlcData) => {
        if (cancelled) return;
        return fetchParticles(symbol).then((particles) => {
          if (cancelled) return;
          rawDataRef.current = ohlcData;
          particlesRef.current = particles;
          try { drawChart(ohlcData, particles); } catch(e) { console.error('drawChart error:', e); }
        }).catch(() => {
          if (cancelled) return;
          rawDataRef.current = ohlcData;
          particlesRef.current = [];
          try { drawChart(ohlcData, []); } catch(e) { console.error('drawChart error:', e); }
        });
      })
      .catch((err) => {
        if (!cancelled) console.error('Chart data error:', err);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    
    return () => { cancelled = true; };
  }, [symbol, period]);

  // Resize handle drag with requestAnimationFrame throttling
  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = { startY: e.clientY, startHeight: chartHeight };
    let rafId: number | null = null;
    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      if (rafId) return; // throttle to rAF
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (!dragRef.current) return;
        const delta = ev.clientY - dragRef.current.startY;
        const newH = Math.max(300, Math.min(window.innerHeight * 0.8, dragRef.current.startHeight + delta));
        setChartHeight(newH);
      });
    };
    const onMouseUp = () => {
      dragRef.current = null;
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      // Redraw after resize
      if (rawDataRef.current.length > 0) {
        requestAnimationFrame(() => drawChart(rawDataRef.current, particlesRef.current));
      }
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [chartHeight]);

  function drawChart(rawData: OHLCRow[], particles: Particle[]) {
    if (!svgRef.current || !containerRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const container = containerRef.current;
    const fullWidth = container.clientWidth;
    if (fullWidth < 10) {
      requestAnimationFrame(() => {
        if (svgRef.current && containerRef.current && containerRef.current.clientWidth >= 10) {
          drawChart(rawData, particles);
        }
      });
      return;
    }
    const fullHeight = container.clientHeight || 500;
    const margin = marginRef.current;
    const width = fullWidth - margin.left - margin.right;
    
    // Reserve space for volume sub-chart (bottom 20% of chart area)
    const volumeHeight = Math.max(30, Math.floor((fullHeight - margin.top - margin.bottom) * 0.18));
    const candleHeight = fullHeight - margin.top - margin.bottom - volumeHeight - 4; // 4px gap

    svg.attr('width', fullWidth).attr('height', fullHeight);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Explicit YYYY-MM-DD parser to avoid timezone issues
    const parseDate = d3.timeParse('%Y-%m-%d');

    // Dynamic date format based on period
    const currentPeriod = period || '1mo';
    let fmtAxis: (d: Date) => string;
    let fmtCrosshair: (d: Date) => string;
    let fmtOHLC: (d: Date) => string;
    if (currentPeriod === '1d') {
      // 5-min candles → show HH:MM
      fmtAxis = d3.timeFormat('%H:%M');
      fmtCrosshair = d3.timeFormat('%H:%M');
      fmtOHLC = d3.timeFormat('%H:%M');
    } else if (currentPeriod === '5d') {
      // 15-min candles → show MM/DD HH:MM
      fmtAxis = d3.timeFormat('%m/%d %H:%M');
      fmtCrosshair = d3.timeFormat('%m/%d %H:%M');
      fmtOHLC = d3.timeFormat('%m/%d %H:%M');
    } else if (currentPeriod === '1mo' || currentPeriod === '3mo') {
      // Daily candles → show MM/DD
      fmtAxis = d3.timeFormat('%m/%d');
      fmtCrosshair = d3.timeFormat('%m/%d');
      fmtOHLC = d3.timeFormat('%m/%d');
    } else {
      // 1y (weekly), 5y (monthly) → show YY/MM
      fmtAxis = d3.timeFormat('%y/%m');
      fmtCrosshair = d3.timeFormat('%y/%m');
      fmtOHLC = d3.timeFormat('%y/%m');
    }

    const rawDataParsed = rawData.map((d, i) => {
      const parsed = parseDate(d.date) || new Date(d.date);
      return {
        date: parsed,
        dateStr: d.date.slice(0, 10),
        open: +d.open,
        high: +d.high,
        low: +d.low,
        close: +d.close,
        volume: +d.volume,
        change: i > 0 ? ((+d.close - +rawData[i - 1].close) / +rawData[i - 1].close) * 100 : 0,
      };
    });

    const zoom = Math.max(1, zoomLevel || 1);
    const visibleCount = Math.max(20, Math.ceil(rawDataParsed.length / zoom));
    const data = rawDataParsed.slice(Math.max(0, rawDataParsed.length - visibleCount));

    const normalizeDate = (s: string | null | undefined) => s ? s.slice(0, 10) : '';
    const dateToOhlc = new Map<string, typeof data[0]>();
    for (const d of data) dateToOhlc.set(normalizeDate(d.dateStr), d);

    const x = d3.scaleTime()
      .domain(d3.extent(data, (d) => d.date) as [Date, Date])
      .range([0, width]);

    // Auto-scale Y to visible data range
    const yMin = d3.min(data, (d) => d.low)!;
    const yMax = d3.max(data, (d) => d.high)!;
    const yPad = (yMax - yMin) * 0.05 || 1;

    const y = d3.scaleLinear()
      .domain([yMin - yPad, yMax + yPad])
      .range([candleHeight, 0]);

    // Volume scale
    const maxVol = d3.max(data, (d) => d.volume) || 1;
    const yVol = d3.scaleLinear()
      .domain([0, maxVol])
      .range([candleHeight + volumeHeight + 4, candleHeight + 4]);

    // Horizontal grid lines (price)
    g.append('g')
      .attr('class', 'grid-y')
      .call(d3.axisLeft(y).ticks(8).tickSize(-width).tickFormat(() => ''))
      .selectAll('line')
      .style('stroke', '#131c2e')
      .style('stroke-width', 1);
    g.selectAll('.grid-y .domain').remove();

    // Vertical grid lines (dates)
    g.append('g')
      .attr('class', 'grid-x')
      .attr('transform', `translate(0,${candleHeight})`)
      .call(d3.axisBottom(x).ticks(8).tickSize(-candleHeight).tickFormat(() => ''))
      .selectAll('line')
      .style('stroke', '#131c2e')
      .style('stroke-width', 0.5);
    g.selectAll('.grid-x .domain').remove();

    // X Axis
    g.append('g')
      .attr('transform', `translate(0,${candleHeight + volumeHeight + 4})`)
      .call(d3.axisBottom(x).ticks(8).tickFormat(fmtAxis as any))
      .selectAll('text')
      .style('font-size', '11px')
      .style('fill', '#5a6577');

    // Y Axis
    const curSym = getCurrencySymbol(symbol);
    g.append('g')
      .call(d3.axisLeft(y).ticks(6).tickFormat((d) => `${curSym}${Number(d).toFixed(0)}`))
      .selectAll('text')
      .style('font-size', '11px')
      .style('fill', '#5a6577');

    g.selectAll('.domain').style('stroke', '#1a2540');
    g.selectAll('.tick line').style('stroke', '#1a2540');

    const candleWidth = Math.max(1, Math.min(20, (width / data.length) * 0.6));

    // Volume bars
    const volBars = g.selectAll('.vol-bar').data(data).enter().append('rect')
      .attr('class', 'vol-bar')
      .attr('x', (d) => x(d.date) - candleWidth / 2)
      .attr('y', (d) => yVol(d.volume))
      .attr('width', candleWidth)
      .attr('height', (d) => Math.max(0, candleHeight + volumeHeight + 4 - yVol(d.volume)))
      .attr('fill', (d) => d.close >= d.open ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)')
      .attr('rx', 1);

    // Candlesticks
    const candles = g.selectAll('.candle').data(data).enter().append('g').attr('class', 'candle');

    candles.append('line')
      .attr('x1', (d) => x(d.date))
      .attr('x2', (d) => x(d.date))
      .attr('y1', (d) => y(d.high))
      .attr('y2', (d) => y(d.low))
      .attr('stroke', (d) => (d.close >= d.open ? '#10b981' : '#ef4444'))
      .attr('stroke-width', 1);

    candles.append('rect')
      .attr('x', (d) => x(d.date) - candleWidth / 2)
      .attr('y', (d) => y(Math.max(d.open, d.close)))
      .attr('width', candleWidth)
      .attr('height', (d) => Math.max(1, Math.abs(y(d.open) - y(d.close))))
      .attr('fill', (d) => (d.close >= d.open ? '#10b981' : '#ef4444'));

    // Place particles
    const particlesByDate = new Map<string, Particle[]>();
    for (const p of particles) {
      const key = normalizeDate(p.d);
      const arr = particlesByDate.get(key) || [];
      arr.push(p);
      particlesByDate.set(key, arr);
    }

    // Particle matching debug (removed for production)

    const placed: PlacedParticle[] = [];
    const pSpacing = Math.max(4.5, Math.min(7, candleHeight / 80));

    for (const [dateStr, pArr] of particlesByDate) {
      const ohlc = dateToOhlc.get(dateStr);
      if (!ohlc) continue;

      const cx = x(ohlc.date);
      pArr.sort((a, b) => {
        const ra = a.r === 'relevant' ? 0 : 1;
        const rb = b.r === 'relevant' ? 0 : 1;
        if (ra !== rb) return ra - rb;
        return Math.abs(b.rt1 || 0) - Math.abs(a.rt1 || 0);
      });

      for (let i = 0; i < pArr.length; i++) {
        const p = pArr[i];
        const radius = getParticleRadius(p.r, p.rt1);
        const candleLowY = y(ohlc.low);
        const py = margin.top + candleLowY + 6 + i * pSpacing;
        if (py > margin.top + candleHeight + 10) break;

        placed.push({
          ...p,
          px: margin.left + cx,
          py,
          radius,
          color: getSentimentColor(p.s),
          alpha: getParticleAlpha(p.r),
        });
      }
    }

    placedRef.current = placed;

    quadtreeRef.current = d3.quadtree<PlacedParticle>()
      .x((d) => d.px)
      .y((d) => d.py)
      .addAll(placed);

    // Setup Canvas
    const canvas = canvasRef.current;
    if (canvas) {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = fullWidth * dpr;
      canvas.height = fullHeight * dpr;
      canvas.style.width = `${fullWidth}px`;
      canvas.style.height = `${fullHeight}px`;
      drawParticles();
    }

    // Crosshair
    const crossV = g.append('line')
      .style('stroke', '#1e293b').style('stroke-width', 0.5)
      .style('stroke-dasharray', '4,3').style('display', 'none').style('pointer-events', 'none');
    const crossH = g.append('line')
      .style('stroke', '#1e293b').style('stroke-width', 0.5)
      .style('stroke-dasharray', '4,3').style('display', 'none').style('pointer-events', 'none');

    const priceLabel = g.append('g').style('display', 'none');
    priceLabel.append('rect').attr('fill', '#131c2e').attr('rx', 3).attr('width', 46).attr('height', 18);
    priceLabel.append('text').attr('fill', '#8b95a8').attr('font-size', '11px')
      .attr('text-anchor', 'middle').attr('dy', '13px');

    const dateLabel = g.append('g').style('display', 'none');
    dateLabel.append('rect').attr('fill', '#131c2e').attr('rx', 3).attr('width', 90).attr('height', 20);
    dateLabel.append('text').attr('fill', '#8b95a8').attr('font-size', '11px')
      .attr('text-anchor', 'middle').attr('dy', '14px');

    const bisect = d3.bisector<typeof data[0], Date>((d) => d.date).left;

    function snapToData(px: number) {
      const xDate = x.invert(px);
      const idx = bisect(data, xDate, 1);
      const d0 = data[idx - 1];
      const d1 = data[idx];
      if (!d0) return data[0];
      return d1 && xDate.getTime() - d0.date.getTime() > d1.date.getTime() - xDate.getTime() ? d1 : d0;
    }

    function findParticle(mouseX: number, mouseY: number): PlacedParticle | null {
      const qt = quadtreeRef.current;
      if (!qt) return null;
      const searchRadius = 8;
      let closest: PlacedParticle | null = null;
      let closestDist = searchRadius;
      const hlSet = highlightedIdsRef.current;
      const locked = lockedNewsIdRef.current;

      qt.visit((node, x0, y0, x1, y1) => {
        if (!('data' in node)) {
          return x0 > mouseX + searchRadius || x1 < mouseX - searchRadius ||
                 y0 > mouseY + searchRadius || y1 < mouseY - searchRadius;
        }
        let leaf: typeof node | undefined = node;
        while (leaf) {
          const p = leaf.data;
          if (hlSet != null && !hlSet.has(p.id) && p.id !== locked) {
            leaf = (leaf as any).next;
            continue;
          }
          const dx = p.px - mouseX;
          const dy = p.py - mouseY;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < closestDist) {
            closestDist = dist;
            closest = p;
          }
          leaf = (leaf as any).next;
        }
        return false;
      });

      return closest;
    }

    // D3 Brush for range selection
    let brushMoving = false;
    const brush = d3.brushX<unknown>()
      .extent([[0, 0], [width, candleHeight + volumeHeight + margin.bottom]])
      .on('end', function (event) {
        if (brushMoving) return;
        if (!event.selection) {
          if (event.sourceEvent) {
            const [mx] = d3.pointer(event.sourceEvent, g.node());
            const d = snapToData(mx);
            const [absX, absY] = d3.pointer(event.sourceEvent, container);
            const hit = findParticle(absX, absY);
            if (hit) {
              onArticleSelect?.({ newsId: hit.id, date: hit.d });
            } else {
              onArticleSelect?.(null);
              onDayClick?.(d.dateStr);
            }
          }
          return;
        }
        const [x0, x1] = event.selection as [number, number];
        const d0 = snapToData(x0);
        const d1 = snapToData(x1);
        if (d0.dateStr === d1.dateStr) {
          brushMoving = true;
          d3.select(this).call(brush.move, null);
          brushMoving = false;
          return;
        }
        brushMoving = true;
        d3.select(this).call(brush.move, [x(d0.date), x(d1.date)]);
        brushMoving = false;
        const priceChange = ((d1.close - d0.open) / d0.open) * 100;
        const popupX = margin.left + x(d1.date) + 8;
        const popupY = margin.top + Math.min(y(d0.close), y(d1.close)) - 20;
        onRangeSelect?.({ startDate: d0.dateStr, endDate: d1.dateStr, priceChange, popupX, popupY });
      });

    const brushG = g.append('g').attr('class', 'brush').call(brush);

    brushG.selectAll('.selection')
      .attr('fill', '#3b82f6')
      .attr('fill-opacity', 0.15)
      .attr('stroke', '#3b82f6')
      .attr('stroke-width', 1);

    // Hover events on brush overlay
    brushG.select('.overlay')
      .style('cursor', 'crosshair')
      .on('mousemove.hover', function (event) {
        const [mx, my] = d3.pointer(event);
        const d = snapToData(mx);
        const cx = x(d.date);
        const priceAtY = y.invert(Math.min(my, candleHeight));

        crossV.attr('x1', cx).attr('x2', cx).attr('y1', 0).attr('y2', candleHeight).style('display', null);
        crossH.attr('x1', 0).attr('x2', width).attr('y1', my).attr('y2', my).style('display', null);

        priceLabel.style('display', null).attr('transform', `translate(${-46},${my - 9})`);
        priceLabel.select('text').attr('x', 23).text(`${curSym}${priceAtY.toFixed(2)}`);

        dateLabel.style('display', null).attr('transform', `translate(${cx - 45},${candleHeight + volumeHeight + 4})`);
        dateLabel.select('text').attr('x', 45).text(fmtCrosshair(d.date));

        onHover(d.dateStr, {
          date: d.dateStr, open: d.open, high: d.high,
          low: d.low, close: d.close, change: d.change,
        });

        const [absX, absY] = d3.pointer(event, container);
        const hit = findParticle(absX, absY);

        if (hit !== hoveredParticleRef.current) {
          hoveredParticleRef.current = hit;
          drawParticles(hit);

          const tooltip = tooltipRef.current;
          if (tooltip) {
            if (hit) {
              const retStr = hit.rt1 !== null ? `${(hit.rt1 * 100).toFixed(2)}%` : '-';
              const retColor = hit.rt1 !== null ? (hit.rt1 >= 0 ? '#10b981' : '#ef4444') : '#5a6577';
              tooltip.innerHTML = `
                <div class="pt-title">${hit.t}</div>
                <div class="pt-meta">
                  <span class="pt-sentiment" style="color:${hit.color}">${hit.s || 'unknown'}</span>
                  <span class="pt-ret" style="color:${retColor}">T+1: ${retStr}</span>
                </div>
              `;
              tooltip.style.display = 'block';
              const tipW = 280;
              const onRight = hit.px < fullWidth / 2;
              const tipX = onRight ? hit.px + 12 : hit.px - tipW - 12;
              const tipY = hit.py - 40;
              tooltip.style.left = `${Math.max(4, tipX)}px`;
              tooltip.style.top = `${Math.max(4, tipY)}px`;
            } else {
              tooltip.style.display = 'none';
            }
          }
        }
      })
      .on('mouseleave.hover', function () {
        crossV.style('display', 'none');
        crossH.style('display', 'none');
        priceLabel.style('display', 'none');
        dateLabel.style('display', 'none');
        onHover(null);

        if (hoveredParticleRef.current) {
          hoveredParticleRef.current = null;
          drawParticles();
        }
        const tooltip = tooltipRef.current;
        if (tooltip) tooltip.style.display = 'none';
      });
  }

  const handleZoomIn = () => setZoomLevel(z => Math.min(10, z * 1.5));
  const handleZoomOut = () => setZoomLevel(z => Math.max(1, z / 1.5));

  return (
    <div
      ref={containerRef}
      className="chart-container"
      style={{ height: `${chartHeight}px`, minHeight: '300px', maxHeight: '80vh' }}
    >
      {loading && <div className="chart-loading">加载中...</div>}
      <svg ref={svgRef}></svg>
      <canvas ref={canvasRef} className="particle-layer" />
      <div ref={tooltipRef} className="particle-tooltip" style={{ display: 'none' }} />
      
      {/* Zoom controls */}
      <div style={{
        position: 'absolute', top: 8, right: 8, zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: 2,
      }}>
        <button
          onClick={handleZoomIn}
          style={{
            width: 24, height: 24, background: '#252836', border: '1px solid #3a3d4a',
            borderRadius: 4, color: '#888', cursor: 'pointer', fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          title="放大：只看更近一段行情"
        >+</button>
        <button
          onClick={handleZoomOut}
          style={{
            width: 24, height: 24, background: '#252836', border: '1px solid #3a3d4a',
            borderRadius: 4, color: '#888', cursor: 'pointer', fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          title="缩小：显示更长历史"
        >−</button>
        <span className="chart-zoom-label">{zoomLevel.toFixed(1)}x</span>
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={handleResizeMouseDown}
        style={{
          position: 'absolute', bottom: 0, right: 0,
          width: 16, height: 16, cursor: 'ns-resize', zIndex: 10,
          background: 'linear-gradient(135deg, transparent 50%, #3a3d4a 50%, #3a3d4a 60%, transparent 60%, transparent 70%, #3a3d4a 70%, #3a3d4a 80%, transparent 80%)',
        }}
        title="Drag to resize"
      />
    </div>
  );
});
