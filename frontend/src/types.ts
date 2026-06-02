// ============ Market Overview ============
export interface MarketItem {
  symbol: string;
  name: string;
  en?: string;
  icon?: string;
  price: number;
  change_pct: number;
  change?: number;
  sparkline?: number[];
}

export interface MarketStatus {
  status: string;
  label?: string;
  minutes_left?: number;
  next?: string;
}

export interface MarketOverviewData {
  markets: {
    us: { indices: MarketItem[]; stocks?: MarketItem[]; sectors?: SectorItem[] };
    hk: { indices: MarketItem[]; stocks?: MarketItem[] };
    cn: { indices: MarketItem[] };
    jp?: { indices: MarketItem[]; stocks?: MarketItem[] };
    eu?: { indices: MarketItem[]; stocks?: MarketItem[] };
  };
  crypto?: MarketItem[];
  commodities?: MarketItem[];
  status?: Record<string, MarketStatus>;
}

export interface SectorItem {
  symbol: string;
  name: string;
  icon?: string;
  change_pct: number;
}

// ============ News ============
export interface NewsTag {
  type: string;
  key?: string;
  value: string;
}

export interface NewsArticle {
  id?: string;
  title: string;
  url: string;
  source: string;
  published: string;
  sentiment: string;
  tags?: NewsTag[];
  impact_tags?: string[];
  feed_category?: string;
}

export interface NewsFeedData {
  articles: NewsArticle[];
}

// ============ Geopolitical ============
export interface RiskCategory {
  key?: string;
  name: string;
  score: number;
}

export interface GeopoliticalData {
  overall: number;
  categories: RiskCategory[];
}

// ============ Sentiment Trend ============
export interface SentimentPoint {
  date: string;
  score: number;
}

// ============ Trending ============
export interface TrendingTopic {
  keyword: string;
  mentions: number;
}

export interface TrendingData {
  topics: TrendingTopic[];
}

// ============ Events ============
export interface CalendarEvent {
  category: string;
  date: string;
  title: string;
  summary: string;
  impact?: string;
  source?: string;
  url?: string;
  watch_points?: string[];
  related_stocks?: string[];
}

export interface IPOItem {
  name: string;
  expected_date: string;
  sector: string;
  valuation: string;
  description: string;
  status?: string;
  watch_points?: string[];
  related_tickers?: string[];
}

export interface SupplyChainTheme {
  theme: string;
  trigger: string;
  upstream: string[];
  midstream: string[];
  downstream: string[];
  hk_tickers: string[];
  us_tickers: string[];
  watch_signals: string[];
  risk: string;
}

export interface EventsData {
  events: CalendarEvent[];
  ipos: IPOItem[];
  supply_chains?: SupplyChainTheme[];
}

// ============ Opportunity Radar / Paper Trading ============
export interface OpportunityEvidence {
  type: 'news' | 'event' | 'catalyst' | string;
  title: string;
  source: string;
  published: string;
  url?: string;
  sentiment?: string;
}

export interface SuggestedPaperAction {
  allowed: boolean;
  book_id: 'hkd' | 'usd' | null;
  symbol: string | null;
  side: 'buy' | 'sell' | 'observe';
  notional: number;
  reason: string;
}

export interface EligiblePaperSymbol {
  symbol: string;
  book_id: 'hkd' | 'usd';
  notional: number;
}

export interface OpportunityAlert {
  id: string;
  theme: string;
  theme_label: string;
  market: 'all' | 'hk' | 'us';
  signal_level: 'strong' | 'watch';
  score: number;
  score_components: Record<string, number | null>;
  title: string;
  thesis: string;
  evidence: OpportunityEvidence[];
  primary_symbols: string[];
  related_symbols: string[];
  risks: string[];
  suggested_paper_action: SuggestedPaperAction;
  eligible_paper_symbols: EligiblePaperSymbol[];
}

export interface OpportunityTheme {
  key: string;
  label: string;
  market: 'all' | 'hk' | 'us';
  alert_count: number;
  strong_count: number;
  watch_count: number;
  top_score: number;
  primary_symbols: string[];
}

export interface OpportunityRadar {
  generated_at: string;
  market: 'all' | 'hk' | 'us';
  lookback_days: number;
  mode: 'balanced';
  summary: {
    themes: number;
    alerts: number;
    strong: number;
    watch: number;
    paper_eligible_symbols: number;
    top_theme?: string | null;
    top_score?: number | null;
  };
  themes: OpportunityTheme[];
  alerts: OpportunityAlert[];
  data_quality: {
    news_count: number;
    event_count: number;
    ipo_count: number;
    catalyst_rows: number;
    trade_setup_rows: number;
    rss_error?: string | null;
    event_error?: string | null;
    catalyst_error?: string | null;
    trade_setup_error?: string | null;
    notes: string[];
  };
}

