from fastmcp import FastMCP
import httpx
import psycopg2
import json
from config import config

mcp = FastMCP("ChaosGuard AI")

# Gateway base URL for internal communication
GATEWAY_URL = "http://gateway:8080"

@mcp.tool()
async def scan_repository(repo_url: str, tier: str = "hunter", branch: str = "main") -> dict:
    """Trigger a security scan on a GitHub repository.

    Tiers:
    - recon: Fast static analysis (~2 min), no LLM needed
    - hunter: LLM-powered vulnerability reasoning (~10 min)
    - siege: Deep hacker-level analysis with attack chains (~25 min)
    """
    assert tier in ("recon", "hunter", "siege"), "Invalid tier. Use: recon, hunter, siege"
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{GATEWAY_URL}/api/v1/scans", json={
            "repo_url": repo_url, "tier": tier, "branch": branch
        })
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_scan_status(scan_id: str) -> dict:
    """Get the current status of a security scan including progress per agent."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_vulnerabilities(scan_id: str, severity: str = None, category: str = None, tier: str = None) -> list:
    """Get vulnerability findings from a completed scan. Filterable by severity, category, and discovered tier."""
    params = {}
    if severity: params["severity"] = severity
    if category: params["category"] = category
    if tier: params["tier"] = tier
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/findings", params=params)
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_attack_chains(scan_id: str) -> list:
    """Get attack chains (Siege tier only). Shows multi-step exploitation paths linking individual findings."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/attack-chains")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_chaos_scenarios(scan_id: str) -> list:
    """Get chaos engineering scenarios. Hunter: single-failure. Siege: compound cascade scenarios with blast radius."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/chaos-scenarios")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def search_code(scan_id: str, query: str, language: str = None) -> list:
    """RAG search: find relevant code chunks by semantic similarity."""
    async with httpx.AsyncClient() as client:
        body = {"query": query}
        if language: body["language"] = language
        resp = await client.post(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/search", json=body)
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def explain_vulnerability(finding_id: str) -> dict:
    """Get a detailed LLM explanation of a vulnerability including attack scenario and fix approach."""
    conn = psycopg2.connect(config.POSTGRES_DSN)
    cur = conn.cursor()
    cur.execute("SELECT title, description, affected_code, evidence, recommendation, attack_vector FROM findings WHERE id = %s", (finding_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"error": "Finding not found"}
    return {
        "title": row[0], "description": row[1], "affected_code": row[2],
        "evidence": row[3], "recommendation": row[4], "attack_vector": row[5]
    }

@mcp.tool()
async def generate_fix(finding_id: str) -> dict:
    """Generate a code fix for a specific vulnerability finding."""
    conn = psycopg2.connect(config.POSTGRES_DSN)
    cur = conn.cursor()
    cur.execute("""
        SELECT f.fixed_code, f.diff, f.explanation, f.confidence
        FROM generated_fixes f WHERE f.finding_id = %s
    """, (finding_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"error": "No fix generated for this finding"}
    return {"fixed_code": row[0], "diff": row[1], "explanation": row[2], "confidence": row[3]}

@mcp.tool()
async def get_pentest_playbook(scan_id: str) -> dict:
    """Get the penetration test playbook (Siege tier only). Contains ordered test cases with PoC descriptions and cURL commands."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/pentest-playbook")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def create_github_issues(scan_id: str, min_severity: str = "MEDIUM") -> dict:
    """Create GitHub issues for scan findings. Issues are tagged with severity, tier, and category labels."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/github/issues",
                                json={"min_severity": min_severity})
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_security_report(scan_id: str, format: str = "json") -> dict:
    """Get the complete tier-appropriate security report for a scan."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/scans/{scan_id}/report", params={"format": format})
        resp.raise_for_status()
        return resp.json()

# Health endpoint
from fastapi import FastAPI
health_app = FastAPI()

@health_app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-server"}

if __name__ == "__main__":
    import threading
    import uvicorn
    # Run health endpoint on a separate thread
    health_thread = threading.Thread(
        target=lambda: uvicorn.run(health_app, host="0.0.0.0", port=5002),
        daemon=True
    )
    health_thread.start()
    # Run MCP server
    mcp.run(transport="sse", host="0.0.0.0", port=5001)
