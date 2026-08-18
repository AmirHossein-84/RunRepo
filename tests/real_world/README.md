# RunRepo Real-World 50-Repository Benchmark

This directory contains the automated benchmark harness, corpus specifications, and raw execution logs for the RunRepo 50-repository real-world validation suite.

## Benchmark Execution Methodology

The benchmark validates RunRepo's deterministic reproducibility capabilities against a curated corpus of 50 open-source repositories across 5 distinct batches:
- **Batch 1 (1–10)**: Core Node.js & Fullstack Web
- **Batch 2 (11–20)**: Modern Frontend & Core Python
- **Batch 3 (21–30)**: Python Ecosystem, Templates & Workflows
- **Batch 4 (31–40)**: Complex Multi-Service, CMS & Apps
- **Batch 5 (41–50)**: Build Systems, ML & Complex Frameworks

## Classification Schema
Every repository is categorized into one of:
- `FULL_SUCCESS`
- `SUCCESS_WITH_USER_INPUT`
- `PARTIAL_SUCCESS`
- `CORRECTLY_UNSUPPORTED`
- `INCORRECT_FAILURE`
- `FALSE_SUCCESS`

## Running the Benchmark
```bash
# Run a specific batch (e.g. Batch 1)
uv run python tests/real_world/runner.py --batch 1

# Run an individual repository by ID or name
uv run python tests/real_world/runner.py --id 1
```
