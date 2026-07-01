# Benchmark Guide

**Version:** 1.0.0-rc.1

## Benchmark Library

Path: `config/benchmarks/rc1_benchmark_library.json`

Each `BenchmarkProject` contains:

```json
{
  "benchmark_id": "BM_A1B2C3D4",
  "project_name": "Coventry Home 2025/26",
  "club": "Coventry City",
  "gjs_project_path": "/path/to/project.gjs",
  "expected_psd_path": "/path/to/expected.psd",
  "generated_psd_path": "/path/to/studio.psd",
  "expected_spec": { },
  "generated_spec": { },
  "operator_notes": "Collar required manual correction",
  "accuracy": { }
}
```

## Workflow

### 1. Build the dataset

For each real Gamechanger jersey:

1. Create and process the jersey in Jersey Studio
2. Save the `.gjs` project
3. Export Studio PSD and PNG
4. Obtain original production PSD and reference images
5. Add to benchmark library via **Add Current Project** or edit JSON directly

### 2. Batch validate

**Batch Validate** scores every benchmark:

- Mean and median accuracy
- AI acceptance rate (from project interpretation feedback)
- Learning rule effectiveness
- Average review and render times
- Most corrected fields
- Missing catalogue components

Reports saved to `reports/validation/batch_validation_summary.json`

### 3. Import / export

```python
production_manager.benchmarks.import_library(Path("shared_benchmarks.json"))
production_manager.benchmarks.export_library(Path("export.json"))
```

## Accuracy Scoring

`AccuracyService` compares `expected_spec` vs `generated_spec` field-by-field.

Category weights are equal; overall score is the mean of category scores.

Confidence per category reflects match ratio × base confidence (default 85%).

## Example Report

See `docs/examples/GJS014_BENCHMARK_REPORT.json`

## Target Metrics for RC1

| Metric | Target |
|--------|--------|
| Mean accuracy | ≥ 85% |
| AI acceptance rate | ≥ 70% |
| Learning rule effectiveness | ≥ 60% |
| Mean render time | < 2s per jersey |
| Missing components | Document and catalogue gaps |