export interface PaperOrder {
  id: number;
  book_id: 'hkd' | 'usd';
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  notional: number;
  reason?: string | null;
  radar_alert_id?: string | null;
  trade_date: string;
  created_at: string;
}

export interface PaperPosition {
  book_id: 'hkd' | 'usd';
  symbol: string;
  shares: number;
  avg_cost?: number | null;
  realized_pnl: number;
  updated_at?: string | null;
  latest_close?: number | null;
  price_date?: string | null;
  market_value?: number | null;
  cost_basis?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
}

export interface PaperBook {
  id: 'hkd' | 'usd';
  label: string;
  currency: 'HKD' | 'USD';
  initial_cash: number;
  cash: number;
  market_value: number;
  equity: number;
  total_return?: number | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
}

export interface PaperBooksResponse {
  generated_at: string;
  books: PaperBook[];
}

export interface PaperOrderInput {
  book_id: 'hkd' | 'usd';
  symbol: string;
  side: 'buy' | 'sell';
  notional: number;
  reason?: string;
  radar_alert_id?: string | null;
}

export interface PaperOrderResponse {
  order_id: number;
  book: PaperBook;
}

export interface PaperBookPerformancePoint {
  date: string;
  equity: number;
  market_value: number;
  return?: number | null;
}

export interface PaperBookPerformance {
  generated_at: string;
  book_id: 'hkd' | 'usd';
  currency: 'HKD' | 'USD';
  window_days: number;
  status: 'empty' | 'tracking';
  label: string;
  message: string;
  summary: {
    positions: number;
    cash: number;
    market_value: number;
    equity: number;
    total_return?: number | null;
    window_return?: number | null;
    annualized_volatility?: number | null;
    max_drawdown?: number | null;
  };
  positions: PaperPosition[];
  orders: PaperOrder[];
  curve: PaperBookPerformancePoint[];
}

// ============ Search ============
export interface SearchResult {
  symbol: string;
  name: string;
  type?: string;
  sector?: string;
  aliases?: string[];
  source?: string;
}

export interface SearchData {
  results: SearchResult[];
}

export interface CompanyProfileNews {
  id: string;
  title: string;
  description?: string | null;
  publisher?: string | null;
  published_utc?: string | null;
  article_url?: string | null;
  image_url?: string | null;
  sentiment?: string | null;
  chinese_summary?: string | null;
}

export interface CompanyProfile {
  symbol: string;
  name: string;
  name_zh?: string | null;
  market?: string | null;
  sector?: string | null;
  industry?: string | null;
  website?: string | null;
  ir_url?: string | null;
  filings_url?: string | null;
  financials_url?: string | null;
  country?: string | null;
  currency?: string | null;
  employees?: number | null;
  summary?: string | null;
  summary_zh?: string | null;
  source?: string | null;
  fetched_at?: string | null;
  links?: Record<string, string>;
  recent_news: CompanyProfileNews[];
  data_status: {
    last_news_fetch?: string | null;
    last_ohlc_fetch?: string | null;
    profile_cache?: string | null;
    cache_policy: string;
    refresh_hint: string;
  };
}

// ============ Stock Deep Analysis ============
export interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Particle {
  id: string;
  d: string;        // trade_date
  s: string | null;  // sentiment
  r: string | null;  // relevance
  t: string;         // title (truncated)
  rt1: number | null; // ret_t1
}

export interface HoverData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
}

export interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

export interface ArticleSelection {
  newsId: string;
  date: string;
}

export interface StockNewsItem {
  news_id: string;
  trade_date: string;
  published_utc: string;
  title: string;
  description: string;
  publisher: string;
  article_url: string;
  image_url: string | null;
  relevance: string | null;
  key_discussion: string | null;
  sentiment: string | null;
  reason_growth: string | null;
  reason_decrease: string | null;
  category_tags?: Array<{ key: string; label: string }>;
  impact_label?: string;
  impact_reason?: string;
  next_watch?: string;
  ret_t0: number | null;
  ret_t1: number | null;
  ret_t3: number | null;
  ret_t5: number | null;
  ret_t10: number | null;
}

// ============ Category ============
export interface CategoryInfo {
  label: string;
  count: number;
  article_ids: string[];
  positive_ids: string[];
  negative_ids: string[];
  neutral_ids: string[];
}

export interface CategoriesResponse {
  categories: Record<string, CategoryInfo>;
  total: number;
}

// ============ Prediction / Forecast ============
export interface Driver {
  name: string;
  value: number;
  importance: number;
  z_score: number;
  contribution: number;
}

