"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  API_BASE, fetchAnalysis, reportUrl, runDemo, uploadFile, type ScanResult,
} from "@/lib/api";
import {
  BenfordBars, DimensionBars, FindingsPanel, Histogram, InvestigatorMode,
  NetworkGraph, ScoreHero, TimeSeries, severityColor,
} from "@/components/panels";

const STAGES = [
  "Schema Analysis",
  "Distribution Scan",
  "Outlier Detection",
  "Correlation Mapping",
  "Pattern Forensics",
  "Integrity Assessment",
];

type Phase = "idle" | "scanning" | "done" | "error";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string>("");
  const [stage, setStage] = useState(0);
  const [investigator, setInvestigator] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const fileRef = useRef<HTMLInputElement>(null);
  const dashRef = useRef<HTMLDivElement>(null);

  // backend health check
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((r) => (r.ok ? setApiStatus("ok") : setApiStatus("down")))
      .catch(() => setApiStatus("down"));
  }, []);

  const runScan = useCallback(async (fn: () => Promise<ScanResult>) => {
    setPhase("scanning");
    setError("");
    setInvestigator(false);
    setStage(0);
    const timer = setInterval(() => {
      setStage((s) => Math.min(s + 1, STAGES.length - 1));
    }, 620);
    try {
      const res = await fn();
      clearInterval(timer);
      setStage(STAGES.length);
      await new Promise((r) => setTimeout(r, 450));
      setResult(res);
      setPhase("done");
      setTimeout(() => dashRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      clearInterval(timer);
      setError(e instanceof Error ? e.message : "分析失败");
      setPhase("error");
    }
  }, []);

  // deep-link support: ?demo=1 auto-runs the bundled demo, ?scan=<id> restores
  // a previous analysis (also used for shareable links / headless captures)
  const autoStarted = useRef(false);
  useEffect(() => {
    if (autoStarted.current || phase !== "idle") return;
    const params = new URLSearchParams(window.location.search);
    const scanId = params.get("scan");
    if (scanId) {
      autoStarted.current = true;
      fetchAnalysis(scanId)
        .then((res) => {
          setResult(res);
          setPhase("done");
        })
        .catch(() => setError("分析记录不存在"));
      return;
    }
    if (params.get("demo") === "1") {
      autoStarted.current = true;
      runScan(runDemo);
    }
  }, [phase, runScan]);

  const onFile = useCallback(
    (f: File) => {
      if (!/\.(csv|xlsx|xls)$/i.test(f.name)) {
        setError("仅支持 .csv / .xlsx / .xls 文件");
        setPhase("error");
        return;
      }
      runScan(() => uploadFile(f));
    },
    [runScan]
  );

  const findings = result?.findings ?? [];
  const charts = result?.charts;
  const histEntries = charts ? Object.entries(charts.histograms).slice(0, 4) : [];
  const seriesEntries = charts ? Object.entries(charts.series).slice(0, 2) : [];
  const digitEntries = charts ? Object.entries(charts.digits).filter(([, d]) => d.benford) : [];

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">TRUTHLENS</span>
          <span className="brand-sub">真相镜 · Data Forensics</span>
        </div>
        <div className="topbar-right">
          <span className={`pill ${apiStatus === "ok" ? "ok" : ""}`}>
            {apiStatus === "ok" ? "● ENGINE ONLINE" : apiStatus === "down" ? "● ENGINE OFFLINE" : "··· CONNECTING"}
          </span>
        </div>
      </header>

      <main className="main">
        {phase === "idle" && (
          <>
            <div className="hero">
              <h1>
                Can you trust <span className="q">your data</span>?
              </h1>
              <p>
                TruthLens is a statistical forensics engine. Upload a CSV or Excel file and it
                will audit the dataset for suspicious patterns, anomalies, inconsistencies and
                hidden structures — then explain, in plain language, <em>why</em> it deserves
                investigation. Evidence first. Never cries fraud.
              </p>
            </div>

            <div
              className={`dropzone ${dragging ? "drag" : ""}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const f = e.dataTransfer.files?.[0];
                if (f) onFile(f);
              }}
            >
              <div className="big">Drop your CSV or Excel file here</div>
              <div className="sub">or click to browse · up to 50 MB · processed locally by the forensic engine</div>
              <div>
                <span className="fmt">.CSV</span>
                <span className="fmt">.XLSX</span>
                <span className="fmt">.XLS</span>
              </div>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
                e.target.value = "";
              }}
            />

            <div className="demo-row">
              <button
                className="demo-btn"
                onClick={() => runScan(runDemo)}
              >
                ▶ RUN BUNDLED DEMO · suspicious_sales.xlsx
              </button>
            </div>
            <p style={{ textAlign: "center", color: "var(--dim)", fontSize: 11, marginTop: 10 }}>
              demo dataset contains planted anomalies — duplicate blocks, extreme outliers,
              a mechanical column copy, Benford deviation, and a spliced time series
            </p>
            {apiStatus === "down" && (
              <div className="err-box">
                Backend engine is not reachable at {API_BASE}. Start it with:
                <br />
                <code>cd backend && python -m uvicorn api.main:app --reload --port 8000</code>
              </div>
            )}
          </>
        )}

        {phase === "scanning" && (
          <div className="scan-stage">
            <div className="mini-label" style={{ textAlign: "center", marginBottom: 20 }}>
              Scanning dataset…
            </div>
            {STAGES.map((s, i) => (
              <div
                key={s}
                className={`stage-line ${i < stage ? "done" : i === stage ? "active" : ""}`}
              >
                <span className="idx">{i < stage ? "✓" : String(i + 1).padStart(2, "0")}</span>
                <span>{s}</span>
                <span className="stage-status">
                  {i < stage ? "complete" : i === stage ? <span className="spinner" /> : "queued"}
                </span>
              </div>
            ))}
          </div>
        )}

        {phase === "error" && (
          <>
            <div className="err-box">{error}</div>
            <div style={{ textAlign: "center", marginTop: 20 }}>
              <button className="btn" onClick={() => setPhase("idle")}>← BACK</button>
            </div>
          </>
        )}

        {phase === "done" && result && (
          <div ref={dashRef}>
            {/* ---------- header ---------- */}
            <div className="dash-head">
              <div>
                <div className="case">CASE <b>#{result.case_number}</b></div>
                <div className="file-meta">
                  {result.filename} · {result.n_rows.toLocaleString()} rows × {result.n_cols} columns ·
                  scanned {new Date(result.created_at).toLocaleString()}
                </div>
              </div>
              <div className="actions">
                <button className={`btn ${investigator ? "accent" : ""}`} onClick={() => setInvestigator((v) => !v)}>
                  {investigator ? "◉ INVESTIGATOR MODE ON" : "○ INVESTIGATOR MODE"}
                </button>
                <a className="btn" href={reportUrl(result.scan_id, "html")} target="_blank" rel="noreferrer">HTML</a>
                <a className="btn" href={reportUrl(result.scan_id, "pdf")} target="_blank" rel="noreferrer">PDF</a>
                <a className="btn" href={reportUrl(result.scan_id, "json")} download>JSON</a>
                <button className="btn primary" onClick={() => setPhase("idle")}>NEW SCAN</button>
              </div>
            </div>

            {investigator ? (
              <InvestigatorMode result={result} />
            ) : (
              <>
                {/* ---------- score ---------- */}
                <div className="score-grid">
                  <div className="panel">
                    <h3>Integrity Score</h3>
                    <ScoreHero integrity={result.integrity} />
                    <div className="score-counts">
                      <b>{findings.length}</b> findings ·{" "}
                      <b style={{ color: "#e5484d" }}>{findings.filter((f) => f.severity === "high").length} high</b>
                      {" · "}
                      <b style={{ color: "#f5a524" }}>{findings.filter((f) => f.severity === "moderate").length} moderate</b>
                      {" · "}
                      <b>{findings.filter((f) => f.severity === "low").length} low</b>
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Score Breakdown</h3>
                    <DimensionBars dimensions={result.integrity.dimensions} />
                  </div>
                </div>

                {/* ---------- relationship map ---------- */}
                <div className="section-title">Variable Relationship Map</div>
                <div className="panel">
                  <NetworkGraph result={result} />
                </div>

                {/* ---------- charts row ---------- */}
                <div className="section-title">Distribution · Temporal · Digit</div>
                <div className="grid-3">
                  <div className="panel">
                    <h3>Distributions</h3>
                    {histEntries.length === 0 && <div className="placeholder">no numeric distributions</div>}
                    {histEntries.map(([col, h]) => (
                      <div key={col} style={{ marginBottom: 14 }}>
                        <div className="mini-label">{col}</div>
                        <Histogram bins={h.bins} counts={h.counts} />
                      </div>
                    ))}
                  </div>
                  <div className="panel">
                    <h3>Temporal Series</h3>
                    {seriesEntries.length === 0 && <div className="placeholder">no temporal column detected</div>}
                    {seriesEntries.map(([col, s]) => (
                      <div key={col} style={{ marginBottom: 14 }}>
                        <div className="mini-label">{col}</div>
                        <TimeSeries time={s.time} values={s.values} />
                      </div>
                    ))}
                  </div>
                  <div className="panel">
                    <h3>Benford First-Digit</h3>
                    {digitEntries.length === 0 && <div className="placeholder">no Benford-eligible column</div>}
                    {digitEntries.map(([col, d]) => (
                      <div key={col} style={{ marginBottom: 12 }}>
                        <div className="mini-label">{col} · MAD {d.benford?.mad}</div>
                        <BenfordBars observed={d.benford!.observed_pct} expected={d.benford!.expected_pct} />
                        <div style={{ fontSize: 10, color: "var(--dim)", marginTop: 4 }}>
                          red = observed · green = Benford expectation
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ---------- synthetic baseline ---------- */}
                {(result.synthetic_comparison as { correlation?: { real_max_abs_r?: number; baseline_mean?: number; z_score?: number } })
                  .correlation && (
                  <>
                    <div className="section-title">Synthetic Baseline Test</div>
                    <div className="panel">
                      {(() => {
                        const c = (result.synthetic_comparison as any).correlation;
                        return (
                          <div className="grid-3">
                            <div className="stat-line"><span>Real max |r|</span><span>{c.real_max_abs_r}</span></div>
                            <div className="stat-line"><span>Baseline mean max |r|</span><span>{c.baseline_mean}</span></div>
                            <div className="stat-line"><span>Deviation (z)</span><span style={{ color: severityColor(c.z_score > 2 ? "high" : "low") }}>{c.z_score}σ</span></div>
                          </div>
                        );
                      })()}
                      <p style={{ fontSize: 12, color: "var(--dim)", marginTop: 10, lineHeight: 1.7 }}>
                        Real dependency structure is compared against i.i.d. resampled baselines that
                        preserve each column&apos;s marginal distribution. A large z-score means the
                        observed correlation structure cannot be explained by the column
                        distributions alone.
                      </p>
                    </div>
                  </>
                )}

                {/* ---------- column profiles ---------- */}
                <div className="section-title">Dataset Overview</div>
                <div className="panel">
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 6 }}>
                    {result.columns.map((c) => (
                      <div key={c.name} className="stat-line">
                        <span title={c.dtype}>{c.name} <span style={{ color: "var(--line)", fontSize: 10 }}>[{c.role}]</span></span>
                        <span>{c.missing_pct}% missing</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ---------- findings ---------- */}
                <div className="section-title">Findings ({findings.length})</div>
                <FindingsPanel findings={findings} />
              </>
            )}
          </div>
        )}
      </main>

      <footer className="footer">
        <b>TRUTHLENS</b> · 真相镜 — STATISTICAL DATA FORENSICS ENGINE · evidence-first ·{" "}
        every finding is a hypothesis, never a verdict
      </footer>
    </>
  );
}
