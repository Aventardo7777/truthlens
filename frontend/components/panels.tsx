"use client";

import { useMemo, useRef, useState } from "react";
import type { Finding, IntegrityScore, ScanResult } from "@/lib/api";

/* ============================================================ colors */
export function severityColor(s: string) {
  if (s === "high") return "#e5484d";
  if (s === "moderate") return "#f5a524";
  return "#46a758";
}

export function scoreColor(v: number) {
  if (v >= 80) return "#46a758";
  if (v >= 60) return "#f5a524";
  return "#e5484d";
}

export const LAYER_NAMES: Record<string, string> = {
  data_health: "LAYER 1 · DATA HEALTH",
  statistical: "LAYER 2 · STATISTICAL",
  pattern_forensics: "LAYER 3 · PATTERN",
  baseline: "BASELINE · SYNTHETIC",
};

/* ============================================================ score hero */
export function ScoreHero({ integrity }: { integrity: IntegrityScore }) {
  const c = scoreColor(integrity.total);
  return (
    <div className="score-hero">
      <div>
        <div className="score-num" style={{ color: c }}>{integrity.total}</div>
        <div className="mini-label" style={{ marginTop: 2 }}>Integrity Score / 100</div>
      </div>
      <div className="score-side">
        <div className="score-verdict">{integrity.verdict}</div>
        <div className="score-expl">{integrity.explanation}</div>
      </div>
    </div>
  );
}