export interface HorizonPrediction {
  direction: 'up' | 'down';
  confidence: number;
  model_type?: string;
  model_quality?: string;
  model_quality_label?: string;
  model_quality_message?: string;
  model_cv_lift?: number | null;
  strict_strategy_excess_return?: number | null;
  strict_strategy_return?: number | null;
  strict_strategy_sharpe?: number | null;
  trade_ready?: boolean;
  signal_gate?: SignalGate;
  top_drivers: Driver[];
  feature_groups?: QuantFeatureGroupMeta[];
  model_accuracy: number | null;
  baseline_accuracy: number | null;
}

export interface SignalGateCheck {
  key: string;
  label: string;
  ok: boolean;
  value?: number | null;
  message: string;
}

export interface SignalGate {
  status: 'research-only' | 'watch' | 'candidate';
  label: string;
  message: string;
  actionable: boolean;
  checks: SignalGateCheck[];
}

export interface SimilarPeriod {
  period_start: string;
  period_end: string;
  similarity: number;
  avg_sentiment: number;
  n_articles: number;
  ret_after_5d: number | null;
  ret_after_10d: number | null;
}

export interface Headline {
  date: string;
  title: string;
  sentiment: string;
  summary: string;
}

export interface ImpactArticle {
  news_id: string;
  date: string;
  title: string;
  sentiment: string;
  relevance: string | null;
  key_discussion: string;
  ret_t0: number | null;
  ret_t1: number | null;
}

export interface NewsSummary {
  total: number;
  positive: number;
  negative: number;
  neutral: number;
  sentiment_ratio: number;
  top_headlines: Headline[];
  top_impact: ImpactArticle[];
}

export interface SimilarStats {
  count: number;
  up_ratio_5d: number;
  up_ratio_10d: number;
  avg_ret_5d: number | null;
  avg_ret_10d: number | null;
}

export interface DeepAnalysis {
  news_id: string;
  discussion: string;
  growth_reasons: string;
  decrease_reasons: string;
}

export interface Forecast {
  symbol: string;
  window_days: number;
  forecast_date: string;
  news_summary: NewsSummary;
  prediction: Record<string, HorizonPrediction>;
  similar_periods: SimilarPeriod[];
  similar_stats: SimilarStats;
  conclusion: string;
}

// ============ Quant Lab ============
export interface QuantCoverage {
  ohlc_rows: number;
  aligned_news: number;
  analyzed_news: number;
  pending_analysis?: number;
  layer0_passed?: number;
  layer0_filtered?: number;
  sentiment?: Record<string, number>;
  universe_symbols?: string[];
}

export interface QuantDependency {
  available: boolean;
  error: string | null;
  name?: string | null;
  package?: string | null;
}

export interface QuantDataQuality {
  status: 'healthy' | 'watch' | 'stale' | 'insufficient' | 'unknown';
  label: string;
  message: string;
  ready_for_modeling: boolean;
  usable_for_research: boolean;
  issues: string[];
  first_ohlc_date?: string | null;
  latest_ohlc_date?: string | null;
  ohlc_age_days?: number | null;
  latest_news_published_utc?: string | null;
  news_age_hours?: number | null;
  latest_labeled_news_published_utc?: string | null;
  labeled_news_age_hours?: number | null;
  label_coverage?: number | null;
  labelable_articles?: number | null;
  symbol_count?: number | null;
  aligned_news_per_symbol?: number | null;
  analyzed_news_per_symbol?: number | null;
}

export interface QuantFeatureMeta {
  name: string;
  importance: number;
}

export interface QuantFeatureGroupMeta {
  key: string;
  label: string;
  importance: number;
  feature_count: number;
  top_feature: string | null;
}

export interface QuantFeatureGroupTest {
  key: string;
  label: string;
  feature_count: number;
  status: 'edge' | 'watch' | 'weak' | 'insufficient' | 'error';
  accuracy?: number | null;
  baseline?: number | null;
  cv_lift?: number | null;
  n_folds?: number | null;
  total_predictions?: number | null;
  error?: string | null;
}

export interface QuantBacktestSummary {
  available: boolean;
  overall_accuracy: number | null;
  overall_baseline: number | null;
  overall_precision: number | null;
  overall_recall: number | null;
  overall_f1: number | null;
  n_folds: number | null;
  total_predictions: number | null;
  long_cash?: QuantStrategySummary | null;
  long_short?: QuantStrategySummary | null;
  non_overlap_long_cash?: QuantStrategySummary | null;
  non_overlap_long_short?: QuantStrategySummary | null;
  feature_group_tests?: QuantFeatureGroupTest[];
  per_ticker?: QuantTickerDiagnostic[];
}

export interface QuantStrategySummary {
  mode: string;
  total_return: number | null;
  benchmark_return: number | null;
  excess_return: number | null;
  average_return: number | null;
  average_daily_return?: number | null;
  benchmark_average_return?: number | null;
  volatility: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  exposure: number | null;
  trades: number;
  rebalance_period_days?: number | null;
  sampled_periods?: number | null;
}

