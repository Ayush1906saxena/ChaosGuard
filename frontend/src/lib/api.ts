import {
  Scan,
  ScanSummary,
  Severity,
  Finding,
  AttackChain,
  ChaosScenario,
  ChaosExperiment,
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

// ── Summary Normalization ────────────────────────────────────────────────────
// Backend sends snake_case summary (total_findings, by_severity, etc.)
// Frontend expects camelCase (totalFindings, criticalCount, etc.)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeSummary(raw: any): ScanSummary | null {
  if (!raw) return null;
  // Already normalized
  if (raw.totalFindings !== undefined && raw.criticalCount !== undefined) return raw;

  const bySev = raw.by_severity || {};
  return {
    totalFindings: raw.total_findings ?? 0,
    criticalCount: bySev.critical ?? bySev.CRITICAL ?? 0,
    highCount: bySev.high ?? bySev.HIGH ?? 0,
    mediumCount: bySev.medium ?? bySev.MEDIUM ?? 0,
    lowCount: bySev.low ?? bySev.LOW ?? 0,
    infoCount: bySev.info ?? bySev.INFO ?? 0,
    agentsCompleted: raw.agents_completed ?? raw.agentsCompleted ?? 0,
    totalAgents: raw.total_agents ?? raw.totalAgents ?? 0,
    fixesGenerated: raw.fixes_generated ?? raw.fixesGenerated ?? 0,
    attackChainsFound: raw.attack_chains_found ?? raw.attackChainsFound ?? 0,
    chaosScenarios: raw.chaos_scenarios ?? raw.chaosScenarios ?? 0,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeScan(scan: any): Scan {
  return { ...scan, summary: normalizeSummary(scan.summary) };
}

// ── Finding Normalization ────────────────────────────────────────────────────
// Backend returns different field names than what the frontend expects
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeFinding(raw: any): Finding {
  return {
    id: raw.id,
    scanId: raw.scanId,
    agentName: raw.metadata?.agent || raw.agentName || 'unknown',
    tier: raw.metadata?.discovered_tier || raw.tier || 'RECON',
    title: raw.title,
    description: raw.description || '',
    severity: (raw.severity || 'INFO').toUpperCase(),
    category: raw.vulnerabilityType || raw.category || 'other',
    confidence: typeof raw.confidence === 'string' ? parseFloat(raw.confidence) || 0 : (raw.confidence ?? 0),
    filePath: raw.filePath || '',
    startLine: raw.lineStart ?? raw.startLine ?? 0,
    endLine: raw.lineEnd ?? raw.endLine ?? 0,
    codeSnippet: raw.codeSnippet || '',
    recommendation: raw.remediation || raw.recommendation || '',
    references: raw.references || [],
    cweId: raw.cweId || null,
    owaspCategory: raw.owaspCategory || null,
    mitreAttackId: raw.mitreAttackId || null,
    createdAt: raw.createdAt,
  };
}

// ── Fix Normalization ───────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeFix(raw: any): Fix {
  const confidence = raw.confidenceScore ?? raw.confidence ?? 0;
  return {
    id: raw.id,
    findingId: raw.findingId,
    scanId: raw.scanId,
    title: raw.title || `Fix for ${raw.filePath || 'unknown file'}`,
    description: raw.explanation || raw.description || '',
    originalCode: raw.originalCode || '',
    fixedCode: raw.fixedCode || '',
    diffPatch: raw.diffPatch || '',
    filePath: raw.filePath || '',
    startLine: raw.startLine ?? 0,
    endLine: raw.endLine ?? 0,
    confidence: confidence > 1 ? confidence / 100 : confidence,
    breakingChange: raw.breakingChange ?? false,
    testRequired: raw.testRequired ?? (raw.testsPass === false),
    syntaxValid: raw.syntaxValid ?? null,
    compileValid: raw.compileValid ?? null,
    testsPass: raw.testsPass ?? null,
    isApplied: raw.isApplied ?? false,
    pocSteps: raw.pocSteps || [],
    createdAt: raw.createdAt,
  };
}

// ── AttackChain Normalization ────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeAttackChain(raw: any): AttackChain {
  // Map chainSteps to the AttackStep interface
  const steps = (raw.chainSteps || raw.steps || []).map((s: Record<string, unknown>, i: number) => ({
    order: (s.order as number) ?? i + 1,
    title: s.title || s.step || `Step ${i + 1}`,
    description: s.description || '',
    findingId: s.findingId || null,
    technique: s.technique || '',
    severity: ((s.severity as string) || 'MEDIUM').toUpperCase(),
    filePath: s.filePath || s.file_path || null,
    codeSnippet: s.codeSnippet || s.code_snippet || null,
  }));

  return {
    id: raw.id,
    scanId: raw.scanId,
    title: raw.title,
    description: raw.description || '',
    overallSeverity: ((raw.severity || raw.overallSeverity || 'MEDIUM') as string).toUpperCase() as Severity,
    steps,
    mitreAttackTechniques: raw.mitreAttackTechniques || [],
    impactDescription: raw.impact || raw.impactDescription || '',
    likelihood: ((raw.likelihood || 'MEDIUM') as string).toUpperCase() as 'HIGH' | 'MEDIUM' | 'LOW',
    mitigations: raw.mitigations || [],
    exploitComplexity: raw.exploitComplexity || 'UNKNOWN',
    createdAt: raw.createdAt,
  };
}

