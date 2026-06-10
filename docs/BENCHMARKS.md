# Performance Benchmarks

## Methodology
- Tested on local Docker setup (M3 Mac, 16GB RAM)
- 5 trials with synthetic patient data covering different conditions:
  IVIG/Myasthenia, Humira/RA, ...
- Timer started when user opens form, stopped when result page renders
- LLM: claude-sonnet-4-5

## Results

| Trial | Total Time | Data Entry | LLM Latency |
|-------|------------|------------|-------------|
| 1     | 5m 25s     | 4m 40s     | 45s         |
| 2     | 6m 4s      | 5m 30s     | 34s         |
| 3     | 6m 6s      | 5m 20s     | 46s         |
| 4     | 7m 8s      | 6m 24s     | 44s         |
| 5     | 8m 58s     | 8m 10s     | 48s         |

**Baseline (customer-reported)**: 20-40 min manual

          TotalTime  Data Entry   LLM Latency
Mean      6m44s      6m1s         43s
Median    6m6s       5m30s        45s
Min       5m25s      4m40s        34s
Max       8m58s      8m10s        48s
Percentage100%       ~89%         ~11%