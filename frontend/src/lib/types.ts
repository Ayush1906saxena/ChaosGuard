// ── Scan Types ──────────────────────────────────────────────────────────────

export type ScanTier = 'RECON' | 'HUNTER' | 'SIEGE' | 'LIVE';

export type ScanStatus =
  | 'QUEUED'
  | 'CLONING'
  | 'CLONING_COMPLETE'
  | 'INDEXING'
  | 'INDEXING_COMPLETE'
  | 'ANALYZING'
  | 'GENERATING_FIXES'
  | 'COMPLETE'
  | 'FAILED';

export interface Scan {
  id: string;
  repoUrl: string;
  branch: string;
  tier: ScanTier;
  status: ScanStatus;
  repoMetadata: RepoMetadata | null;
  summary: ScanSummary | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

export interface RepoMetadata {
  name: string;
  language: string;
  languages: Record<string, number>;
  fileCount: number;
  totalLines: number;
  frameworks: string[];
}

export interface ScanSummary {
  totalFindings: number;
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  infoCount: number;
  agentsCompleted: number;
  totalAgents: number;
  fixesGenerated: number;
  attackChainsFound: number;
  chaosScenarios: number;
}

// ── Finding Types ───────────────────────────────────────────────────────────

export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingCategory =
  | 'SQL_INJECTION'
  | 'XSS'
  | 'AUTHENTICATION'
  | 'AUTHORIZATION'
  | 'CRYPTOGRAPHY'
  | 'CONFIGURATION'
  | 'DEPENDENCY'
  | 'INFORMATION_DISCLOSURE'
  | 'INJECTION'
  | 'SSRF'
  | 'PATH_TRAVERSAL'
  | 'DESERIALIZATION'
  | 'RACE_CONDITION'
  | 'BUSINESS_LOGIC'
  | 'OTHER';

export interface Finding {
  id: string;
  scanId: string;
  agentName: string;
  tier: ScanTier;
  title: string;
  description: string;
  severity: Severity;
  category: FindingCategory;
  confidence: number;
  filePath: string;
  startLine: number;
  endLine: number;
  codeSnippet: string;
  recommendation: string;
  references: string[];
  cweId: string | null;
  owaspCategory: string | null;
  mitreAttackId: string | null;
  createdAt: string;
}

// ── Attack Chain Types ──────────────────────────────────────────────────────

export interface AttackChain {
  id: string;
  scanId: string;
  title: string;
  description: string;
  overallSeverity: Severity;
  steps: AttackStep[];
  mitreAttackTechniques: MitreReference[];
  impactDescription: string;
  likelihood: 'HIGH' | 'MEDIUM' | 'LOW';
  createdAt: string;
}

export interface AttackStep {
  order: number;
  title: string;
  description: string;
  findingId: string | null;
  technique: string;
  severity: Severity;
  filePath: string | null;
  codeSnippet: string | null;
}

export interface MitreReference {
  techniqueId: string;
  name: string;
  tacticName: string;
  url: string;
}

// ── Chaos Scenario Types ────────────────────────────────────────────────────

export interface ChaosScenario {
  id: string;
  scanId: string;
  title: string;
  description: string;
  tier: ScanTier;
  scenarioType: 'SINGLE_FAILURE' | 'CASCADE' | 'BLAST_RADIUS';
  trigger: string;
  affectedComponents: string[];
  blastRadius: BlastRadiusNode[];
  missingSafeguards: string[];
  estimatedRecoveryTime: string;
  severity: Severity;
  timeline: ChaosTimelineEvent[];
  createdAt: string;
}

export interface BlastRadiusNode {
  component: string;
  impact: Severity;
  failureMode: string;
  dependents: string[];
}

export interface ChaosTimelineEvent {
  timestamp: string;
  event: string;
  component: string;
  impact: Severity;
}

// ── Fix Types ───────────────────────────────────────────────────────────────

export interface Fix {
  id: string;
  findingId: string;
  scanId: string;
  title: string;
  description: string;
  originalCode: string;
  fixedCode: string;
  filePath: string;
  startLine: number;
  endLine: number;
  confidence: number;
  breakingChange: boolean;
  testRequired: boolean;
  pocSteps: string[];
  createdAt: string;
}

// ── Playbook Types ──────────────────────────────────────────────────────────

export interface PentestPlaybook {
  id: string;
  scanId: string;
  title: string;
  description: string;
  testCases: PentestTestCase[];
  owaspReferences: string[];
  mitreReferences: MitreReference[];
  createdAt: string;
}

export interface PentestTestCase {
  order: number;
  title: string;
  description: string;
  curlCommand: string;
  expectedBehavior: string;
  actualBehavior: string;
  findingId: string | null;
  severity: Severity;
  passed: boolean;
}

// ── Code Explorer Types ─────────────────────────────────────────────────────

export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileTreeNode[];
  findingCount?: number;
  maxSeverity?: Severity;
}