export interface QuantTickerDiagnostic {
  symbol: string;
  n: number;
  accuracy: number | null;
  baseline: number | null;
  classification_lift: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  strategy_return: number | null;
  benchmark_return: number | null;
  strategy_excess_return: number | null;
  strategy_sharpe: number | null;
  strict_strategy_return: number | null;
  strict_strategy_excess_return: number | null;
  strict_strategy_sharpe: number | null;
  max_drawdown: number | null;
  exposure: number | null;
  trades: number;
  verdict: 'edge' | 'watch' | 'weak';
}

export interface QuantModelQuality {
  status: string;
  label: string;
  message: string;
  holdout_lift: number | null;
  cv_lift: number | null;
  strategy_excess_return?: number | null;
  strategy_return?: number | null;
  strategy_sharpe?: number | null;
  strict_strategy_excess_return?: number | null;
  strict_strategy_return?: number | null;
  strict_strategy_sharpe?: number | null;
  trade_ready: boolean;
}

export interface QuantModelState {
  horizon: string;
  trained: boolean;
  model_file: string | null;
  model_type: string | null;
  model_package: string | null;
  trained_at: string | null;
  accuracy: number | null;
  baseline: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  top_features: QuantFeatureMeta[];
  feature_groups?: QuantFeatureGroupMeta[];
  quality: QuantModelQuality;
  backtest: QuantBacktestSummary;
}

