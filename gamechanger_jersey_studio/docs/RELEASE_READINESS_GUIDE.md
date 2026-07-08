# Release Readiness Guide

**Version:** 1.0.0-rc.1

## Purpose

The Release Readiness Report aggregates test, performance, accuracy, and stability data into a single RC1 recommendation.

## Generating the Report

**UI:** Validation → Benchmarks → **Release Readiness**

**Programmatic:**

```python
report = production_manager.readiness.generate(
    test_total=203,
    test_passed=203,
    batch_summary=batch_summary,
    stress_report=stress_report,
    kb_report=kb_report,
)
path = production_manager.readiness.save(report)
```

**Production Reports:** Production → Reports → **Release Readiness**

## Report Sections

### Test Summary

- Total / passed / failed tests
- Pass rate percentage

### Performance Summary

- Application version and build
- Mean render time (from batch metrics)
- Estimated batch throughput

### Accuracy Summary

- Mean and median accuracy across benchmarks
- AI acceptance rate
- Most corrected fields

### Stability Summary

- Stress test scenario results
- Memory peak per scenario
- Render consistency flag

### Outstanding Issues

Automatically populated when:

- Tests are failing
- Mean accuracy < 80%
- Stress tests report inconsistency

Manual issues can be added when generating programmatically.

## Recommendations

| Value | Meaning |
|-------|---------|
| **Ready for RC1** | All checks pass, no blocking issues |
| **Conditional** | Minor issues — proceed with documented caveats |
| **Not ready** | Test failures or multiple blocking issues |

## Stress Testing

`StressTestService.run_lightweight_suite()` exercises:

- 100 consecutive render iterations
- Large component library scan
- Multiple template switches
- Large knowledge base load

Full PSD stress tests should be run on production hardware with real assets.

## Example

See `docs/examples/GJS014_RELEASE_READINESS.json`

## Sign-off Checklist

- [ ] 203+ automated tests passing
- [ ] 50–100 real jerseys in benchmark library
- [ ] Mean accuracy ≥ 85%
- [ ] Stress tests consistent
- [ ] Knowledge Base curated from real corrections
- [ ] Outstanding issues reviewed and accepted or resolved