/* ============================================================ dimension bars */
export function DimensionBars({ dimensions }: { dimensions: Record<string, number> }) {
  const order = ["完整性", "一致性", "分布自然度", "异常程度", "重复风险", "模式异常"];
  return (
    <div>
      {order.map((k) => {
        const v = dimensions[k] ?? 0;
        return (
          <div className="dim-row" key={k}>
            <span className="label">{k}</span>
            <div className="bar">
              <div style={{ width: `${v}%`, background: scoreColor(v) }} />
            </div>
            <span className="val">{v}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ============================================================ histogram sparkline */
export function Histogram({ bins, counts }: { bins: number[]; counts: number[] }) {
  const w = 240;
  const h = 56;
  const max = Math.max(...counts, 1);
  const n = counts.length;
  const bw = w / n;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%" }}>
      {counts.map((c, i) => (
        <rect
          key={i}
          x={i * bw + 0.5}
          y={h - (c / max) * (h - 4)}
          width={Math.max(bw - 1, 1)}
          height={(c / max) * (h - 4)}
          fill="rgba(232,179,57,0.75)"
        />
      ))}
    </svg>
  );
}

/* ============================================================ time series */
export function TimeSeries({ time, values }: { time: (string | null)[]; values: (number | null)[] }) {
  const w = 260;
  const h = 64;
  const pts = values.map((v, i) => ({ x: i, y: v }));
  const ys = pts.filter((p) => p.y != null).map((p) => p.y as number);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const range = yMax - yMin || 1;
  const px = (i: number) => (i / Math.max(pts.length - 1, 1)) * w;
  const py = (v: number) => h - 6 - ((v - yMin) / range) * (h - 12);
  const path = pts
    .map((p, i) => (p.y == null ? "" : `${i === 0 ? "M" : "L"}${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%" }}>
      <path d={path} fill="none" stroke="rgba(76,141,255,0.9)" strokeWidth="1.4" />
    </svg>
  );
}

/* ============================================================ digit bars (Benford) */
export function BenfordBars({
  observed,
  expected,
}: {
  observed: number[];
  expected: number[];
}) {
  const w = 240;
  const h = 90;
  const labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
  const max = Math.max(...observed, ...expected, 1);
  const bw = w / 9;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%" }}>
      {observed.map((o, i) => (
        <g key={i}>
          <rect x={i * bw + 1} y={h - 18 - (o / max) * (h - 24)} width={bw * 0.42} height={(o / max) * (h - 24)} fill="rgba(229,72,77,0.85)" />
          <rect x={i * bw + bw * 0.5} y={h - 18 - (expected[i] / max) * (h - 24)} width={bw * 0.42} height={(expected[i] / max) * (h - 24)} fill="rgba(70,167,88,0.75)" />
          <text x={i * bw + bw / 2} y={h - 4} fontSize="8" fill="#8b94a3" textAnchor="middle">{labels[i]}</text>
        </g>
      ))}
    </svg>
  );
}

/* ============================================================ variable relationship network */
export function NetworkGraph({ result }: { result: ScanResult }) {
  const { nodes, edges } = result.correlation_network;
  const wrapRef = useRef<HTMLDivElement>(null);
  const [dim, setDim] = useState({ w: 560, h: 320 });
  const [hover, setHover] = useState<string | null>(null);

  const layout = useMemo(() => {
    const n = nodes.length;
    const cx = dim.w / 2;
    const cy = dim.h / 2;
    const R = Math.min(cx, cy) - 40;
    const pos = new Map<string, { x: number; y: number }>();
    nodes.forEach((nd, i) => {
      const ang = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
      pos.set(nd.id, { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) });
    });
    // repel nodes with no edges inward
    nodes.forEach((nd) => {
      if (nd.degree === 0) {
        const p = pos.get(nd.id)!;
        p.x = cx + (p.x - cx) * 0.45;
        p.y = cy + (p.y - cy) * 0.45;
      }
    });
    return pos;
  }, [nodes, dim]);

  const strokeFor = (w: number) => Math.max(0.8, Math.min(5, w * 4.5));
  const colorFor = (w: number) => (w > 0.9 ? "rgba(229,72,77,0.85)" : w > 0.7 ? "rgba(245,165,36,0.8)" : "rgba(76,141,255,0.55)");

  return (
    <div className="network-wrap">
      <div
        ref={wrapRef}
        style={{ width: "100%", aspectRatio: "1.75 / 1", position: "relative" }}
      >
        <svg viewBox={`0 0 ${dim.w} ${dim.h}`} preserveAspectRatio="xMidYMid meet" style={{ position: "absolute", inset: 0 }}>
          {edges.map((e, i) => {
            const a = layout.get(e.source);
            const b = layout.get(e.target);
            if (!a || !b) return null;
            const hot = hover === e.source || hover === e.target;
            return (
              <line
                key={i}
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={colorFor(e.weight)}
                strokeOpacity={hot ? 1 : 0.75}
                strokeWidth={strokeFor(e.weight)}
              />
            );
          })}
          {nodes.map((nd) => {
            const p = layout.get(nd.id);
            if (!p) return null;
            const r = nd.degree > 0 ? 7 + Math.min(nd.degree, 6) * 1.6 : 5;
            return (
              <g key={nd.id} onMouseEnter={() => setHover(nd.id)} onMouseLeave={() => setHover(null)}>
                <circle cx={p.x} cy={p.y} r={r} fill={nd.role === "numeric" ? "#1d2534" : "#171c26"}
                  stroke={hover === nd.id ? "#e8b339" : "#4c8dff"} strokeWidth="1.5" />
                <text x={p.x} y={p.y + r + 12} fontSize="10" fill="#8b94a3" textAnchor="middle">{nd.id}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="net-legend">
        <span><span className="sw" style={{ background: "rgba(229,72,77,0.85)" }} /> |r| &gt; 0.9</span>
        <span><span className="sw" style={{ background: "rgba(245,165,36,0.8)" }} /> |r| &gt; 0.7</span>
        <span><span className="sw" style={{ background: "rgba(76,141,255,0.55)" }} /> |r| &gt; 0.3</span>
        <span style={{ marginLeft: "auto" }}>node size ∝ degree</span>
      </div>
    </div>
  );
}

/* ============================================================ findings panel */
export function FindingsPanel({ findings }: { findings: Finding[] }) {
  const [open, setOpen] = useState<string | null>(findings[0]?.id ?? null);
  const high = findings.filter((f) => f.severity === "high").length;
  const mod = findings.filter((f) => f.severity === "moderate").length;
  const low = findings.filter((f) => f.severity === "low").length;
  return (
    <div>
      <div className="score-counts" style={{ marginBottom: 14 }}>
        <b>{findings.length}</b> findings · <b style={{ color: "#e5484d" }}>{high}</b> high ·
        <b style={{ color: "#f5a524" }}> {mod}</b> moderate · <b>{low}</b> low
      </div>
      {findings.map((f) => (
        <div className="finding" key={f.id}>
          <div className="finding-head" onClick={() => setOpen(open === f.id ? null : f.id)}>
            <div>
              <div className="fid">FINDING {f.id}</div>
              <div className="ftitle">{f.title}</div>
            </div>
            <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center" }}>
              <span className="badge layer">{LAYER_NAMES[f.layer] ?? f.layer}</span>
              <span className={`badge ${f.severity}`}>{f.severity}</span>
              <span style={{ color: "var(--dim)", fontSize: 12 }}>{open === f.id ? "−" : "+"}</span>
            </div>
          </div>
          {open === f.id && (
            <div className="finding-body">
              <div className="sec">Statistical Summary</div>
              <p>{f.stat_summary}</p>
              <div className="sec">Why it matters</div>
              <p>{f.why_it_matters}</p>
              <div className="sec">Possible Causes</div>
              <ul>{f.possible_causes.map((c, i) => <li key={i}>{c}</li>)}</ul>
              <div className="sec">What this does not prove</div>
              <p className="note">{f.what_it_does_not_prove}</p>
              <div className="sec">Recommended next steps</div>
              <ul>{f.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
              <div className="sec">Evidence</div>
              <table className="ev-table">
                <tbody>
                  {Object.entries(f.evidence).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td><code>{typeof v === "object" ? JSON.stringify(v) : String(v)}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ============================================================ investigator mode */
export function InvestigatorMode({ result }: { result: ScanResult }) {
  const [selected, setSelected] = useState<string | null>(result.findings[0]?.id ?? null);
  const f = result.findings.find((x) => x.id === selected);
  const evLevel =
    result.findings.some((x) => x.severity === "high")
      ? "high"
      : result.findings.some((x) => x.severity === "moderate")
        ? "moderate"
        : "low";
  return (
    <div className="investigator">
      <div className="inv-head">Digital Forensic Case File</div>
      <div className="inv-case">CASE #{result.case_number}</div>
      <div className="inv-ev">
        <span className="ev-item">
          <span className={`ev-dot ${evLevel}`} />
          EVIDENCE LEVEL: {evLevel.toUpperCase()}
        </span>
        <span className="ev-item">RECORDS: {result.n_rows.toLocaleString()}</span>
        <span className="ev-item">VARIABLES: {result.n_cols}</span>
        <span className="ev-item">SCORE: {result.integrity.total}/100</span>
      </div>
      <div className="inv-list">
        {result.findings.map((x, i) => (
          <div
            key={x.id}
            className="inv-item"
            onClick={() => setSelected(x.id)}
            style={selected === x.id ? { borderColor: "#e8b339" } : undefined}
          >
            <div className="n">FINDING #{String(i + 1).padStart(2, "0")} · {x.severity.toUpperCase()}</div>
            <div className="t">{x.title}</div>
          </div>
        ))}
      </div>
      {f && (
        <div style={{ marginTop: 18, borderTop: "1px solid var(--line-soft)", paddingTop: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{f.title}</div>
          <div className="score-counts" style={{ marginBottom: 8 }}>
            <b>{f.stat_summary}</b>
          </div>
          <div className="finding-body" style={{ border: "1px solid var(--line-soft)", borderRadius: 8 }}>
            <div className="sec">Evidence</div>
            <p>{f.stat_summary}</p>
            <div className="sec">Statistical Method</div>
            <p>{f.why_it_matters}</p>
            <div className="sec">Plausible Explanations</div>
            <ul>{f.possible_causes.map((c, i) => <li key={i}>{c}</li>)}</ul>
            <div className="sec">Counter-Evidence / Limitations</div>
            <p className="note">{f.what_it_does_not_prove}</p>
            <div className="sec">Suggested Investigation</div>
            <ul>{f.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </div>
        </div>
      )}
    </div>
  );
}
