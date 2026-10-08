"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type MoneyPoint = { month: string; revenue: number };
type ForecastPoint = { month: string; forecast_revenue: number };
type DashboardData = {
  kpis: { revenue: number; completed_orders: number; active_customers: number; average_order_value: number };
  monthly_revenue: MoneyPoint[];
  product_performance: { product_id: string; product_name: string; product_category: string; orders: number; units: number; revenue: number; trend_pct: number | null }[];
  analytics: { segments: { segment: string; customers: number }[] };
  ml_status: {
    churn_metrics: { model: string; roc_auc: number; average_precision: number; baseline_average_precision?: number; candidate_results: { family: string; cv_average_precision: number }[] };
    demand_forecast: { forecast: ForecastPoint[]; mape?: number };
    model_monitoring: { status: string; latest_snapshot: string; prediction_summary: { high_risk_rate: number }; checks: { name: string; status: string }[] };
  };
  data_note: string;
};

type ChurnScore = { customer_id: number; churn_probability: number; risk_band: string; model: string; model_run_id: string | null; reasons: string[] };

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

export default function Dashboard({ initialData }: { initialData: DashboardData }) {
  const [data, setData] = useState(initialData);
  const [source, setSource] = useState<"snapshot" | "live">("snapshot");
  const [growth, setGrowth] = useState(0);
  const [customerId, setCustomerId] = useState("1");
  const [score, setScore] = useState<ChurnScore | null>(null);
  const [scoreError, setScoreError] = useState("");

  useEffect(() => {
    if (!["localhost", "127.0.0.1"].includes(window.location.hostname)) return;
    fetch("http://127.0.0.1:8001/api/v1/dashboard")
      .then((response) => { if (!response.ok) throw new Error("API unavailable"); return response.json(); })
      .then((live: DashboardData) => { setData(live); setSource("live"); })
      .catch(() => setSource("snapshot"));
  }, []);

  const forecast = data.ml_status.demand_forecast.forecast.map((point) => ({
    month: point.month.slice(0, 7),
    baseline: point.forecast_revenue,
    scenario: Math.round(point.forecast_revenue * (1 + growth / 100)),
  }));

  async function analyzeCustomer() {
    setScore(null);
    setScoreError("");
    if (source !== "live") { setScoreError("Start the local API and BentoML service to score a customer."); return; }
    try {
      const response = await fetch(`http://127.0.0.1:8001/api/v1/customers/${encodeURIComponent(customerId)}/churn-score`);
      if (!response.ok) throw new Error(response.status === 404 ? "Customer not found." : "The scoring service is unavailable.");
      setScore(await response.json());
    } catch (error) { setScoreError(error instanceof Error ? error.message : "Scoring failed."); }
  }

  return <main className="shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">EI</span><span>E-Commerce Intelligence</span></div><span className="source"><span className={source === "live" ? "dot live" : "dot"} />{source === "live" ? "Local live pipeline" : "Synthetic demo snapshot"}</span></header>

    <section className="hero"><div><p className="eyebrow">COMMERCE ANALYTICS / MODEL OPERATIONS</p><h1>Understand the store.<br /><em>Anticipate what comes next.</em></h1><p className="hero-copy">Explore sales, customer behavior, demand scenarios, and the evidence behind a churn model. All data is synthetic.</p></div><div className="hero-aside"><span>2025 / FULL YEAR</span><strong>{currency.format(data.kpis.revenue)}</strong><small>completed-order revenue</small></div></section>

    <section className="metrics" aria-label="Key performance indicators">
      <Metric label="Revenue" value={currency.format(data.kpis.revenue)} detail="Completed orders only" />
      <Metric label="Orders" value={data.kpis.completed_orders.toLocaleString()} detail="Across the full demo year" />
      <Metric label="Active customers" value={data.kpis.active_customers.toLocaleString()} detail="With a completed purchase" />
      <Metric label="Average order" value={currency.format(data.kpis.average_order_value)} detail="Revenue per completed order" />
    </section>

    <section className="two-column">
      <article className="panel wide"><div className="panel-heading"><div><p className="eyebrow">PERFORMANCE</p><h2>Revenue trend</h2></div><span className="tag">12 months</span></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.monthly_revenue} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}><CartesianGrid stroke="#243849" vertical={false} /><XAxis dataKey="month" tick={{ fill: "#8ea6b5", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tickFormatter={(value: number) => `$${Math.round(value / 1000)}k`} tick={{ fill: "#8ea6b5", fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => currency.format(Number(value))} contentStyle={{ background: "#112633", border: "1px solid #315061", color: "#e7f3f7" }} /><Line type="monotone" dataKey="revenue" stroke="#54d9bb" strokeWidth={3} dot={false} activeDot={{ r: 5 }} /></LineChart></ResponsiveContainer></div></article>
      <article className="panel"><div className="panel-heading"><div><p className="eyebrow">CUSTOMERS</p><h2>Segments</h2></div></div><div className="segment-list">{data.analytics.segments.map((item) => <div className="segment" key={item.segment}><span>{item.segment}</span><strong>{item.customers.toLocaleString()}</strong><div className="track"><div style={{ width: `${(item.customers / 600) * 100}%` }} /></div></div>)}</div></article>
    </section>

    <section className="two-column">
      <article className="panel"><div className="panel-heading"><div><p className="eyebrow">MERCHANDISING</p><h2>Product performance</h2></div><span className="tag">ClickHouse</span></div><div className="table-wrap"><table><thead><tr><th>Product</th><th>Revenue</th><th>Monthly trend</th></tr></thead><tbody>{data.product_performance.map((item) => <tr key={item.product_id}><td>{item.product_name}<small>{item.product_category}</small></td><td>{currency.format(item.revenue)}</td><td>{item.trend_pct === null ? "—" : `${item.trend_pct > 0 ? "+" : ""}${item.trend_pct}%`}</td></tr>)}</tbody></table></div><p className="footnote">Trend compares the latest two months of completed-order revenue.</p></article>
      <article className="panel"><div className="panel-heading"><div><p className="eyebrow">DEMAND PLANNING</p><h2>Forecast scenario</h2></div></div><label className="slider-label" htmlFor="growth">Sales growth assumption <strong>{growth > 0 ? "+" : ""}{growth}%</strong></label><input id="growth" aria-label="Sales growth assumption" type="range" min="-30" max="30" step="5" value={growth} onChange={(event) => setGrowth(Number(event.target.value))} /><div className="chart forecast-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={forecast}><CartesianGrid stroke="#243849" vertical={false} /><XAxis dataKey="month" tick={{ fill: "#8ea6b5", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tickFormatter={(value: number) => `$${Math.round(value / 1000)}k`} tick={{ fill: "#8ea6b5", fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => currency.format(Number(value))} contentStyle={{ background: "#112633", border: "1px solid #315061", color: "#e7f3f7" }} /><Bar dataKey="baseline" fill="#335d6c" name="Baseline" radius={[4, 4, 0, 0]} /><Bar dataKey="scenario" fill="#e7bd7a" name="Scenario" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div><p className="footnote">Scenario applies your assumption to the baseline forecast; it does not retrain the model.</p></article>
    </section>

    <section className="two-column">
      <article className="panel"><div className="panel-heading"><div><p className="eyebrow">PREDICTIVE MODEL</p><h2>Churn comparison</h2></div><span className="tag">{data.ml_status.churn_metrics.model}</span></div><div className="score-strip"><div><strong>{percent(data.ml_status.churn_metrics.average_precision)}</strong><span>Test average precision</span></div><div><strong>{percent(data.ml_status.churn_metrics.roc_auc)}</strong><span>Test ROC AUC</span></div></div><div className="table-wrap"><table><thead><tr><th>Candidate</th><th>CV average precision</th></tr></thead><tbody>{data.ml_status.churn_metrics.candidate_results.map((item) => <tr key={item.family}><td>{item.family.replaceAll("_", " ")}</td><td>{percent(item.cv_average_precision)}</td></tr>)}</tbody></table></div></article>
      <article className="panel"><div className="panel-heading"><div><p className="eyebrow">MODEL OPERATIONS</p><h2>Monitoring</h2></div><span className={`status-pill ${data.ml_status.model_monitoring.status}`}>{data.ml_status.model_monitoring.status}</span></div><p className="monitor-rate">{percent(data.ml_status.model_monitoring.prediction_summary.high_risk_rate)}</p><p className="footnote">High-risk share in latest snapshot · {data.ml_status.model_monitoring.latest_snapshot}</p><div className="checks">{data.ml_status.model_monitoring.checks.map((check) => <div key={check.name}><span>{check.name.replaceAll("_", " ")}</span><strong>{check.status}</strong></div>)}</div></article>
    </section>

    <section className="panel customer-panel"><div><p className="eyebrow">INTERACTIVE ANALYSIS</p><h2>Analyze a customer</h2><p className="footnote">Enter a synthetic customer ID to request a live score from FastAPI and BentoML.</p></div><div className="customer-control"><label htmlFor="customer-id">Customer ID</label><div><input id="customer-id" type="number" min="1" max="600" value={customerId} onChange={(event) => setCustomerId(event.target.value)} /><button type="button" onClick={analyzeCustomer}>Analyze customer <span aria-hidden>↗</span></button></div></div>{score && <div className="score-result"><strong>{percent(score.churn_probability)} churn risk</strong><span>{score.risk_band.toUpperCase()} · {score.model.replaceAll("_", " ")}</span><p>{score.reasons.join(" · ") || "No simple rule-based flags."}</p></div>}{scoreError && <p className="error" role="alert">{scoreError}</p>}</section>

    <footer><span>E-COMMERCE INTELLIGENCE</span><span>Synthetic data · portfolio demonstration · {source === "live" ? "live local services" : "precomputed snapshot"}</span></footer>
  </main>;
}