export interface QuantJob {
  symbol: string;
  horizon: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  backtest: boolean;
  requested_at?: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface QuantAnalysisJob {
  symbol: string;
  kind: 'layer1';
  status: 'queued' | 'running' | 'complete' | 'failed';
  limit: number;
  engine: string;
  requested_at?: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result?: Record<string, unknown>;
}

export interface QuantStatus {
  symbol: string;
  coverage: QuantCoverage;
  data_quality?: QuantDataQuality;
  dependencies: Record<string, QuantDependency>;
  models: QuantModelState[];
  jobs: QuantJob[];
  analysis_jobs?: QuantAnalysisJob[];
}

export interface QuantTrainResponse {
  symbol: string;
  horizon: string;
  job: QuantJob;
}

export interface QuantAnalyzeResponse {
  symbol: string;
  job: QuantAnalysisJob;
}

// ============ Risk Brief ============
export interface RiskBriefPrediction {
  direction?: 'up' | 'down';
  confidence?: number | null;
  model_quality?: string | null;
  trade_ready?: boolean;
  gate_status?: string | null;
  gate_label?: string | null;
  actionable?: boolean;
  failed_checks?: string[];
  error?: string;
}

export interface RiskBrief {
  symbol: string;
  as_of: string;
  status: 'research-only' | 'candidate';
  label: string;
  message: string;
  latest_close: number;
  volatility_20d: number | null;
  volatility_60d: number | null;
  annualized_volatility_20d: number | null;
  atr_14: number | null;
  atr_pct: number | null;
  drawdown_60d: number | null;
  trend_20d: number | null;
  trend_60d: number | null;
  risk_budget: {
    position_sizing_enabled: boolean;
    max_portfolio_risk_pct: number;
    reference_stop_distance_pct: number | null;
    actionable_horizons: string[];
  };
  predictions: Record<string, RiskBriefPrediction>;
  notes: string[];
}

// ============ Decision Board ============
export interface DecisionBoardGate {
  horizon: string;
  direction?: 'up' | 'down';
  confidence?: number | null;
  model_quality?: string | null;
  trade_ready: boolean;
  gate_status?: string | null;
  gate_label?: string | null;
  actionable: boolean;
  failed_checks: string[];
}

export interface DecisionBoardHeadline {
  date: string;
  title: string;
  sentiment: string;
  summary: string;
}

export interface DecisionBoardCoverage {
  status: string;
  label: string;
  issues: string[];
  ohlc_rows: number;
  latest_ohlc_date?: string | null;
  analyzed_news: number;
  pending_news: number;
  label_coverage?: number | null;
}

export interface DecisionBoardRow {
  rank: number;
  symbol: string;
  decision_status: 'candidate' | 'watch' | 'research-only' | 'blocked' | 'unavailable';
  label: string;
  score: number;
  action: string;
  as_of?: string | null;
  latest_close?: number | null;
  trend_20d?: number | null;
  trend_60d?: number | null;
  drawdown_60d?: number | null;
  annualized_volatility_20d?: number | null;
  atr_pct?: number | null;
  risk_status?: string | null;
  risk_label?: string | null;
  data_quality_status: string;
  data_quality_label: string;
  coverage: DecisionBoardCoverage;
  sentiment_ratio_30d: number;
  news_count_30d: number;
  positive_news_30d: number;
  negative_news_30d: number;
  neutral_news_30d: number;
  actionable_horizons: string[];
  gates: DecisionBoardGate[];
  blockers: string[];
  notes: string[];
  headlines: DecisionBoardHeadline[];
  error?: string;
}

export interface DecisionBoard {
  generated_at: string;
  lookback_days: number;
  universe: string[];
  summary: {
    total: number;
    candidates: number;
    watch: number;
    research_only: number;
    blocked: number;
    unavailable: number;
    best_symbol?: string | null;
  };
  rows: DecisionBoardRow[];
}

// ============ Strategy Monitor ============
export interface StrategyFeatureGroupEdge {
  key?: string | null;
  label: string;
  cv_lift: number;
  accuracy?: number | null;
  baseline?: number | null;
}

export interface StrategyTickerDiagnostic {
  n: number;
  accuracy?: number | null;
  baseline?: number | null;
  cv_lift?: number | null;
  strategy_excess_return?: number | null;
  strict_strategy_excess_return?: number | null;
  strict_strategy_sharpe?: number | null;
  verdict: 'edge' | 'watch' | 'weak';
}

export interface StrategyMonitorRow {
  symbol: string;
  horizon: 't1' | 't5';
  model_symbol: string;
  source: 'symbol' | 'unified-fallback';
  trained: boolean;
  status: 'ready' | 'watch' | 'blocked' | 'missing';
  label: string;
  action: string;
  issues: string[];
  model_type?: string | null;
  model_package?: string | null;
  test_end?: string | null;
  model_age_days?: number | null;
  quality_status?: string | null;
  quality_label?: string | null;
  holdout_lift?: number | null;
  cv_lift?: number | null;
  strategy_excess_return?: number | null;
  strategy_sharpe?: number | null;
  strict_strategy_excess_return?: number | null;
  strict_strategy_sharpe?: number | null;
  trade_ready: boolean;
  backtest_available: boolean;
  total_predictions: number;
  feature_group_edges: StrategyFeatureGroupEdge[];
  top_driver_group?: string | null;
  coverage_status?: string | null;
  coverage_label?: string | null;
  ohlc_age_days?: number | null;
  label_coverage?: number | null;
  analyzed_news?: number | null;
  per_ticker?: StrategyTickerDiagnostic | null;
}

export interface StrategyMonitorAction {
  priority: 'high' | 'medium' | 'low';
  title: string;
  message: string;
  action: string;
  evidence: string[];
}

export interface StrategyMonitor {
  generated_at: string;
  status: 'setup' | 'research-only' | 'watch' | 'candidate-review';
  label: string;
  message: string;
  horizons: string[];
  summary: {
    rows: number;
    symbols: number;
    ready: number;
    watch: number;
    blocked: number;
    missing: number;
    unified_fallback: number;
    trained: number;
    best_cv_lift?: number | null;
    best_strict_excess_return?: number | null;
  };
  actions: StrategyMonitorAction[];
  rows: StrategyMonitorRow[];
}

// ============ Catalyst Radar ============
export interface CatalystHeadline {
  date: string;
  title: string;
  publisher: string;
  url: string;
  sentiment: 'positive' | 'negative' | 'neutral' | string;
  relevance?: string | null;
  summary?: string | null;
  ret_t0?: number | null;
  ret_t1?: number | null;
  ret_t5?: number | null;
}

export interface CatalystRow {
  symbol: string;
  rank: number;
  status: 'hot' | 'watch' | 'quiet' | 'needs-labels';
  label: string;
  message: string;
  action: string;
  score: number;
  bias: 'bullish' | 'bearish' | 'mixed' | 'neutral';
  bias_label: string;
  latest_trade_date?: string | null;
  latest_close?: number | null;
  price_date?: string | null;
  news_count: number;
  positive: number;
  negative: number;
  neutral: number;
  sentiment_ratio: number;
  pending_labels: number;
  avg_abs_ret_t0?: number | null;
  avg_abs_ret_t1?: number | null;
  avg_abs_ret_t5?: number | null;
  avg_ret_t0?: number | null;
  avg_ret_t1?: number | null;
  avg_ret_t5?: number | null;
  trend_5d?: number | null;
  trend_20d?: number | null;
  headlines: CatalystHeadline[];
}

export interface CatalystRadar {
  generated_at: string;
  lookback_days: number;
  start_date: string;
  latest_trade_date?: string | null;
  status: 'hot' | 'watch' | 'quiet' | 'needs-labels';
  label: string;
  message: string;
  summary: {
    symbols: number;
    hot: number;
    watch: number;
    needs_labels: number;
    bullish: number;
    bearish: number;
    total_articles: number;
    pending_labels: number;
    top_symbol?: string | null;
    top_score?: number | null;
  };
  rows: CatalystRow[];
}

// ============ Trade Setups ============
export interface TradeSetupLevels {
  as_of: string;
  latest_close: number;
  atr_14: number;
  atr_pct: number;
  support_20d: number;
  resistance_20d: number;
  support_60d: number;
  resistance_60d: number;
  near_breakout: boolean;
  extended: boolean;
}

export interface TradeSetupRow {
  symbol: string;
  rank: number;
  status: 'candidate' | 'paper-watch' | 'avoid' | 'wait' | 'setup';
  label: string;
  message: string;
  action: string;
  setup_type?: string | null;
  score: number;
  catalyst_score: number;
  decision_score: number;
  decision_status?: string | null;
  bias?: string | null;
  bias_label?: string | null;
  latest_headline?: string | null;
  news_count?: number | null;
  sentiment_ratio?: number | null;
  trend_5d?: number | null;
  trend_20d?: number | null;
  entry_low?: number | null;
  entry_high?: number | null;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  risk_reward_1?: number | null;
  risk_reward_2?: number | null;
  max_position_notional?: number | null;
  levels?: TradeSetupLevels | null;
  rationale?: string[];
}

export interface TradeSetups {
  generated_at: string;
  capital: number;
  lookback_days: number;
  status: 'candidate-review' | 'paper-watch' | 'risk-review' | 'wait';
  label: string;
  message: string;
  summary: {
    rows: number;
    candidates: number;
    paper_watch: number;
    avoid: number;
    wait: number;
    top_symbol?: string | null;
    top_status?: string | null;
  };
  rows: TradeSetupRow[];
  sources: {
    catalyst_status?: string | null;
    decision_board_status?: string | null;
    mode?: string | null;
  };
}

// ============ Portfolio Plan ============
export interface PortfolioAllocation {
  symbol: string;
  rank?: number | null;
  decision_status: string;
  allocation_status: 'live-candidate' | 'research-watch' | 'research-only' | 'blocked' | 'excluded';
  label: string;
  score?: number | null;
  latest_close?: number | null;
  live_weight: number;
  live_notional: number;
  live_shares: number;
  paper_weight: number;
  paper_notional: number;
  paper_shares: number;
  stop_distance_pct: number | null;
  max_risk_pct: number | null;
  annualized_volatility_20d?: number | null;
  drawdown_60d?: number | null;
  trend_20d?: number | null;
  sentiment_ratio_30d?: number | null;
  actionable_horizons: string[];
  blockers: string[];
  reasons: string[];
}

export interface PortfolioPlan {
  generated_at: string;
  capital: number;
  lookback_days: number;
  status: 'research-only' | 'candidate-review';
  label: string;
  message: string;
  universe: string[];
  controls: {
    max_live_gross_weight: number;
    max_single_live_weight: number;
    max_account_risk_pct: number;
    max_position_risk_pct: number;
    paper_gross_weight: number;
    min_stop_distance_pct: number;
    max_stop_distance_pct: number;
  };
  summary: {
    total: number;
    candidate_count: number;
    watch_count: number;
    blocked_count: number;
    live_weight: number;
    live_notional: number;
    paper_weight: number;
    paper_notional: number;
  };
  allocations: PortfolioAllocation[];
}

// ============ Paper Performance ============
export interface PaperPerformanceWindow {
  window_days: number;
  total_return: number | null;
  benchmark_return: number | null;
  active_return: number | null;
  ending_value: number | null;
  benchmark_value: number | null;
}

export interface PaperPerformanceContribution {
  symbol: string;
  label?: string | null;
  weight: number;
  paper_notional: number;
  latest_close?: number | null;
  total_return: number | null;
  contribution: number | null;
  score?: number | null;
  allocation_status?: string | null;
}

export interface PaperPerformancePoint {
  date: string;
  paper_value: number;
  benchmark_value: number;
  paper_return: number;
  benchmark_return: number;
}

export interface PaperPerformance {
  generated_at: string;
  capital: number;
  window_days: number;
  status: 'setup' | 'tracking' | 'outperforming' | 'lagging';
  label: string;
  message: string;
  plan_status?: string | null;
  summary: {
    allocation_count: number;
    paper_weight: number;
    paper_notional: number;
    total_return: number | null;
    benchmark_return: number | null;
    active_return: number | null;
    ending_value: number | null;
    benchmark_value: number | null;
    annualized_volatility: number | null;
    max_drawdown: number | null;
    best_contributor?: string | null;
    worst_contributor?: string | null;
  };
  windows: PaperPerformanceWindow[];
  contributions: PaperPerformanceContribution[];
  curve: PaperPerformancePoint[];
}

// ============ Portfolio Holdings ============
export interface PortfolioPositionInput {
  shares: number;
  avg_cost?: number | null;
  thesis?: string;
}

export interface PortfolioPosition {
  symbol: string;
  shares: number;
  avg_cost: number | null;
  thesis: string;
  created_at?: string | null;
  updated_at?: string | null;
  latest_close: number | null;
  price_date?: string | null;
  market_value: number;
  cost_basis: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  weight: number;
  risk_status?: string | null;
  risk_label?: string | null;
  atr_pct: number | null;
  drawdown_60d: number | null;
  trend_20d: number | null;
  stop_distance_pct: number | null;
  estimated_stop_risk: number;
  actionable_horizons: string[];
  failed_checks: string[];
  risk_error?: string | null;
}

export interface PortfolioHoldings {
  generated_at: string;
  status: 'empty' | 'monitored' | 'research-only' | 'elevated';
  label: string;
  message: string;
  summary: {
    position_count: number;
    total_market_value: number;
    total_cost_basis: number | null;
    total_unrealized_pnl: number | null;
    total_unrealized_pnl_pct: number | null;
    estimated_stop_risk: number;
    estimated_stop_risk_pct: number;
    gate_blocked_positions: number;
    largest_position?: string | null;
  };
  positions: PortfolioPosition[];
}

// ============ Action Center ============
export interface ActionCenterItem {
  key: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  category: 'portfolio' | 'risk' | 'gate' | 'data' | 'research' | 'model';
  symbol?: string | null;
  title: string;
  message: string;
  action: string;
  metric?: number | null;
  evidence: string[];
}

export interface ActionCenter {
  generated_at: string;
  status: 'calm' | 'review' | 'attention';
  label: string;
  message: string;
  summary: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    portfolio_status?: string | null;
    decision_best_symbol?: string | null;
    live_weight?: number | null;
  };
  actions: ActionCenterItem[];
}

