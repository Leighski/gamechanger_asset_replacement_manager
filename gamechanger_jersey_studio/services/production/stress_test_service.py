"""Stability stress testing for RC1 readiness."""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field

from models.validation import StressTestReport, StressTestResult, StressTestScenario
from services.logging_manager import get_logger

logger = get_logger()


@dataclass
class _StressRun:
    durations_ms: list[float] = field(default_factory=list)
    successes: int = 0
    failures: int = 0
    peak_memory_mb: float = 0.0


class StressTestService:
    """Run stability stress scenarios and record memory/render consistency."""

    def run_consecutive_renders(
        self,
        render_fn,
        *,
        count: int = 100,
    ) -> StressTestResult:
        run = _StressRun()
        tracemalloc.start()
        for _ in range(count):
            start = time.perf_counter()
            try:
                render_fn()
                run.successes += 1
            except Exception:
                run.failures += 1
            run.durations_ms.append((time.perf_counter() - start) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        run.peak_memory_mb = round(peak / 1024 / 1024, 2)
        return self._build_result(StressTestScenario.CONSECUTIVE_RENDERS, count, run)

    def run_iterations(
        self,
        scenario: StressTestScenario,
        fn,
        *,
        count: int = 10,
    ) -> StressTestResult:
        run = _StressRun()
        tracemalloc.start()
        for _ in range(count):
            start = time.perf_counter()
            try:
                fn()
                run.successes += 1
            except Exception:
                run.failures += 1
            run.durations_ms.append((time.perf_counter() - start) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        run.peak_memory_mb = round(peak / 1024 / 1024, 2)
        return self._build_result(scenario, count, run)

    def run_lightweight_suite(self) -> StressTestReport:
        """Run simulated stress scenarios without heavy PSD I/O."""
        scenarios: list[StressTestResult] = []

        def noop_render() -> None:
            _ = sum(range(1000))

        scenarios.append(self.run_consecutive_renders(noop_render, count=100))

        def catalogue_scan() -> None:
            items = [f"component_{i}" for i in range(500)]
            _ = sorted(items)

        scenarios.append(
            self.run_iterations(StressTestScenario.LARGE_CATALOGUE, catalogue_scan, count=20)
        )

        def template_switch() -> None:
            templates = ["T1", "T2", "T3", "T4", "T5"]
            _ = templates[len(scenarios) % len(templates)]

        scenarios.append(
            self.run_iterations(StressTestScenario.TEMPLATE_SWITCHES, template_switch, count=50)
        )

        def kb_load() -> None:
            rules = [{"id": f"R{i}", "title": f"Rule {i}"} for i in range(200)]
            _ = len(rules)

        scenarios.append(
            self.run_iterations(StressTestScenario.LARGE_KNOWLEDGE_BASE, kb_load, count=30)
        )

        all_consistent = all(s.consistent for s in scenarios)
        return StressTestReport(scenarios=scenarios, all_consistent=all_consistent)

    def _build_result(
        self,
        scenario: StressTestScenario,
        count: int,
        run: _StressRun,
    ) -> StressTestResult:
        avg = round(sum(run.durations_ms) / len(run.durations_ms), 2) if run.durations_ms else 0.0
        consistent = run.failures == 0
        if run.durations_ms:
            spread = max(run.durations_ms) - min(run.durations_ms)
            if spread > avg * 5 and avg > 0:
                consistent = False
        return StressTestResult(
            scenario=scenario,
            iterations=count,
            success_count=run.successes,
            failure_count=run.failures,
            peak_memory_mb=run.peak_memory_mb,
            average_duration_ms=avg,
            consistent=consistent,
        )
