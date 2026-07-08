# Performance Guide — Live Renderer

## Target

**Standard quality:** &lt; 150 ms per render (warm cache).

## Tips

1. **Use Draft** while editing colours rapidly; switch to Standard/High for review.
2. **Warm the cache** — first render after quality change is slower (all layers miss).
3. **Partial updates** — changing one colour re-renders one layer; expect sub-50 ms updates.
4. **Inspector** — watch per-layer timings to find expensive catalogue assets.
5. **Layer toggles** — disable shadows/lighting/highlights during rapid editing.

## Benchmarks (reference hardware)

Run:

```bash
cd gamechanger_jersey_studio
.venv/bin/python scripts/benchmark_renderer.py
```

Typical Coventry City Home spec (Standard, warm cache):

| Metric        | Expected   |
|---------------|------------|
| Full render   | 30–80 ms   |
| Collar only   | 5–15 ms    |
| Cache hit rate| &gt; 80% on partial edits |

## Memory

Each cached layer ≈ `width × height × 4` bytes. Standard (400×500) × 10 layers ≈ 8 MB.

Clear cache via application restart or `LiveRendererService.clear_cache()`.