// ============ Investment Brief ============
export interface InvestmentBriefPriority {
  source: 'action-center' | 'strategy-monitor' | 'trade-review';
  priority: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  symbol?: string | null;
  title: string;
  message: string;
  action: string;
  evidence: string[];
}

export interface InvestmentBriefResearchRow {
  symbol: string;
  rank?: number | null;
  score?: number | null;
  label?: string | null;
  decision_status?: string | null;
  action?: string | null;
  sentiment_ratio_30d?: number | null;
  trend_20d?: number | null;
  risk_label?: string | null;
  data_quality_label?: string | null;
  strategy_status?: 'ready' | 'watch' | 'blocked' | 'missing' | null;
  strategy_horizon?: string | null;
  strategy_reason?: string | null;
  blockers: string[];
}

export interface InvestmentBriefAllocation {
  symbol: string;
  label?: string | null;
  allocation_status?: string | null;
  live_weight: number;
  live_notional: number;
  paper_weight: number;
  paper_notional: number;
  score?: number | null;
  reasons: string[];
}

export interface InvestmentBrief {
  generated_at: string;
  capital: number;
  status: 'attention' | 'research-only' | 'candidate-review' | 'paper-ready';
  label: string;
  message: string;
  mode: string;
  summary: {
    portfolio_status?: string | null;
    position_count: number;
    action_items: number;
    high_priority_actions: number;
    live_ready_horizons: number;
    watch_horizons: number;
    blocked_horizons: number;
    live_weight: number;
    paper_weight: number;
    trade_review_rate: number;
    missing_trade_reviews: number;
    top_symbol?: string | null;
  };
  priorities: InvestmentBriefPriority[];
  research_queue: InvestmentBriefResearchRow[];
  allocation_snapshot: InvestmentBriefAllocation[];
  notes: string[];
  sources: {
    action_center_status?: string | null;
    strategy_status?: string | null;
    portfolio_plan_status?: string | null;
    trade_review_status?: string | null;
    decision_board_best_symbol?: string | null;
  };
}