export interface FileContent {
  path: string;
  content: string;
  language: string;
  findings: Finding[];
}

// ── Dependency Graph Types ──────────────────────────────────────────────────

export interface DependencyNode {
  id: string;
  name: string;
  type: 'file' | 'package' | 'service' | 'database' | 'external';
  riskLevel: Severity | 'NONE';
  findingCount: number;
  metadata: Record<string, string>;
}

export interface DependencyEdge {
  source: string;
  target: string;
  type: 'import' | 'api_call' | 'data_flow' | 'dependency';
  label?: string;
  isDataFlow?: boolean;
}

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
}

// ── Agent Progress Types ────────────────────────────────────────────────────

export interface AgentProgress {
  agentName: string;
  tier: ScanTier;
  status: 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED';
  progress: number;
  currentTask: string;
  findingsCount: number;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ScanProgressUpdate {
  scanId: string;
  status: ScanStatus;
  agents: AgentProgress[];
  latestFinding: Finding | null;
  logMessage: string | null;
  timestamp: string;
}

// ── API Request/Response Types ──────────────────────────────────────────────

export interface CreateScanRequest {
  repoUrl: string;
  branch?: string;
  tier: ScanTier;
}

export interface PaginatedResponse<T> {
  content: T[];
  totalElements: number;
  totalPages: number;
  page: number;
  size: number;
}

export interface FindingsFilter {
  severity?: Severity[];
  category?: FindingCategory[];
  agentName?: string[];
  tier?: ScanTier[];
  page?: number;
  size?: number;
  sortBy?: string;
  sortDir?: 'asc' | 'desc';
}

// ── Feedback Types (Task 3) ─────────────────────────────────────────────────

export type FeedbackLabel = 'TRUE_POSITIVE' | 'FALSE_POSITIVE' | 'WONT_FIX';

export interface FindingFeedback {
  id: string;
  findingId: string;
  label: FeedbackLabel;
  userComment: string | null;
  codeFingerprint: string;
  createdAt: string;
}

// ── Chaos Experiment Types (Real Execution) ─────────────────────────────────

export type ExperimentStatus =
  | 'PENDING'
  | 'PLANNING'
  | 'PROVISIONING'
  | 'BASELINE'
  | 'PENDING_APPROVAL'
  | 'STEADY_STATE'
  | 'INJECTING'
  | 'OBSERVING'
  | 'ROLLING_BACK'
  | 'RECOVERING'
  | 'COMPLETED'
  | 'FAILED'
  | 'ABORTED'
  | 'REJECTED'
  | 'ERROR';

export interface ChaosExperiment {
  id: string;
  scanId: string;
  scenarioId: string;
  status: ExperimentStatus;
  experimentPlan: Record<string, unknown>;
  baselineMetrics: ExperimentMetrics;
  chaosMetrics: ExperimentMetrics;
  recoveryMetrics: ExperimentMetrics;
  resilienceScore: number | null;
  recoveryTimeS: number | null;
  faultsInjected: FaultInjection[];
  healthTimeline: HealthTimelineEntry[];
  verdict: string | null;
  recommendations: string[];
  startedAt: string | null;
  completedAt: string | null;
}

export interface ExperimentMetrics {
  total: number;
  success_rate: number;
  avg_response_ms: number;
  p99_response_ms: number;
  error_count: number;
}

export interface FaultInjection {
  injection_id: string;
  fault_type: string;
  target_service: string;
  target_container: string;
  params: Record<string, unknown>;
  success: boolean;
  started_at: string;
  error: string;
}

export interface HealthTimelineEntry {
  timestamp: string;
  service: string;
  url: string;
  status_code: number;
  response_time_ms: number;
  success: boolean;
  error: string;
}

// ── Benchmark/Metrics Types (Task 6) ────────────────────────────────────────

export interface ScanMetrics {
  scanId: string;
  tier: ScanTier;
  status: ScanStatus;
  createdAt: string;
  completedAt: string | null;
  durationSeconds: number | null;
  summary: ScanSummary | null;
}

export interface BenchmarkRun {
  id: string;
  repoUrl: string;
  tier: ScanTier;
  scanId: string | null;
  precisionScore: number;
  recallScore: number;
  f1Score: number;
  scanDurationS: number;
  findingCounts: Record<string, number>;
  chaosguardVersion: string;
  runAt: string;
}
