#!/usr/bin/env python3
"""ChaosGuard Benchmark Runner.

Runs scans against known-vulnerable repos and computes precision/recall/F1
against expected findings defined in expected_findings.json.

Usage:
    python run_benchmarks.py [--api-url http://localhost:8080] [--tier HUNTER]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
EXPECTED_FINDINGS_PATH = SCRIPT_DIR / "expected_findings.json"
CHAOSGUARD_VERSION = "1.0.0"


def load_expected_findings() -> dict:
    with open(EXPECTED_FINDINGS_PATH) as f:
        return json.load(f)


def create_scan(api_url: str, repo_url: str, tier: str) -> str:
    """Create a scan and return the scan ID."""
    resp = requests.post(
        f"{api_url}/api/v1/scans",
        json={"repoUrl": repo_url, "tier": tier},
    )
    resp.raise_for_status()
    return resp.json()["scanId"]


def wait_for_scan(api_url: str, scan_id: str, timeout: int = 1800) -> dict:
    """Poll until scan completes or fails."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{api_url}/api/v1/scans/{scan_id}")
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")
        if status in ("COMPLETE", "FAILED"):
            return data
        time.sleep(10)
    raise TimeoutError(f"Scan {scan_id} did not complete within {timeout}s")


def get_findings(api_url: str, scan_id: str) -> list[dict]:
    """Fetch all findings for a scan."""
    resp = requests.get(f"{api_url}/api/v1/scans/{scan_id}/findings?size=1000")
    resp.raise_for_status()
    return resp.json().get("findings", [])


def compute_metrics(actual_findings: list[dict], expected: list[dict]) -> dict:
    """Compute precision, recall, F1 against expected findings."""
    if not expected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    # Build actual category/subcategory counts
    actual_counts: dict[str, int] = {}
    for f in actual_findings:
        cat = f.get("category", "unknown").lower()
        subcat = f.get("subcategory", "unknown").lower()
        key = f"{cat}:{subcat}"
        actual_counts[key] = actual_counts.get(key, 0) + 1

    # Compute recall: how many expected categories were found
    true_positives = 0
    false_negatives = 0
    for exp in expected:
        key = f"{exp['category']}:{exp['subcategory']}"
        min_count = exp.get("min_count", 1)
        actual = actual_counts.get(key, 0)
        if actual >= max(min_count, 1):
            true_positives += 1
        else:
            false_negatives += 1

    # Precision: what fraction of actual findings matched expected categories
    expected_keys = {f"{e['category']}:{e['subcategory']}" for e in expected}
    relevant_actual = sum(1 for f in actual_findings
                         if f"{f.get('category', '').lower()}:{f.get('subcategory', '').lower()}" in expected_keys)
    total_actual = len(actual_findings) if actual_findings else 1

    precision = relevant_actual / total_actual if total_actual > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "total_actual": len(actual_findings),
    }


def save_benchmark_result(api_url: str, result: dict) -> None:
    """Save benchmark result to database via direct PostgreSQL or API."""
    print(f"  Precision: {result['precision']:.2%}")
    print(f"  Recall:    {result['recall']:.2%}")
    print(f"  F1 Score:  {result['f1']:.2%}")
    print(f"  Duration:  {result['duration_s']:.1f}s")
    print(f"  Findings:  {result['total_findings']}")


def main():
    parser = argparse.ArgumentParser(description="ChaosGuard Benchmark Runner")
    parser.add_argument("--api-url", default="http://localhost:8080", help="ChaosGuard API URL")
    parser.add_argument("--tier", default=None, help="Override tier for all repos")
    parser.add_argument("--repo", default=None, help="Run only specific repo by name")
    args = parser.parse_args()

    data = load_expected_findings()
    repos = data["repos"]

    if args.repo:
        repos = [r for r in repos if r["name"].lower() == args.repo.lower()]
        if not repos:
            print(f"No repo found matching: {args.repo}")
            sys.exit(1)

    results = []
    print(f"Running benchmarks against {len(repos)} repositories...")
    print(f"API: {args.api_url}\n")

    for repo in repos:
        repo_url = repo["url"]
        repo_name = repo["name"]
        tier = args.tier or repo["tier"]
        expected = repo["expected_findings"]

        print(f"{'='*60}")
        print(f"Benchmark: {repo_name} (tier={tier})")
        print(f"URL: {repo_url}")
        print(f"Expected finding categories: {len(expected)}")

        try:
            # Create scan
            scan_id = create_scan(args.api_url, repo_url, tier)
            print(f"Scan created: {scan_id}")

            # Wait for completion
            start_time = time.time()
            scan_data = wait_for_scan(args.api_url, scan_id)
            duration = time.time() - start_time
            print(f"Scan completed in {duration:.1f}s (status={scan_data['status']})")

            if scan_data["status"] == "FAILED":
                print(f"  FAILED: {scan_data.get('errorMessage', 'unknown')}")
                continue

            # Get findings
            findings = get_findings(args.api_url, scan_id)
            print(f"Total findings: {len(findings)}")

            # Compute metrics
            metrics = compute_metrics(findings, expected)
            metrics["repo_url"] = repo_url
            metrics["repo_name"] = repo_name
            metrics["tier"] = tier
            metrics["scan_id"] = scan_id
            metrics["duration_s"] = round(duration, 2)
            metrics["total_findings"] = len(findings)

            save_benchmark_result(args.api_url, metrics)
            results.append(metrics)

        except Exception as exc:
            print(f"  ERROR: {exc}")

        print()

    # Summary
    if results:
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_recall = sum(r["recall"] for r in results) / len(results)
        avg_f1 = sum(r["f1"] for r in results) / len(results)
        print(f"Repos tested:     {len(results)}")
        print(f"Avg Precision:    {avg_precision:.2%}")
        print(f"Avg Recall:       {avg_recall:.2%}")
        print(f"Avg F1 Score:     {avg_f1:.2%}")

        # Save to JSON
        output_path = SCRIPT_DIR / "benchmark_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
