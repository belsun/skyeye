import { useState, useEffect, useCallback, Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import Header from './components/Header';
import MarketOverview from './components/MarketOverview';
import MarketSectorHeatmap from './components/MarketSectorHeatmap';
import SectorHeatmap from './components/SectorHeatmap';
import GeopoliticalGauge from './components/GeopoliticalGauge';
import ActionCenterPanel from './components/ActionCenterPanel';
import OpportunityRadarPanel from './components/OpportunityRadarPanel';
import InvestmentBriefPanel from './components/InvestmentBriefPanel';
import DecisionBoardPanel from './components/DecisionBoardPanel';
import CatalystRadarPanel from './components/CatalystRadarPanel';
import TradeSetupPanel from './components/TradeSetupPanel';
import QuantStarterPanel from './components/QuantStarterPanel';
import StrategyMonitorPanel from './components/StrategyMonitorPanel';
import PortfolioPlanPanel from './components/PortfolioPlanPanel';
import PaperPerformancePanel from './components/PaperPerformancePanel';
import HoldingsMonitorPanel from './components/HoldingsMonitorPanel';
import RebalanceMonitorPanel from './components/RebalanceMonitorPanel';
import TradeJournalPanel from './components/TradeJournalPanel';
import TradeReviewPanel from './components/TradeReviewPanel';

// Error boundary to prevent entire app from crashing
class ErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean, error: string}> {
  constructor(props: {children: ReactNode}) {
    super(props);
    this.state = { hasError: false, error: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{padding: 40, color: '#ef4444', background: '#070b14', minHeight: '100vh'}}>
          <h2>⚠️ 渲染错误</h2>
          <p>{this.state.error}</p>
          <button onClick={() => this.setState({hasError: false})} style={{padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', marginTop: 10}}>
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
import SentimentTrend from './components/SentimentTrend';
import NewsFeed from './components/NewsFeed';
import EventTracker from './components/EventTracker';
import TrendingTopics from './components/TrendingTopics';
import StockSelector from './components/StockSelector';
import CandlestickChart from './components/CandlestickChart';
import type { ChartPeriod } from './components/CandlestickChart';
import { PERIOD_OPTIONS } from './components/CandlestickChart';
import CompanyProfilePanel from './components/CompanyProfilePanel';
import NewsPanel from './components/NewsPanel';
import NewsCategoryPanel from './components/NewsCategoryPanel';
import SimilarDaysPanel from './components/SimilarDaysPanel';
import PredictionPanel from './components/PredictionPanel';
import RiskBriefPanel from './components/RiskBriefPanel';
import QuantLabPanel from './components/QuantLabPanel';
import RangeAnalysisPanel from './components/RangeAnalysisPanel';
import RangeNewsPanel from './components/RangeNewsPanel';
import RangeQueryPopup from './components/RangeQueryPopup';
import StoryPanel from './components/StoryPanel';
import SectorAnalysisPanel from './components/SectorAnalysisPanel';
import { fetchStocks, postStock } from './api';
import type { HoverData, RangeSelection, ArticleSelection } from './types';

const TABS = [
  { key: 'overview', label: '🌍 全球总览' },
  { key: 'watchlist', label: '⭐ 自选' },
  { key: 'us', label: '🇺🇸 美股' },
  { key: 'hk', label: '🇭🇰 港股' },
  { key: 'cn', label: '🇨🇳 A股' },
  { key: 'jp', label: '🇯🇵 日股' },
  { key: 'eu', label: '🇪🇺 欧股' },
  { key: 'crypto', label: '₿ 加密' },
  { key: 'commodities', label: '🥇 大宗' },
];

type ViewMode = 'overview' | 'deep';
type ThemeMode = 'midnight' | 'hk' | 'terminal' | 'sakura' | 'daylight' | 'aurora';
type LanguageMode = 'zh' | 'en' | 'both';
type LearningMode = 'learning' | 'pro';

function readStoredMode<T extends string>(key: string, fallback: T, allowed: readonly T[]): T {
  const stored = window.localStorage.getItem(key) as T | null;
  return stored && allowed.includes(stored) ? stored : fallback;
}

export default function App() {
  // ===== Top-level state =====
  const [activeTab, setActiveTab] = useState('overview');
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [tickers, setTickers] = useState<string[]>([]);
  const [themeMode, setThemeMode] = useState<ThemeMode>(() =>
    readStoredMode<ThemeMode>('skyeye.theme', 'midnight', ['midnight', 'hk', 'terminal', 'sakura', 'daylight', 'aurora'])
  );
  const [languageMode, setLanguageMode] = useState<LanguageMode>(() =>
    readStoredMode<LanguageMode>('skyeye.language', 'both', ['zh', 'en', 'both'])
  );
  const [learningMode, setLearningMode] = useState<LearningMode>(() =>
    readStoredMode<LearningMode>('skyeye.learningMode', 'learning', ['learning', 'pro'])
  );
  const [showQuantTools, setShowQuantTools] = useState(false);

  // ===== Deep analysis state =====
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const [lockedNewsId, setLockedNewsId] = useState<string | null>(null);
  const [highlightedCategoryIds, setHighlightedCategoryIds] = useState<string[]>([]);
  const [highlightColor, setHighlightColor] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [rangeSelection, setRangeSelection] = useState<RangeSelection | null>(null);
  const [rangeQuestion, setRangeQuestion] = useState<string | undefined>(undefined);
  const [similarDaysDate, setSimilarDaysDate] = useState<string | null>(null);
  const [showRangeNews, setShowRangeNews] = useState(false);
  const [chartRect, setChartRect] = useState<DOMRect | undefined>(undefined);
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('1mo');
  const [sectorAnalysisKey, setSectorAnalysisKey] = useState<string | null>(null);

  // ===== Load tickers for stock selector =====
  // Global error handler to prevent silent crashes
  useEffect(() => {
    const handleError = (e: ErrorEvent) => {
      console.error('Global error caught:', e.error);
      e.preventDefault();
    };
    const handleRejection = (e: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', e.reason);
      e.preventDefault();
    };
    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);
    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleRejection);
    };
  }, []);

  useEffect(() => {
    fetchStocks().then(setTickers).catch(() => {});
  }, []);

  const addTrackingSymbol = useCallback(async (symbol: string) => {
    const created = await postStock(symbol);
    setTickers(prev => {
      const next = (created?.symbol || symbol).toUpperCase();
      return prev.includes(next) ? prev : [...prev, next];
    });
  }, []);

  useEffect(() => {
    window.localStorage.setItem('skyeye.theme', themeMode);
  }, [themeMode]);

  useEffect(() => {
    window.localStorage.setItem('skyeye.language', languageMode);
  }, [languageMode]);

  useEffect(() => {
    window.localStorage.setItem('skyeye.learningMode', learningMode);
  }, [learningMode]);

  // ===== Enter deep analysis =====
  const enterDeepAnalysis = useCallback((symbol: string) => {
    setSelectedSymbol(symbol);
    setViewMode('deep');
    setLockedNewsId(null);
    setHighlightedCategoryIds([]);
    setHighlightColor(null);
    setActiveCategory(null);
    setRangeSelection(null);
    setSimilarDaysDate(null);
    setShowRangeNews(false);
    setHoveredDate(null);
  }, []);

  // ===== Back to overview =====
  const backToOverview = useCallback(() => {
    setViewMode('overview');
    setSelectedSymbol('');
  }, []);

  // ===== ESC key handler =====
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (sectorAnalysisKey) {
          setSectorAnalysisKey(null);
        } else if (rangeSelection) {
          setRangeSelection(null);
        } else if (similarDaysDate) {
          setSimilarDaysDate(null);
        } else if (showRangeNews) {
          setShowRangeNews(false);
        } else if (lockedNewsId) {
          setLockedNewsId(null);
        } else if (viewMode === 'deep') {
          backToOverview();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [sectorAnalysisKey, rangeSelection, similarDaysDate, showRangeNews, lockedNewsId, viewMode, backToOverview]);

  // ===== Chart interaction handlers =====
  const handleHover = useCallback((date: string | null, _ohlc?: HoverData) => {
    if (!lockedNewsId) {
      setHoveredDate(date);
    }
  }, [lockedNewsId]);

  const handleRangeSelect = useCallback((range: RangeSelection | null) => {
    setRangeSelection(range);
    if (range) {
      setChartRect(document.querySelector('.chart-container')?.getBoundingClientRect());
    }
  }, []);

  const handleArticleSelect = useCallback((article: ArticleSelection | null) => {
    if (article) {
      setLockedNewsId(article.newsId);
      setHoveredDate(article.date);
    } else {
      setLockedNewsId(null);
    }
  }, []);

  const handleDayClick = useCallback((date: string) => {
    setSimilarDaysDate(date);
  }, []);

  const handleCategoryChange = useCallback((category: string | null, articleIds: string[], color?: string) => {
    setActiveCategory(category);
    setHighlightedCategoryIds(articleIds);
    setHighlightColor(color || null);
  }, []);

  const handleRangeAsk = useCallback((question: string) => {
    setRangeQuestion(question);
    setRangeSelection(null);
    setShowRangeNews(false);
  }, []);

  return (
    <ErrorBoundary>
    <div className={`app theme-${themeMode} lang-${languageMode} mode-${learningMode}`}>
      <Header
        viewMode={viewMode}
        selectedSymbol={selectedSymbol}
        onBack={backToOverview}
        onSearchSelect={enterDeepAnalysis}
        themeMode={themeMode}
        languageMode={languageMode}
        learningMode={learningMode}
        onThemeChange={setThemeMode}
        onLanguageChange={setLanguageMode}
        onLearningModeChange={setLearningMode}
      />

      {viewMode === 'overview' ? (
        <>
          {/* Tabs */}
          <div className="tabs">
            {TABS.map(tab => (
              <div
                key={tab.key}
                className={`tab ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </div>
            ))}
          </div>

          {/* Overview content */}
          <div className="container">
            {activeTab === 'overview' ? (
              <div className="overview-layout">
                <div className="overview-main">
                  <div className="section">
                    <OpportunityRadarPanel onStockClick={enterDeepAnalysis} />
                  </div>
                  <div className="section">
                    <InvestmentBriefPanel onStockClick={enterDeepAnalysis} />
                  </div>
                  <div className="section">
                    <ActionCenterPanel onStockClick={enterDeepAnalysis} />
                  </div>
                  <div className="section">
                    <CatalystRadarPanel onStockClick={enterDeepAnalysis} />
                  </div>
                  <div className="section quant-tools-section">
                    <button className="quant-tools-toggle" onClick={() => setShowQuantTools(v => !v)}>
                      <span>量化工具箱 / Quant Tools</span>
                      <em>把模型、回测、组合和复盘先收起来；需要学习或深入研究时再展开。</em>
                      <strong>{showQuantTools ? '收起' : '展开'}</strong>
                    </button>
                    {showQuantTools && (
                      <div className="quant-tools-body">
                        <DecisionBoardPanel onStockClick={enterDeepAnalysis} />
                        <TradeSetupPanel onStockClick={enterDeepAnalysis} />
                        <QuantStarterPanel />
                        <StrategyMonitorPanel onStockClick={enterDeepAnalysis} />
                        <PortfolioPlanPanel onStockClick={enterDeepAnalysis} />
                        <PaperPerformancePanel onStockClick={enterDeepAnalysis} />
                        <HoldingsMonitorPanel onStockClick={enterDeepAnalysis} />
                        <RebalanceMonitorPanel onStockClick={enterDeepAnalysis} />
                        <TradeJournalPanel onStockClick={enterDeepAnalysis} />
                        <TradeReviewPanel onStockClick={enterDeepAnalysis} />
                      </div>
                    )}
                  </div>
                  <div className="section">
                    <div className="section-title">全球市场概览</div>
                    <MarketOverview onStockClick={enterDeepAnalysis} />
                  </div>
                  <div className="section">
                    <div className="section-title">板块热力图 (美股)</div>
                    <SectorHeatmap onSectorClick={(key) => setSectorAnalysisKey(key)} />
                  </div>
                  <div className="section">
                    <div className="section-title">📰 全球新闻舆情</div>
                    <NewsFeed />
                  </div>
                </div>
                <div className="overview-sidebar">
                  <div className="panel">
                    <div className="section-title">⚠️ 地缘政治风险</div>
                    <GeopoliticalGauge />
                  </div>
                  <div className="panel">
                    <div className="section-title">📈 舆情趋势</div>
                    <SentimentTrend />
                  </div>
                  <div className="panel">
                    <div className="section-title">🔥 热门话题</div>
                    <TrendingTopics />
                  </div>
                  <div className="panel">
                    <div className="section-title">🚀 重大事件 & IPO</div>
                    <EventTracker onStockClick={enterDeepAnalysis} />
                  </div>
                </div>
              </div>
            ) : (
              /* Region-specific tabs (US, HK, CN, etc.) */
              <div className="section">
                <div className="section-title">
                  {TABS.find(t => t.key === activeTab)?.label || activeTab}
                </div>
                <MarketOverview
                  filter={activeTab}
                  onStockClick={enterDeepAnalysis}
                />
                {activeTab === 'hk' && (
                  <>
                    <OpportunityRadarPanel onStockClick={enterDeepAnalysis} defaultMarket="hk" />
                    <MarketSectorHeatmap market="hk" label="港股" onStockClick={enterDeepAnalysis} />
                  </>
                )}
                {activeTab === 'cn' && <MarketSectorHeatmap market="cn" label="A股" onStockClick={enterDeepAnalysis} />}
                {activeTab === 'jp' && <MarketSectorHeatmap market="jp" label="日股" onStockClick={enterDeepAnalysis} />}
                {activeTab === 'eu' && <MarketSectorHeatmap market="eu" label="欧股" onStockClick={enterDeepAnalysis} />}
              </div>
            )}
          </div>
        </>
      ) : (
        /* Deep Analysis View */
        <div className="deep-container">
          <div className="deep-header">
            <StockSelector
              activeTickers={tickers}
              selectedSymbol={selectedSymbol}
              onSelect={enterDeepAnalysis}
              onAdd={addTrackingSymbol}
            />
          </div>

          <div className="deep-layout">
            <div className="deep-market-stage">
              <div className="deep-chart-column">
                <CompanyProfilePanel symbol={selectedSymbol} />
                <NewsCategoryPanel
                  symbol={selectedSymbol}
                  activeCategory={activeCategory}
                  onCategoryChange={handleCategoryChange}
                />

                <div className="deep-chart-area">
                  <div className="period-tabs">
                    {PERIOD_OPTIONS.map((opt, i) => (
                      <button
                        key={`${opt.key}-${i}`}
                        className={`period-btn ${chartPeriod === opt.key ? 'active' : ''}`}
                        onClick={() => setChartPeriod(opt.key)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <CandlestickChart
                    symbol={selectedSymbol}
                    period={chartPeriod}
                    lockedNewsId={lockedNewsId}
                    highlightedArticleIds={highlightedCategoryIds.length > 0 ? highlightedCategoryIds : null}
                    highlightColor={highlightColor}
                    onHover={handleHover}
                    onRangeSelect={handleRangeSelect}
                    onArticleSelect={handleArticleSelect}
                    onDayClick={handleDayClick}
                  />
                </div>
              </div>

              <div className="deep-news-column">
                <NewsPanel
                  symbol={selectedSymbol}
                  hoveredDate={hoveredDate}
                  highlightedNewsId={lockedNewsId}
                  isLocked={!!lockedNewsId}
                  onUnlock={() => setLockedNewsId(null)}
                  highlightedCategoryIds={highlightedCategoryIds}
                />
              </div>
            </div>

            <div className="deep-analysis-dashboard">
              <PredictionPanel symbol={selectedSymbol} />
              <RiskBriefPanel symbol={selectedSymbol} />
              <details className="deep-quant-details">
                <summary>
                  <span>量化实验室 / Quant Lab</span>
                  <em>模型训练、标注覆盖和回测质量，学习时展开即可。</em>
                </summary>
                <QuantLabPanel symbol={selectedSymbol} />
              </details>
              {similarDaysDate && (
                <SimilarDaysPanel
                  symbol={selectedSymbol}
                  date={similarDaysDate}
                  onClose={() => setSimilarDaysDate(null)}
                />
              )}
              {rangeQuestion && rangeSelection && (
                <RangeAnalysisPanel
                  symbol={selectedSymbol}
                  startDate={rangeSelection.startDate}
                  endDate={rangeSelection.endDate}
                  question={rangeQuestion}
                  onClear={() => { setRangeQuestion(undefined); setRangeSelection(null); }}
                />
              )}
              <StoryPanel symbol={selectedSymbol} />
            </div>
          </div>

          {/* Range Query Popup */}
          {rangeSelection && !rangeQuestion && (
            <RangeQueryPopup
              range={rangeSelection}
              chartRect={chartRect}
              onAsk={handleRangeAsk}
              onClose={() => setRangeSelection(null)}
            />
          )}

          {/* Range News Panel (overlay) */}
          {showRangeNews && rangeSelection && (
            <div className="modal-overlay show" onClick={() => setShowRangeNews(false)}>
              <div className="modal" onClick={e => e.stopPropagation()}>
                <RangeNewsPanel
                  symbol={selectedSymbol}
                  startDate={rangeSelection.startDate}
                  endDate={rangeSelection.endDate}
                  priceChange={rangeSelection.priceChange}
                  onClose={() => setShowRangeNews(false)}
                  onAskAI={handleRangeAsk}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sector Analysis Panel (global overlay) */}
      {sectorAnalysisKey && (
        <SectorAnalysisPanel
          sectorKey={sectorAnalysisKey}
          onClose={() => setSectorAnalysisKey(null)}
          onStockClick={(sym) => { setSectorAnalysisKey(null); enterDeepAnalysis(sym); }}
        />
      )}
    </div>
    </ErrorBoundary>
  );
}
