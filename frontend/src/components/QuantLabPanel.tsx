import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchQuantStatus, postAnalyzeNews, postTrainQuantModel } from '../api';
import type { QuantModelState, QuantStatus, QuantTickerDiagnostic } from '../types';

interface Props {
  symbol: string;
}

function pct(value: number | null | undefined): string {
  return value == null ? '-' : `${(value * 100).toFixed(1)}%`;
}

function pp(value: number | null | undefined): string {
  if (value == null) return '-';
  const diff = value * 100;
  return `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}pp`;
}

function holdoutLift(model: QuantModelState): string {
  return pp(model.quality?.holdout_lift);
}

function strategyReturn(model: QuantModelState): string {
  return pct(model.backtest.long_cash?.total_return);
}

function strategyExcess(model: QuantModelState): string {
  return pp(model.backtest.long_cash?.excess_return);
}

function strictStrategyReturn(model: QuantModelState): string {
  return pct(model.backtest.non_overlap_long_cash?.total_return);
}

function strictStrategyExcess(model: QuantModelState): string {
  return pp(model.backtest.non_overlap_long_cash?.excess_return);
}

function sharpe(value: number | null | undefined): string {
  return value == null ? '-' : value.toFixed(2);
}

function shortDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '-';
}

function ageDays(value: number | null | undefined): string {
  return value == null ? '-' : `${value}d`;
}

function ageHours(value: number | null | undefined): string {
  if (value == null) return '-';
  if (value < 24) return `${value.toFixed(1)}h`;
  return `${(value / 24).toFixed(1)}d`;
}

function statusLabel(status?: string): string {
  if (status === 'queued') return 'Queued';
  if (status === 'running') return 'Training';
  if (status === 'complete') return 'Complete';
  if (status === 'failed') return 'Failed';
  return 'Idle';
}

function diagnosticMetric(row: QuantTickerDiagnostic): string {
  return `${pp(row.classification_lift)} / ${pp(row.strict_strategy_excess_return ?? row.strategy_excess_return)}`;
}

function diagnosticRowClass(row: QuantTickerDiagnostic): string {
  return `quant-diagnostic-line ${row.verdict}`;
}

function driverWidth(value: number | null | undefined): string {
  if (value == null) return '0%';
  return `${Math.max(3, Math.min(value * 100, 100)).toFixed(1)}%`;
}

function groupTestClass(status?: string): string {
  return `quant-group-test ${status || 'unknown'}`;
}

