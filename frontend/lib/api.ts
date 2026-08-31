// TruthLens API client
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Finding {
  id: string;
  layer: string;
  category: string;
  title: string;
  severity: "low" | "moderate" | "high";
  evidence_level: "low" | "moderate" | "high";
  stat_summary: string;
  evidence: Record<string, unknown>;
  why_it_matters: string;
  possible_causes: string[];
  what_it_does_not_prove: string;
  next_steps: string[];
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  role: string;
  count: number;
  missing: number;
  missing_pct: number;
  unique: number;
  stats: Record<string, unknown>;
}

export interface IntegrityScore {
  total: number;
  verdict: string;
  dimensions: Record<string, number>;
  explanation: string;
}

export interface ScanResult {
  scan_id: string;
  case_number: string;
  filename: string;
  created_at: string;
  n_rows: number;
  n_cols: number;
  columns: ColumnProfile[];
  findings: Finding[];
  integrity: IntegrityScore;
  correlation_network: { nodes: { id: string; role: string; degree: number }[]; edges: { source: string; target: string; weight: number; sign: string }[] };
  charts: {
    histograms: Record<string, { bins: number[]; counts: number[] }>;
    series: Record<string, { time: (string | null)[]; values: (number | null)[] }>;
    digits: Record<string, { benford?: { observed_pct: number[]; expected_pct: number[]; chi2: number; p_value: number; mad: number }; last_digit?: { observed_pct: number[]; chi2: number; p_value: number } }>;
    shapes: Record<string, { skew: number; kurtosis: number; mean: number; std: number }>;
    outliers: Record<string, { iqr_outliers: number; iqr_pct: number; max_robust_z: number; fences: number[] }>;
  };
  synthetic_comparison: Record<string, unknown>;
  fingerprint: Record<string, unknown>;
  pipeline_steps: string[];
}

export async function uploadFile(file: File): Promise<ScanResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function runDemo(): Promise<ScanResult> {
  const res = await fetch(`${API_BASE}/api/demo`);
  if (!res.ok) throw new Error(`Demo failed (${res.status})`);
  return res.json();
}

export async function fetchAnalysis(id: string): Promise<ScanResult> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}`);
  if (!res.ok) throw new Error(`Analysis ${id} not found`);
  return res.json();
}

export function reportUrl(id: string, format: "html" | "json" | "pdf"): string {
  return `${API_BASE}/api/analyses/${id}/report?format=${format}`;
}
