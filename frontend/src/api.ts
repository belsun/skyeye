import axios from 'axios';
import type {
  MarketOverviewData, SectorItem, NewsFeedData, GeopoliticalData,
  SentimentPoint, TrendingData, EventsData, SearchData, OHLCRow,
  Particle, StockNewsItem, CategoriesResponse, Forecast,
  SimilarDaysData, RangeAnalysis, RangeNewsResponse, SectorAnalysisData,
  ActionCenter, CatalystRadar, DecisionBoard, PortfolioHoldings, PortfolioPlan, PortfolioPositionInput,
  OpportunityRadar, PaperBookPerformance, PaperBooksResponse, PaperOrderInput, PaperOrderResponse,
  InvestmentBrief, PaperPerformance, QuantAnalyzeResponse, QuantStatus, QuantTrainResponse, RebalancePlan, RiskBrief,
  StrategyMonitor, TradeJournal, TradeJournalInput, TradeReview, TradeSetups
} from './types';

const api = axios.create({ baseURL: '/api' });

// ============ Request Deduplication & Cache ============
const CACHE_TTL = 5000; // 5 seconds
const cache = new Map<string, { data: any; timestamp: number }>();
const inflight = new Map<string, Promise<any>>();

function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
    return entry.data as T;
  }
  cache.delete(key);
  return null;
}

function setCache(key: string, data: any) {
  cache.set(key, { data, timestamp: Date.now() });
}

function dedupedFetch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  // Check cache
  const cached = getCached<T>(key);
  if (cached !== null) return Promise.resolve(cached);

  // Check inflight
  const inflightReq = inflight.get(key);
  if (inflightReq) return inflightReq;

  const promise = fetcher().then((data) => {
    setCache(key, data);
    inflight.delete(key);
    return data;
  }).catch((err) => {
    inflight.delete(key);
    throw err;
  });

  inflight.set(key, promise);
  return promise;
}

// ============ Overview APIs ============
export const fetchMarketOverview = () =>
  dedupedFetch<MarketOverviewData>('market-overview', () =>
    api.get<MarketOverviewData>('/market-overview').then(r => r.data));

export const fetchMarketData = (key: string) =>
  dedupedFetch(`market/${key}`, () =>
    api.get(`/market/${key}`).then(r => r.data));

export const fetchSectors = () =>
  dedupedFetch<SectorItem[]>('sectors', () =>
    api.get<SectorItem[]>('/sectors').then(r => r.data));

export const fetchNews = (sentiment?: string, category?: string) => {
  const cacheKey = `news:${sentiment || 'all'}:${category || ''}`;
  const params: Record<string, string> = { limit: '40' };
  if (sentiment && sentiment !== 'all') params.sentiment = sentiment;
  if (category) params.category = category;
  return dedupedFetch<NewsFeedData>(cacheKey, () =>
    api.get<NewsFeedData>('/news', { params }).then(r => r.data));
};

export const fetchGeopolitical = () =>
  dedupedFetch<GeopoliticalData>('geopolitical', () =>
    api.get<GeopoliticalData>('/geopolitical').then(r => r.data));

export const fetchSentimentTrend = () =>
  dedupedFetch<SentimentPoint[]>('sentiment-trend', () =>
    api.get<SentimentPoint[]>('/sentiment-trend').then(r => r.data));

export const fetchTrending = () =>
  dedupedFetch<TrendingData>('trending', () =>
    api.get<TrendingData>('/trending').then(r => r.data));

export const fetchEvents = () =>
  dedupedFetch<EventsData>('events', () =>
    api.get<EventsData>('/events').then(r => r.data));

export const fetchSearch = (query: string) =>
  api.get<SearchData>(`/search/${encodeURIComponent(query)}`).then(r => r.data);

export const fetchOpportunityRadar = (market: 'all' | 'hk' | 'us' = 'all', lookbackDays = 10) =>
  api.get<OpportunityRadar>('/opportunity-radar', { params: { market, lookback_days: lookbackDays, mode: 'balanced' } }).then(r => r.data);

export const fetchPaperBooks = () =>
  api.get<PaperBooksResponse>('/paper/books').then(r => r.data);

export const postPaperOrder = (payload: PaperOrderInput) =>
  api.post<PaperOrderResponse>('/paper/orders', payload).then(r => {
    cache.delete('paper-books');
    return r.data;
  });

export const fetchPaperBookPerformance = (book: 'hkd' | 'usd', windowDays = 20) =>
  api.get<PaperBookPerformance>('/paper/performance', { params: { book, window_days: windowDays } }).then(r => r.data);

// ============ Deep Analysis APIs ============
export const fetchStocks = () =>
  dedupedFetch<string[]>('stocks', () =>
    api.get<any[]>('/stocks').then(r => r.data.map((t: any) => t.symbol || t)));

export const postStock = (symbol: string, name?: string) =>
  api.post('/stocks', { symbol, name }).then(r => r.data);

export const fetchOHLC = (symbol: string) =>
  api.get<OHLCRow[]>(`/stocks/${symbol}/ohlc`).then(r => r.data);

export const fetchStockNews = (symbol: string, date?: string) => {
  const params: Record<string, string> = {};
  if (date) params.date = date;
  return api.get<StockNewsItem[]>(`/news/${symbol}`, { params }).then(r => r.data);
};

export const fetchParticles = (symbol: string) =>
  api.get<Particle[]>(`/news/${symbol}/particles`).then(r => r.data);