// ── ChaosScenario Normalization ─────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeChaosScenario(raw: any): ChaosScenario {
  return {
    id: raw.id,
    scanId: raw.scanId,
    title: raw.title,
    description: raw.description || '',
    scenarioType: raw.scenarioType || raw.scenario_type || 'SINGLE_FAILURE',
    targetComponent: raw.targetComponent || raw.target_component || '',
    injectionPoints: raw.injectionPoints || raw.injection_points || [],
    expectedImpact: raw.expectedImpact || raw.expected_impact || {},
    blastRadius: raw.blastRadius || raw.blast_radius || {},
    severity: ((raw.severity || 'MEDIUM') as string).toUpperCase() as Severity,
    prerequisites: raw.prerequisites || [],
    recoverySteps: raw.recoverySteps || raw.recovery_steps || [],
    createdAt: raw.createdAt,
  };
}

// ── Scan Operations ─────────────────────────────────────────────────────────

export async function createScan(data: CreateScanRequest): Promise<Scan> {
  const raw = await request<Scan>('/api/v1/scans', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return normalizeScan(raw);
}

export async function getScan(id: string): Promise<Scan> {
  const raw = await request<Scan>(`/api/v1/scans/${id}`);
  return normalizeScan(raw);
}

export async function listScans(page = 0, size = 20): Promise<PaginatedResponse<Scan>> {
  const raw = await request<PaginatedResponse<Scan>>(`/api/v1/scans?page=${page}&size=${size}`);
  return { ...raw, content: raw.content.map(normalizeScan) };
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
  const raw = await request<PaginatedResponse<Finding>>(`/api/v1/scans/${scanId}/findings${qs}`);
  return { ...raw, content: raw.content.map(normalizeFinding) };
}

export async function getFinding(scanId: string, findingId: string): Promise<Finding> {
  return request<Finding>(`/api/v1/scans/${scanId}/findings/${findingId}`);
}

// ── Attack Chains ───────────────────────────────────────────────────────────

export async function getAttackChains(scanId: string): Promise<AttackChain[]> {
  const raw = await request<AttackChain[]>(`/api/v1/scans/${scanId}/attack-chains`);
  return raw.map(normalizeAttackChain);
}

export async function getAttackChain(scanId: string, chainId: string): Promise<AttackChain> {
  const raw = await request<AttackChain>(`/api/v1/scans/${scanId}/attack-chains/${chainId}`);
  return normalizeAttackChain(raw);
}

// ── Chaos Scenarios ─────────────────────────────────────────────────────────

export async function getChaosScenarios(scanId: string): Promise<ChaosScenario[]> {
  const raw = await request<ChaosScenario[]>(`/api/v1/scans/${scanId}/chaos-scenarios`);
  return raw.map(normalizeChaosScenario);
}

export async function getChaosScenario(
  scanId: string,
  scenarioId: string
): Promise<ChaosScenario> {
  const raw = await request<ChaosScenario>(`/api/v1/scans/${scanId}/chaos-scenarios/${scenarioId}`);
  return normalizeChaosScenario(raw);
}

// ── Fixes ───────────────────────────────────────────────────────────────────

export async function getFixes(scanId: string): Promise<Fix[]> {
  const raw = await request<Fix[]>(`/api/v1/scans/${scanId}/fixes`);
  return raw.map(normalizeFix);
}

export async function getFix(scanId: string, fixId: string): Promise<Fix> {
  const raw = await request<Fix>(`/api/v1/scans/${scanId}/fixes/${fixId}`);
  return normalizeFix(raw);
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

// ── Chaos Experiments (Real Execution) ──────────────────────────────────────

export async function getChaosAvailability(
  scanId: string
): Promise<{ available: boolean; reason: string }> {
  return request<{ available: boolean; reason: string }>(
    `/api/v1/scans/${scanId}/chaos-availability`
  );
}

export async function startChaosExperiment(
  scanId: string,
  scenarioId: string,
  autoApprove: boolean = false
): Promise<{ status: string; scanId: string }> {
  return request<{ status: string; scanId: string }>(
    `/api/v1/scans/${scanId}/chaos-experiments`,
    {
      method: 'POST',
      body: JSON.stringify({ scenarioId, autoApprove }),
    }
  );
}

export async function getChaosExperiments(
  scanId: string
): Promise<ChaosExperiment[]> {
  return request<ChaosExperiment[]>(
    `/api/v1/scans/${scanId}/chaos-experiments`
  );
}

export async function getChaosExperiment(
  experimentId: string
): Promise<ChaosExperiment> {
  return request<ChaosExperiment>(
    `/api/v1/chaos-experiments/${experimentId}`
  );
}

export async function approveChaosExperiment(
  experimentId: string
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/api/v1/chaos-experiments/${experimentId}/approve`,
    { method: 'POST' }
  );
}

export async function rejectChaosExperiment(
  experimentId: string
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/api/v1/chaos-experiments/${experimentId}/reject`,
    { method: 'POST' }
  );
}

export async function abortChaosExperiments(
  scanId: string
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/api/v1/scans/${scanId}/chaos-experiments/abort`,
    { method: 'POST' }
  );
}

// ── Export ───────────────────────────────────────────────────────────────────

export { ApiError };