// ============ Rebalance Monitor ============
export interface RebalanceRow {
  symbol: string;
  status: 'off-gate' | 'research-hold' | 'add-candidate' | 'trim-candidate' | 'aligned' | 'research-watch' | 'paper-only' | 'excluded';
  label: string;
  message: string;
  actual_notional: number;
  actual_weight: number;
  live_target_notional: number;
  live_target_weight: number;
  live_delta_notional: number;
  live_delta_weight: number;
  paper_target_notional: number;
  paper_target_weight: number;
  paper_delta_notional: number;
  paper_delta_weight: number;
  latest_close?: number | null;
  shares: number;
  allocation_status?: string | null;
  decision_status?: string | null;
  score?: number | null;
  blockers: string[];
  reasons: string[];
}

export interface RebalancePlan {
  generated_at: string;
  capital: number;
  status: 'setup' | 'review' | 'candidate-review' | 'aligned';
  label: string;
  message: string;
  summary: {
    rows: number;
    off_gate: number;
    add_candidates: number;
    trim_candidates: number;
    live_gap_notional: number;
    paper_gap_notional: number;
    actual_market_value: number;
    live_target_notional: number;
    paper_target_notional: number;
  };
  rows: RebalanceRow[];
}

// ============ Trade Journal ============
export interface TradeJournalInput {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  trade_date?: string | null;
  thesis?: string;
  setup?: string;
  review?: string;
}

