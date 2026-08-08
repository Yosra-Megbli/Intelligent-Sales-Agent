#!/usr/bin/env python3
"""
Real-LLM evaluation of the golden message dataset.

This is a standalone script, NEVER collected by pytest and never run in CI
by default - exactly the separation the audit called for: deterministic
regression tests (test_golden_messages.py / test_golden_conversations.py)
stay fast, free, and stable; this is the one place that actually calls the
real model and can tell you whether it understands French customers, at the
cost of being slower, non-free, and non-deterministic run to run.

Usage:
    export GROQ_API_KEY=...
    python golden_tests/run_real_llm_eval.py
    python golden_tests/run_real_llm_eval.py --category price_question_vs_objection
    python golden_tests/run_real_llm_eval.py --save-report golden_tests/reports/latest.json

What it does NOT do: it never asserts/exits non-zero on a per-scenario
mismatch (LLM output isn't stable enough for that to be a useful gate). It
prints a report; a human decides which failures matter, per the audit's
"fix only what a real failure reveals" principle.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.providers.groq import GroqProvider  # noqa: E402

from golden_tests.harness import (  # noqa: E402
    MessageEvalResult,
    evaluate_message_scenarios_with_provider,
    load_message_scenarios,
    summarize,
)


def _print_report(results: list[MessageEvalResult]) -> dict:
    summary = summarize(results)

    print(f"\n{'=' * 70}\nGOLDEN DATASET — REAL LLM EVALUATION\n{'=' * 70}")
    print(f"Total: {summary['total']}  Passed: {summary['passed']}  Accuracy: {summary['accuracy']:.1%}\n")

    print(f"{'Category':<32} {'Passed':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 60)
    for category, stats in sorted(summary["by_category"].items()):
        acc = stats["passed"] / stats["total"] if stats["total"] else 0.0
        flag = "  <-- CHECK" if acc < 1.0 else ""
        print(f"{category:<32} {stats['passed']:>8} {stats['total']:>8} {acc:>9.1%}{flag}")

    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\n{'-' * 70}\nFAILURES ({len(failures)})\n{'-' * 70}")
        for r in failures:
            print(f"\n[{r.scenario.id}] ({r.scenario.category})")
            print(f"  input:    {r.scenario.input!r}")
            if not r.event_type_correct:
                print(f"  event_type  expected={r.scenario.expected_event_type!r}  actual={r.actual_event_type!r}")
            if not r.entities_correct:
                print(f"  entities    expected={r.scenario.expected_entities!r}  actual={r.actual_entities!r}")
            if r.scenario.notes:
                print(f"  notes:    {r.scenario.notes.strip()}")
    else:
        print("\nNo failures. 🎉")

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--category", help="Only run scenarios in this category")
    parser.add_argument("--model", help="Override GROQ_MODEL / provider default")
    parser.add_argument("--save-report", help="Write a JSON report to this path")
    args = parser.parse_args()

    scenarios = load_message_scenarios()
    if args.category:
        scenarios = [s for s in scenarios if s.category == args.category]
        if not scenarios:
            print(f"No scenarios found for category={args.category!r}", file=sys.stderr)
            sys.exit(1)

    try:
        provider = GroqProvider(model=args.model)
    except Exception as exc:  # LLMAuthenticationError / missing `groq` package
        print(f"Could not build a GroqProvider: {exc}", file=sys.stderr)
        print("Set GROQ_API_KEY and `pip install groq` to run the real-LLM eval.", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(scenarios)} scenario(s) against the real LLM ({provider.model})...")
    results = evaluate_message_scenarios_with_provider(scenarios, provider)
    summary = _print_report(results)

    if args.save_report:
        report_path = Path(args.save_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "summary": summary,
                    "results": [
                        {
                            "id": r.scenario.id,
                            "category": r.scenario.category,
                            "input": r.scenario.input,
                            "expected_event_type": r.scenario.expected_event_type,
                            "actual_event_type": r.actual_event_type,
                            "expected_entities": r.scenario.expected_entities,
                            "actual_entities": r.actual_entities,
                            "passed": r.passed,
                        }
                        for r in results
                    ],
                },
                fh,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