export const fetchCategories = (symbol: string) =>
  api.get<CategoriesResponse>(`/news/${symbol}/categories`).then(r => r.data);

export const fetchKline = (symbol: string, period: string = '1mo') =>
  api.get(`/kline/${symbol}`, { params: { period } }).then(r => r.data);

export const fetchPrediction = (symbol: string) =>
  api.get(`/predict/${symbol}`).then(r => r.data);

export const fetchSimilarDays = (symbol: string, date: string) =>
  api.get<SimilarDaysData>(`/predict/${symbol}/similar-days`, { params: { date } }).then(r => r.data);

export const fetchForecast = (symbol: string, windowDays: number) =>
  api.get<Forecast>(`/predict/${symbol}/forecast`, { params: { window: windowDays } }).then(r => r.data);

export const fetchQuantStatus = (symbol: string) =>
  api.get<QuantStatus>(`/predict/${symbol}/quant`).then(r => r.data);

export const fetchRiskBrief = (symbol: string) =>
  api.get<RiskBrief>(`/predict/${symbol}/risk-brief`).then(r => r.data);

export const fetchDecisionBoard = () =>
  api.get<DecisionBoard>('/predict/decision-board').then(r => r.data);

export const fetchStrategyMonitor = () =>
  api.get<StrategyMonitor>('/predict/strategy-monitor').then(r => r.data);

export const fetchCatalystRadar = (lookbackDays = 10) =>
  api.get<CatalystRadar>('/predict/catalyst-radar', { params: { lookback_days: lookbackDays } }).then(r => r.data);

export const fetchTradeSetups = (capital = 100000, lookbackDays = 10) =>
  api.get<TradeSetups>('/predict/trade-setups', { params: { capital, lookback_days: lookbackDays } }).then(r => r.data);

export const fetchPortfolioPlan = (capital = 100000) =>
  api.get<PortfolioPlan>('/predict/portfolio-plan', { params: { capital } }).then(r => r.data);

export const fetchPaperPerformance = (capital = 100000, windowDays = 60) =>
  api.get<PaperPerformance>('/portfolio/paper-performance', { params: { capital, window_days: windowDays } }).then(r => r.data);

export const fetchPortfolioHoldings = () =>
  api.get<PortfolioHoldings>('/portfolio').then(r => r.data);

export const putPortfolioPosition = (symbol: string, payload: PortfolioPositionInput) =>
  api.put<PortfolioHoldings>(`/portfolio/positions/${encodeURIComponent(symbol)}`, payload).then(r => r.data);

export const deletePortfolioPosition = (symbol: string) =>
  api.delete<PortfolioHoldings>(`/portfolio/positions/${encodeURIComponent(symbol)}`).then(r => r.data);

export const fetchActionCenter = (capital = 100000) =>
  api.get<ActionCenter>('/portfolio/action-center', { params: { capital } }).then(r => r.data);

export const fetchInvestmentBrief = (capital = 100000) =>
  api.get<InvestmentBrief>('/portfolio/investment-brief', { params: { capital } }).then(r => r.data);

export const fetchRebalancePlan = (capital = 100000) =>
  api.get<RebalancePlan>('/portfolio/rebalance', { params: { capital } }).then(r => r.data);

export const fetchTradeJournal = () =>
  api.get<TradeJournal>('/portfolio/trades').then(r => r.data);

export const fetchTradeReview = () =>
  api.get<TradeReview>('/portfolio/trade-review').then(r => r.data);

export const postTradeJournalEntry = (payload: TradeJournalInput) =>
  api.post<TradeJournal>('/portfolio/trades', payload).then(r => r.data);

export const putTradeJournalEntry = (tradeId: number, payload: TradeJournalInput) =>
  api.put<TradeJournal>(`/portfolio/trades/${tradeId}`, payload).then(r => r.data);

export const deleteTradeJournalEntry = (tradeId: number) =>
  api.delete<TradeJournal>(`/portfolio/trades/${tradeId}`).then(r => r.data);

export const postTrainQuantModel = (symbol: string, horizon: string, backtest = true) =>
  api.post<QuantTrainResponse>(`/predict/${symbol}/train`, null, { params: { horizon, backtest } }).then(r => r.data);

export const postAnalyzeNews = (symbol: string, limit = 100, engine = 'auto') =>
  api.post<QuantAnalyzeResponse>(`/predict/${symbol}/analyze-news`, null, { params: { limit, engine } }).then(r => r.data);

export const postDeepAnalysis = (newsId: string, symbol: string) =>
  api.post('/analysis/deep', { news_id: newsId, symbol }).then(r => r.data);

export const postStory = (symbol: string) =>
  api.post('/analysis/story', { symbol }).then(r => r.data);

export const postRangeAnalysis = (symbol: string, startDate: string, endDate: string, question?: string) =>
  api.post<RangeAnalysis>('/analysis/range-local', { symbol, start_date: startDate, end_date: endDate, question }).then(r => r.data);

export const fetchRangeNews = (symbol: string, startDate: string, endDate: string) =>
  api.get<RangeNewsResponse>(`/news/${symbol}/range`, { params: { start: startDate, end: endDate } }).then(r => r.data);

export const fetchSectorAnalysis = (key: string) =>
  dedupedFetch<SectorAnalysisData>(`sector/${key}`, () =>
    api.get<SectorAnalysisData>(`/sector/${key}`).then(r => r.data));
