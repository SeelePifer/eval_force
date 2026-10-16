export interface TargetPoint {
  name: string;
  model: string;
  quality: number;
  cost_usd: number;
  latency_p95_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface RunSummary {
  id: string;
  dataset_sha256: string;
  passed: boolean;
  created_at: string;
  targets: TargetPoint[];
}

export interface CaseResult {
  case_id: string;
  output: string;
  expected: string;
  cost_usd: number;
  scores: { quality: number };
}

export interface RunDetail {
  id: string;
  passed: boolean;
  created_at: string;
  results: {
    passed: boolean;
    targets: Array<{
      name: string;
      model: string;
      summary: TargetPoint;
      cases: CaseResult[];
    }>;
  };
}

export interface CompareResult {
  quality_delta: number;
  cost_delta: number;
  latency_p95_delta_ms: number;
  cases: Array<{
    case_id: string;
    quality_a: number;
    quality_b: number;
    quality_delta: number;
    output_a: string;
    output_b: string;
  }>;
}

const apiUrl = () => (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function listRuns(apiKey: string): Promise<RunSummary[]> {
  return request("/v1/runs", apiKey);
}

export function getRun(apiKey: string, id: string): Promise<RunDetail> {
  return request(`/v1/runs/${id}`, apiKey);
}

export function compareRun(
  apiKey: string,
  runId: string,
  targetA: string,
  targetB: string,
): Promise<CompareResult> {
  return request("/v1/compare", apiKey, {
    method: "POST",
    body: JSON.stringify({ run_id: runId, target_a: targetA, target_b: targetB }),
  });
}