export interface TradeJournalEntry {
  id: number;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  trade_date: string;
  thesis: string;
  setup: string;
  review: string;
  created_at?: string | null;
  updated_at?: string | null;
  entry_notional: number;
  latest_close: number | null;
  price_date?: string | null;
  current_value: number | null;
  marked_pnl: number | null;
  marked_pnl_pct: number | null;
  risk_status?: string | null;
  risk_label?: string | null;
  actionable_horizons: string[];
  failed_checks: string[];
  risk_error?: string | null;
}

export interface TradeJournal {
  generated_at: string;
  status: 'empty' | 'needs-review' | 'gate-review' | 'reviewed';
  label: string;
  message: string;
  summary: {
    trade_count: number;
    buy_count: number;
    sell_count: number;
    total_notional: number;
    marked_pnl: number | null;
    missing_review: number;
    gate_blocked_trades: number;
  };
  trades: TradeJournalEntry[];
  created_id?: number;
}

// ============ Trade Review ============
export interface TradeReviewSetup {
  setup: string;
  trade_count: number;
  reviewed_count: number;
  review_rate: number;
  total_notional: number;
  marked_pnl: number | null;
  marked_pnl_pct: number | null;
  gate_blocked_trades: number;
  symbols: string[];
}

export interface TradeReviewPriority {
  id: number;
  symbol: string;
  trade_date: string;
  setup: string;
  side: 'buy' | 'sell';
  priority: 'high' | 'medium' | 'low';
  priority_score: number;
  reasons: string[];
  action: string;
  marked_pnl: number | null;
  marked_pnl_pct: number | null;
  review: string;
  thesis: string;
}

export interface TradeReviewMonth {
  month: string;
  trade_count: number;
  review_rate: number;
  total_notional: number;
  marked_pnl: number | null;
  marked_pnl_pct: number | null;
}

export interface TradeReview {
  generated_at: string;
  status: 'empty' | 'needs-review' | 'gate-review' | 'learning' | 'disciplined';
  label: string;
  message: string;
  summary: {
    trade_count: number;
    reviewed_count: number;
    review_rate: number;
    total_notional: number;
    marked_pnl: number | null;
    marked_pnl_pct: number | null;
    positive_count: number;
    negative_count: number;
    missing_review: number;
    gate_blocked_trades: number;
    setup_count: number;
    best_setup?: string | null;
    worst_setup?: string | null;
    avg_days_since_trade?: number | null;
  };
  setup_breakdown: TradeReviewSetup[];
  priority_reviews: TradeReviewPriority[];
  monthly: TradeReviewMonth[];
}

// ============ Similar Days ============
export interface NewsSnippet {
  title: string;
  sentiment: string | null;
}

export interface SimilarDay {
  date: string;
  similarity: number;
  sentiment_score: number;
  n_articles: number;
  ret_1d: number | null;
  rsi_14: number;
  ret_t1_after: number | null;
  ret_t5_after: number | null;
  news: NewsSnippet[];
}

export interface SimilarDaysData {
  symbol: string;
  target_date: string;
  target_features: Record<string, number | null>;
  similar_days: SimilarDay[];
  stats: {
    up_ratio_t1: number | null;
    up_ratio_t5: number | null;
    avg_ret_t1: number | null;
    avg_ret_t5: number | null;
    count: number;
  };
}

// ============ Range Analysis ============
export interface RangeAnalysis {
  symbol: string;
  start_date: string;
  end_date: string;
  price_change_pct: number;
  open_price: number;
  close_price: number;
  high_price: number;
  low_price: number;
  news_count: number;
  trading_days: number;
  question?: string;
  analysis: {
    summary: string;
    key_events: string[];
    bullish_factors: string[];
    bearish_factors: string[];
    trend_analysis: string;
  };
  error?: string;
}

// ============ Range News ============
export interface RangeNewsResponse {
  total: number;
  date_range: [string, string];
  articles: StockNewsItem[];
  top_bullish: StockNewsItem[];
  top_bearish: StockNewsItem[];
}

// ============ Sector Analysis ============
export interface SectorStock {
  symbol: string;
  name: string;
  price?: number;
  change_pct?: number;
  weight?: number;
}

export interface SectorAnalysisData {
  key: string;
  name: string;
  outlook?: {
    short_term?: { period?: string; view?: string; score?: number; reason?: string };
    medium_term?: { period?: string; view?: string; score?: number; reason?: string };
    long_term?: { period?: string; view?: string; score?: number; reason?: string };
  };
  drivers?: string[];
  risks?: string[];
  stocks?: SectorStock[];
  stock_performance?: Array<{ symbol: string; name?: string; price?: number; change?: number; change_pct?: number }> | Record<string, { price?: number; change_pct?: number }>;
}