export default function QuantLabPanel({ symbol }: Props) {
  const [data, setData] = useState<QuantStatus | null>(null);
  const [universeData, setUniverseData] = useState<QuantStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState<string | null>(null);
  const [trainingUniverse, setTrainingUniverse] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    Promise.all([fetchQuantStatus(symbol), fetchQuantStatus('UNIFIED')])
      .then(([symbolStatus, universeStatus]) => {
        setData(symbolStatus);
        setUniverseData(universeStatus);
      })
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Failed to load quant status'))
      .finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    load();
  }, [load]);

  const hasActiveJob = useMemo(
    () => !!data?.jobs.some((job) => job.status === 'queued' || job.status === 'running'),
    [data],
  );
  const hasActiveAnalysis = useMemo(
    () => !!data?.analysis_jobs?.some((job) => job.status === 'queued' || job.status === 'running'),
    [data],
  );
  const hasActiveUniverseJob = useMemo(
    () => !!universeData?.jobs.some((job) => job.status === 'queued' || job.status === 'running'),
    [universeData],
  );

  useEffect(() => {
    if (!hasActiveJob && !hasActiveAnalysis && !hasActiveUniverseJob) return;
    const id = window.setInterval(load, 2500);
    return () => window.clearInterval(id);
  }, [hasActiveAnalysis, hasActiveJob, hasActiveUniverseJob, load]);

  const engine = data?.dependencies.model_engine;
  const canTrain = engine?.available ?? false;
  const engineLabel = engine?.name || engine?.package || 'None';
  const latestJob = data?.jobs[0];
  const latestAnalysisJob = data?.analysis_jobs?.[0];
  const latestUniverseJob = universeData?.jobs[0];
  const pendingAnalysis = data?.coverage.pending_analysis
    ?? Math.max((data?.coverage.aligned_news ?? 0) - (data?.coverage.analyzed_news ?? 0), 0);
  const filteredNews = data?.coverage.layer0_filtered ?? 0;
  const sentimentEngine = data?.dependencies.sentiment_engine;
  const sentimentEngineLabel = sentimentEngine?.name || 'SkyEye';
  const universeSymbols = universeData?.coverage.universe_symbols ?? [];
  const activeSymbol = symbol.toUpperCase();

  const train = (horizon: string) => {
    setTraining(horizon);
    setError(null);
    postTrainQuantModel(symbol, horizon, true)
      .then(() => load())
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Training failed'))
      .finally(() => setTraining(null));
  };

  const trainUniverse = (horizon: string) => {
    setTrainingUniverse(horizon);
    setError(null);
    postTrainQuantModel('UNIFIED', horizon, true)
      .then(() => load())
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Universe training failed'))
      .finally(() => setTrainingUniverse(null));
  };

  const analyzeNews = () => {
    setAnalyzing(true);
    setError(null);
    postAnalyzeNews(symbol, 120, 'auto')
      .then(() => load())
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'News analysis failed'))
      .finally(() => setAnalyzing(false));
  };

  return (
    <div className="quant-panel">
      <div className="quant-header">
        <div>
          <span className="quant-title">Quant Lab</span>
          <span className="quant-symbol">{symbol}</span>
        </div>
        <button className="quant-refresh" onClick={load} disabled={loading} title="Refresh">
          {loading ? '...' : '↻'}
        </button>
      </div>

      {error && <div className="quant-alert">{error}</div>}

      {data && (
        <>
          <div className="quant-stat-grid">
            <div className="quant-stat">
              <span className="quant-stat-label">OHLC</span>
              <span className="quant-stat-value">{data.coverage.ohlc_rows}</span>
            </div>
            <div className="quant-stat">
              <span className="quant-stat-label">Aligned News</span>
              <span className="quant-stat-value">{data.coverage.aligned_news}</span>
            </div>
            <div className="quant-stat">
              <span className="quant-stat-label">AI Labels</span>
              <span className="quant-stat-value">{data.coverage.analyzed_news}</span>
            </div>
            <div className="quant-stat">
              <span className="quant-stat-label">Pending</span>
              <span className={`quant-stat-value ${pendingAnalysis > 0 ? 'warn' : 'ready'}`}>
                {pendingAnalysis}
              </span>
            </div>
            <div className="quant-stat">
              <span className="quant-stat-label">Engine</span>
              <span className={`quant-stat-value ${canTrain ? 'ready' : 'blocked'}`}>
                {canTrain ? engineLabel : 'Missing'}
              </span>
            </div>
          </div>

          {data.data_quality && (
            <div className={`quant-health quant-health-${data.data_quality.status}`}>
              <div className="quant-health-main">
                <div>
                  <span className="quant-health-title">Data Health</span>
                  <span className={`quant-health-badge ${data.data_quality.status}`}>
                    {data.data_quality.label}
                  </span>
                </div>
                <span className="quant-health-message">{data.data_quality.message}</span>
              </div>
              <div className="quant-health-metrics">
                <span>OHLC {shortDate(data.data_quality.latest_ohlc_date)} · {ageDays(data.data_quality.ohlc_age_days)}</span>
                <span>News {ageHours(data.data_quality.news_age_hours)}</span>
                <span>Labels {pct(data.data_quality.label_coverage)}</span>
                <span>{data.data_quality.ready_for_modeling ? 'Modeling Ready' : 'Research Only'}</span>
              </div>
              {data.data_quality.issues.length > 0 && (
                <div className="quant-health-issues">
                  {data.data_quality.issues.slice(0, 2).map((issue) => (
                    <span key={issue}>{issue}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {latestJob && (
            <div className={`quant-job quant-job-${latestJob.status}`}>
              <span>{latestJob.horizon.toUpperCase()}</span>
              <span>{statusLabel(latestJob.status)}</span>
              {latestJob.error && <span className="quant-job-error">{latestJob.error}</span>}
            </div>
          )}

          {latestAnalysisJob && (
            <div className={`quant-job quant-job-${latestAnalysisJob.status}`}>
              <span>LAYER 1</span>
              <span>{statusLabel(latestAnalysisJob.status)}</span>
              <span>{latestAnalysisJob.engine}</span>
              {latestAnalysisJob.error && <span className="quant-job-error">{latestAnalysisJob.error}</span>}
            </div>
          )}

          <div className="quant-action-row">
            <div className="quant-action-copy">
              <span>Sentiment: {sentimentEngineLabel}</span>
              <span>
                {pendingAnalysis > 0
                  ? `${pendingAnalysis} articles need labels`
                  : `News labels are current${filteredNews > 0 ? `, ${filteredNews} filtered` : ''}`}
              </span>
            </div>
            <button
              className="quant-analyze-btn"
              disabled={pendingAnalysis <= 0 || analyzing || hasActiveAnalysis}
              onClick={analyzeNews}
            >
              {analyzing || hasActiveAnalysis ? 'Analyzing' : 'Analyze News'}
            </button>
          </div>

          <div className="quant-models">
            {data.models.map((model) => (
              <div className="quant-model-row" key={model.horizon}>
                <div className="quant-model-main">
                  <div className="quant-model-top">
                    <span className="quant-horizon">{model.horizon.toUpperCase()}</span>
                    <span className={`quant-trained ${model.trained ? 'yes' : 'no'}`}>
                      {model.trained ? 'Trained' : 'No Model'}
                    </span>
                    {model.model_type && <span className="quant-engine-badge">{model.model_type}</span>}
                    <span className={`quant-quality-badge ${model.quality.status}`}>
                      {model.quality.label}
                    </span>
                    <span className="quant-lift">{holdoutLift(model)}</span>
                  </div>
                  <div className="quant-metrics">
                    <span>Holdout {pct(model.accuracy)}</span>
                    <span>Base {pct(model.baseline)}</span>
                    <span>F1 {pct(model.f1)}</span>
                    <span>CV {model.backtest.available ? pct(model.backtest.overall_accuracy) : '-'}</span>
                    <span>CV Lift {pp(model.quality.cv_lift)}</span>
                    <span>Strategy {strategyReturn(model)}</span>
                    <span>Excess {strategyExcess(model)}</span>
                    <span>Strict {strictStrategyReturn(model)}</span>
                    <span>StrictEx {strictStrategyExcess(model)}</span>
                    <span>Sharpe {sharpe(model.backtest.long_cash?.sharpe)}</span>
                  </div>
                  <div className="quant-quality-note">{model.quality.message}</div>
                  {model.top_features.length > 0 && (
                    <div className="quant-features">
                      {model.top_features.slice(0, 5).map((feature) => (
                        <span className="quant-feature" key={feature.name}>
                          {feature.name}
                        </span>
                      ))}
                    </div>
                  )}
                  {!!model.feature_groups?.length && (
                    <div className="quant-driver-mix">
                      {model.feature_groups.slice(0, 3).map((group) => (
                        <div className="quant-driver" key={group.key}>
                          <div className="quant-driver-top">
                            <span>{group.label}</span>
                            <span>{pct(group.importance)}</span>
                          </div>
                          <div className="quant-driver-bar">
                            <span style={{ width: driverWidth(group.importance) }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {!!model.backtest.feature_group_tests?.length && (
                    <div className="quant-group-tests">
                      {model.backtest.feature_group_tests.slice(0, 3).map((test) => (
                        <div className={groupTestClass(test.status)} key={test.key}>
                          <span>{test.label}</span>
                          <span>{pp(test.cv_lift)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  className="quant-train-btn"
                  disabled={!canTrain || training === model.horizon || hasActiveJob}
                  onClick={() => train(model.horizon)}
                >
                  {training === model.horizon ? 'Queueing' : 'Train'}
                </button>
              </div>
            ))}
          </div>

          {universeData && (
            <div className="quant-universe">
              <div className="quant-universe-header">
                <div>
                  <span className="quant-universe-title">Universe Model</span>
                  <span className="quant-universe-count">{universeSymbols.length} tickers</span>
                </div>
                <div className="quant-universe-meta">
                  {universeData.data_quality && (
                    <span className={`quant-health-mini ${universeData.data_quality.status}`}>
                      {universeData.data_quality.label}
                    </span>
                  )}
                  <span className="quant-universe-news">{universeData.coverage.analyzed_news} labels</span>
                </div>
              </div>
              {latestUniverseJob && (
                <div className={`quant-job quant-job-${latestUniverseJob.status}`}>
                  <span>{latestUniverseJob.horizon.toUpperCase()}</span>
                  <span>{statusLabel(latestUniverseJob.status)}</span>
                  {latestUniverseJob.error && <span className="quant-job-error">{latestUniverseJob.error}</span>}
                </div>
              )}
              <div className="quant-universe-models">
                {universeData.models.map((model) => {
                  const diagnostics = model.backtest.per_ticker ?? [];
                  const selectedDiagnostic = diagnostics.find((row) => row.symbol === activeSymbol);
                  const strongest = diagnostics.slice(0, 3);
                  const weakest = diagnostics.slice(-3).reverse();

                  return (
                    <div className="quant-universe-model-block" key={model.horizon}>
                      <div className="quant-universe-row">
                        <div className="quant-universe-main">
                          <span className="quant-horizon">{model.horizon.toUpperCase()}</span>
                          {model.model_type && <span className="quant-engine-badge">{model.model_type}</span>}
                          <span className={`quant-quality-badge ${model.quality.status}`}>{model.quality.label}</span>
                          <span className="quant-lift">CV {pp(model.quality.cv_lift)}</span>
                          <span className="quant-lift">Strategy {strategyReturn(model)}</span>
                          <span className="quant-lift">Strict {strictStrategyReturn(model)}</span>
                        </div>
                        <button
                          className="quant-train-btn"
                          disabled={!canTrain || trainingUniverse === model.horizon || hasActiveUniverseJob}
                          onClick={() => trainUniverse(model.horizon)}
                        >
                          {trainingUniverse === model.horizon ? 'Queueing' : 'Train'}
                        </button>
                      </div>

                      {diagnostics.length > 0 && (
                        <div className="quant-diagnostics">
                          <div className="quant-diagnostic-focus">
                            <span className="quant-diagnostic-label">{activeSymbol}</span>
                            {selectedDiagnostic ? (
                              <>
                                <span className={`quant-diagnostic-verdict ${selectedDiagnostic.verdict}`}>
                                  {selectedDiagnostic.verdict}
                                </span>
                                <span>Acc {pct(selectedDiagnostic.accuracy)}</span>
                                <span>Lift {pp(selectedDiagnostic.classification_lift)}</span>
                                <span>Excess {pp(selectedDiagnostic.strategy_excess_return)}</span>
                                <span>StrictEx {pp(selectedDiagnostic.strict_strategy_excess_return)}</span>
                                <span>Sharpe {sharpe(selectedDiagnostic.strategy_sharpe)}</span>
                              </>
                            ) : (
                              <span>No universe backtest row</span>
                            )}
                          </div>

                          <div className="quant-diagnostic-groups">
                            <div className="quant-diagnostic-group">
                              <span className="quant-diagnostic-heading">Best Rank</span>
                              {strongest.map((row) => (
                                <div className={diagnosticRowClass(row)} key={row.symbol}>
                                  <span>{row.symbol}</span>
                                  <span>{diagnosticMetric(row)}</span>
                                </div>
                              ))}
                            </div>
                            <div className="quant-diagnostic-group">
                              <span className="quant-diagnostic-heading">Weakest</span>
                              {weakest.map((row) => (
                                <div className={diagnosticRowClass(row)} key={row.symbol}>
                                  <span>{row.symbol}</span>
                                  <span>{diagnosticMetric(row)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {!!model.feature_groups?.length && (
                        <div className="quant-driver-mix compact">
                          {model.feature_groups.slice(0, 3).map((group) => (
                            <div className="quant-driver" key={group.key}>
                              <div className="quant-driver-top">
                                <span>{group.label}</span>
                                <span>{pct(group.importance)}</span>
                              </div>
                              <div className="quant-driver-bar">
                                <span style={{ width: driverWidth(group.importance) }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {!!model.backtest.feature_group_tests?.length && (
                        <div className="quant-group-tests compact">
                          {model.backtest.feature_group_tests.slice(0, 3).map((test) => (
                            <div className={groupTestClass(test.status)} key={test.key}>
                              <span>{test.label}</span>
                              <span>{pp(test.cv_lift)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!canTrain && (
            <div className="quant-footnote">
              No supported quant training engine is available in the current Python environment.
            </div>
          )}
        </>
      )}
    </div>
  );
}
