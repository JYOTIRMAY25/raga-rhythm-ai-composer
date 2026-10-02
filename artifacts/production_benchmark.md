# Production Performance & Load Benchmark Report

**Generated**: 2026-10-02T05:06:54Z  
**Architecture**: FastAPI / Python 3.11 / Librosa / NumPy / Vite React Frontend  

---

## 1. API Endpoint Latencies

| Endpoint | Samples | Mean (ms) | Median (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health` | 20 | 24.2 | 21.53 | 37.54 | 12.6 | 67.44 |
| `GET /ragas` | 10 | 30.23 | 21.14 | 62.65 | 15.47 | 69.14 |
| `GET /talas` | 10 | 18.67 | 16.95 | 29.68 | 12.15 | 30.81 |

---

## 2. Algorithmic Composition Generation

| Composition Tier | Duration | Uncached (ms) | Cached Mean (ms) | Cached p95 (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Small (20s)** | 20s | 49.15 | 22.51 | 41.66 |
| **Normal (45s)** | 45s | 88.5 | 72.5 | 132.58 |
| **Long (60s)** | 60s | 33.64 | 40.5 | 55.61 |
| **Max Cap (300s)** | 300s | 44.05 | 29.59 | 46.86 |

---

## 3. Audio WAV Synthesis & Rendering

| Tier | Duration | WAV Size | Uncached Render (ms) | Cached Render (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Small (20s)** | 20s | 1,008,170 B | 994.57 | 532.5 |
| **Normal (45s)** | 45s | 2,015,854 B | 1015.15 | 838.45 |
| **Long (60s)** | 60s | 2,519,918 B | 888.18 | 1029.95 |
| **Max Cap (300s)** | 300s | 13,103,918 B | 4905.29 | 5102.73 |

---

## 4. Concurrency & Throughput Scaling

| Concurrency Level | Success Rate | Total Time (ms) | Mean Latency (ms) | p95 Latency (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **2 Simultaneous** | 100.0% | 45.58 | 32.47 | 32.66 |
| **5 Simultaneous** | 100.0% | 66.65 | 32.63 | 43.53 |
| **10 Simultaneous** | 100.0% | 151.05 | 49.13 | 87.15 |

---

## 5. Memory & Asset Sizes

- **Frontend Bundle Size**: 887.34 KB
- **Process Memory Delta**: 0.0 MB
- **Composition Cache Entries**: 11 / 300
- **Audio Cache Entries**: 6 / 100
