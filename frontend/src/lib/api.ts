import {
  Scan,
  Finding,
  AttackChain,
  ChaosScenario,
  Fix,
  PentestPlaybook,
  FileTreeNode,
  FileContent,
  DependencyGraph,
  CreateScanRequest,
  PaginatedResponse,
  FindingsFilter,
  FeedbackLabel,
  FindingFeedback,
  ScanMetrics,
  BenchmarkRun,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => 'Unknown error');
    throw new ApiError(res.status, `API error ${res.status}: ${body}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

function buildQueryString(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => parts.push(`${key}=${encodeURIComponent(String(v))}`));
    } else {
      parts.push(`${key}=${encodeURIComponent(String(value))}`);
    }
  }
  return parts.length > 0 ? `?${parts.join('&')}` : '';
}

// ── Scan Operations ─────────────────────────────────────────────────────────

export async function createScan(data: CreateScanRequest): Promise<Scan> {
  return request<Scan>('/api/v1/scans', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getScan(id: string): Promise<Scan> {
  return request<Scan>(`/api/v1/scans/${id}`);
}

export async function listScans(page = 0, size = 20): Promise<PaginatedResponse<Scan>> {
  return request<PaginatedResponse<Scan>>(`/api/v1/scans?page=${page}&size=${size}`);
}

export async function cancelScan(id: string): Promise<void> {
  return request<void>(`/api/v1/scans/${id}/cancel`, { method: 'POST' });
}

// ── Findings ────────────────────────────────────────────────────────────────

export async function getFindings(
  scanId: string,
  filter?: FindingsFilter
): Promise<PaginatedResponse<Finding>> {
  const qs = filter ? buildQueryString(filter as Record<string, unknown>) : '';
  return request<PaginatedResponse<Finding>>(`/api/v1/scans/${scanId}/findings${qs}`);
}

export async function getFinding(scanId: string, findingId: string): Promise<Finding> {
  return request<Finding>(`/api/v1/scans/${scanId}/findings/${findingId}`);
}

// ── Attack Chains ───────────────────────────────────────────────────────────

export async function getAttackChains(scanId: string): Promise<AttackChain[]> {
  return request<AttackChain[]>(`/api/v1/scans/${scanId}/attack-chains`);
}

export async function getAttackChain(scanId: string, chainId: string): Promise<AttackChain> {
  return request<AttackChain>(`/api/v1/scans/${scanId}/attack-chains/${chainId}`);
}

// ── Chaos Scenarios ─────────────────────────────────────────────────────────

export async function getChaosScenarios(scanId: string): Promise<ChaosScenario[]> {
  return request<ChaosScenario[]>(`/api/v1/scans/${scanId}/chaos-scenarios`);
}

export async function getChaosScenario(
  scanId: string,
  scenarioId: string
): Promise<ChaosScenario> {
  return request<ChaosScenario>(`/api/v1/scans/${scanId}/chaos-scenarios/${scenarioId}`);
}

// ── Fixes ───────────────────────────────────────────────────────────────────

export async function getFixes(scanId: string): Promise<Fix[]> {
  return request<Fix[]>(`/api/v1/scans/${scanId}/fixes`);
}

export async function getFix(scanId: string, fixId: string): Promise<Fix> {
  return request<Fix>(`/api/v1/scans/${scanId}/fixes/${fixId}`);
}

export async function createIssue(scanId: string, fixId: string): Promise<{ issueUrl: string }> {
  return request<{ issueUrl: string }>(`/api/v1/scans/${scanId}/fixes/${fixId}/create-issue`, {
    method: 'POST',
  });
}

export async function createPullRequest(
  scanId: string,
  fixIds: string[]
): Promise<{ prUrl: string }> {
  return request<{ prUrl: string }>(`/api/v1/scans/${scanId}/fixes/create-pr`, {
    method: 'POST',
    body: JSON.stringify({ fixIds }),
  });
}

// ── Playbooks ───────────────────────────────────────────────────────────────

export async function getPlaybooks(scanId: string): Promise<PentestPlaybook[]> {
  return request<PentestPlaybook[]>(`/api/v1/scans/${scanId}/playbooks`);
}

export async function getPlaybook(scanId: string, playbookId: string): Promise<PentestPlaybook> {
  return request<PentestPlaybook>(`/api/v1/scans/${scanId}/playbooks/${playbookId}`);
}

// ── Code Explorer ───────────────────────────────────────────────────────────

export async function getFileTree(scanId: string): Promise<FileTreeNode[]> {
  return request<FileTreeNode[]>(`/api/v1/scans/${scanId}/files`);
}

export async function getFileContent(scanId: string, filePath: string): Promise<FileContent> {
  return request<FileContent>(
    `/api/v1/scans/${scanId}/files/content?path=${encodeURIComponent(filePath)}`
  );
}

// ── Dependency Graph ────────────────────────────────────────────────────────

export async function getDependencyGraph(scanId: string): Promise<DependencyGraph> {
  return request<DependencyGraph>(`/api/v1/scans/${scanId}/dependency-graph`);
}

// ── Feedback (Task 3) ────────────────────────────────────────────────────────

export async function submitFeedback(
  findingId: string,
  label: FeedbackLabel,
  comment?: string
): Promise<FindingFeedback> {
  return request<FindingFeedback>(`/api/v1/findings/${findingId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ label, comment }),
  });
}

export async function getFeedback(findingId: string): Promise<{ feedback: FindingFeedback[] }> {
  return request<{ feedback: FindingFeedback[] }>(`/api/v1/findings/${findingId}/feedback`);
}

// ── Metrics (Task 6) ────────────────────────────────────────────────────────

export async function getScanMetrics(scanId: string): Promise<ScanMetrics> {
  return request<ScanMetrics>(`/api/v1/scans/${scanId}/metrics`);
}

// ── Queue Status (Task 7) ───────────────────────────────────────────────────

export async function getQueueStatus(): Promise<Record<string, { queued: number; processing: number }>> {
  return request<Record<string, { queued: number; processing: number }>>('/api/v1/scans/queue-status');
}

// ── Export ───────────────────────────────────────────────────────────────────

export { ApiError };
