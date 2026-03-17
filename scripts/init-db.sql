-- scripts/init-db.sql
-- ChaosGuard AI - Database Schema
-- Uses VARCHAR for enum-like fields to match JPA entity mappings.

-- === Tables ===

CREATE TABLE IF NOT EXISTS scans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_url        VARCHAR(500) NOT NULL,
    branch          VARCHAR(100) NOT NULL DEFAULT 'main',
    tier            VARCHAR(20) NOT NULL DEFAULT 'HUNTER',
    status          VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    repo_metadata   JSONB DEFAULT '{}',
    summary         JSONB DEFAULT '{}',
    error_message   TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at    TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);

CREATE TABLE IF NOT EXISTS findings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    file_path           VARCHAR(500) NOT NULL DEFAULT '',
    line_start          INT,
    line_end            INT,
    vulnerability_type  VARCHAR(200) NOT NULL DEFAULT '',
    severity            VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    confidence          VARCHAR(20),
    title               VARCHAR(500) NOT NULL DEFAULT '',
    description         TEXT,
    code_snippet        TEXT,
    remediation         TEXT,
    cwe_id              VARCHAR(50),
    cvss_score          FLOAT,
    owasp_category      VARCHAR(100),
    "references"        JSONB DEFAULT '[]',
    metadata            JSONB DEFAULT '{}',
    is_false_positive   BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);

CREATE TABLE IF NOT EXISTS attack_chains (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    title               VARCHAR(300) NOT NULL,
    description         TEXT,
    severity            VARCHAR(50) NOT NULL,
    entry_point         VARCHAR(500),
    target_asset        VARCHAR(300),
    steps               JSONB NOT NULL DEFAULT '[]',
    chain_steps         JSONB DEFAULT '[]',
    finding_ids         JSONB DEFAULT '[]',
    mitigations         JSONB DEFAULT '[]',
    exploit_complexity  VARCHAR(100),
    impact              TEXT,
    narrative           TEXT,
    likelihood          VARCHAR(50),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attack_chains_scan ON attack_chains(scan_id);

CREATE TABLE IF NOT EXISTS generated_fixes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID,
    finding_id          UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    file_path           VARCHAR(500) NOT NULL,
    original_code       TEXT,
    fixed_code          TEXT,
    diff_patch          TEXT,
    explanation         TEXT,
    confidence_score    FLOAT,
    metadata            JSONB DEFAULT '{}',
    is_applied          BOOLEAN DEFAULT FALSE,
    syntax_valid        BOOLEAN,
    compile_valid       BOOLEAN,
    tests_pass          BOOLEAN,
    sandbox_output      TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fixes_finding ON generated_fixes(finding_id);

CREATE TABLE IF NOT EXISTS chaos_scenarios (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    title               VARCHAR(300) NOT NULL,
    description         TEXT,
    scenario_type       VARCHAR(100) NOT NULL DEFAULT '',
    target_component    VARCHAR(300),
    injection_points    JSONB DEFAULT '[]',
    expected_impact     JSONB DEFAULT '{}',
    blast_radius        JSONB DEFAULT '{}',
    severity            VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    prerequisites       JSONB DEFAULT '[]',
    recovery_steps      JSONB DEFAULT '[]',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chaos_scan ON chaos_scenarios(scan_id);

CREATE TABLE IF NOT EXISTS dependency_graph (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id     UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    source_file VARCHAR(500) NOT NULL,
    source_name VARCHAR(300) NOT NULL,
    target_file VARCHAR(500) NOT NULL,
    target_name VARCHAR(300) NOT NULL,
    edge_type   VARCHAR(50) NOT NULL,
    metadata    JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_depgraph_scan ON dependency_graph(scan_id);
CREATE INDEX IF NOT EXISTS idx_depgraph_source ON dependency_graph(scan_id, source_file);

CREATE TABLE IF NOT EXISTS agent_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id     UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    agent       VARCHAR(50) NOT NULL,
    phase       VARCHAR(50) NOT NULL,
    message     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_scan ON agent_logs(scan_id);

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS scans_updated_at ON scans;
CREATE TRIGGER scans_updated_at
    BEFORE UPDATE ON scans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- === Task 3: Finding feedback table ===
CREATE TABLE IF NOT EXISTS finding_feedback (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id        UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    label             VARCHAR(30) NOT NULL,
    user_comment      TEXT,
    code_fingerprint  VARCHAR(64) NOT NULL,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_finding ON finding_feedback(finding_id);
CREATE INDEX IF NOT EXISTS idx_feedback_fingerprint ON finding_feedback(code_fingerprint);

-- === Task 6: Benchmark runs table ===
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_url            VARCHAR(500) NOT NULL,
    tier                VARCHAR(20) NOT NULL,
    scan_id             UUID REFERENCES scans(id),
    precision_score     FLOAT,
    recall_score        FLOAT,
    f1_score            FLOAT,
    scan_duration_s     FLOAT,
    finding_counts      JSONB DEFAULT '{}',
    chaosguard_version  VARCHAR(50),
    run_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_benchmark_runs_repo ON benchmark_runs(repo_url);
CREATE INDEX IF NOT EXISTS idx_benchmark_runs_date ON benchmark_runs(run_at DESC);

-- === Task 6: Scan metrics table ===
CREATE TABLE IF NOT EXISTS scan_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    tier            VARCHAR(20) NOT NULL,
    total_duration_s FLOAT,
    recon_duration_s FLOAT,
    hunter_duration_s FLOAT,
    siege_duration_s FLOAT,
    finding_counts  JSONB DEFAULT '{}',
    llm_call_count  INT DEFAULT 0,
    llm_total_latency_s FLOAT DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_metrics_scan ON scan_metrics(scan_id);

-- === Task 5: DAST results table ===
CREATE TABLE IF NOT EXISTS dast_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    agent           VARCHAR(50) NOT NULL,
    target_url      VARCHAR(500) NOT NULL,
    route_path      VARCHAR(500),
    http_method     VARCHAR(10),
    probe_type      VARCHAR(50) NOT NULL,
    request_payload TEXT,
    response_status INT,
    response_body   TEXT,
    is_vulnerable   BOOLEAN DEFAULT FALSE,
    evidence        TEXT,
    severity        VARCHAR(20),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dast_results_scan ON dast_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_dast_results_probe ON dast_results(probe_type);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES scans(id),
    report_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- === Chaos Experiments (real execution results) ===
CREATE TABLE IF NOT EXISTS chaos_experiments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id             UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    scenario_id         VARCHAR(200),
    status              VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    experiment_plan     JSONB DEFAULT '{}',
    baseline_metrics    JSONB DEFAULT '{}',
    chaos_metrics       JSONB DEFAULT '{}',
    recovery_metrics    JSONB DEFAULT '{}',
    resilience_score    FLOAT,
    recovery_time_s     FLOAT,
    faults_injected     JSONB DEFAULT '[]',
    health_timeline     JSONB DEFAULT '[]',
    verdict             TEXT,
    recommendations     JSONB DEFAULT '[]',
    started_at          TIMESTAMP WITH TIME ZONE,
    completed_at        TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chaos_experiments_scan ON chaos_experiments(scan_id);
CREATE INDEX IF NOT EXISTS idx_chaos_experiments_status ON chaos_experiments(status);

