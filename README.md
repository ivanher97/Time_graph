# MoTeC Telemetry Dashboard — by Hammerman
- https://timegraph-hammerman.streamlit.app/

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat-square&logo=streamlit)
![Plotly](https://img.shields.io/badge/Charts-Plotly-3F4F75?style=flat-square&logo=plotly)
![Groq](https://img.shields.io/badge/Inference-Groq_LPU-orange?style=flat-square&logo=groq)
![Llama](https://img.shields.io/badge/LLM-Llama_3.3_70B-0668E1?style=flat-square&logo=meta)

## Project Overview

This project implements a **High-Performance Sim Racing Telemetry Dashboard** built on top of raw **MoTeC CSV exports**. Designed for endurance sim racing drivers, it transforms thousands of rows of raw telemetry log data into actionable performance metrics and a fully interactive scatter-plot analysis of every lap in a session.

Beyond the pure data visualization layer, the dashboard integrates an **AI-powered Pit Wall Engineer** that leverages **Groq's ultra-low latency LPU inference** and **Llama 3.3 70B** to deliver a professional, Spanish-language radio debrief — analyzing stint pacing, traffic incidents in multiclass races, tire degradation patterns, and driver consistency — exactly as a real race engineer would.

---

## Architecture & Workflow

### Phase 1: Telemetry Ingestion & Parsing
* **Format Support:** Natively handles the proprietary **MoTeC CSV export format**, skipping the 14-line manufacturer header and dynamically locating the `Time`, `Lap Number`, and `In Pits` column indexes.
* **In-Memory Processing:** The uploaded file is parsed entirely in-memory using `io.TextIOWrapper` and Python's `csv.Reader` — no temporary files written to disk, ensuring security and speed.
* **Lap Aggregation:** For each lap number encountered, the parser tracks `start_time` and `end_time` by iterating over all telemetry samples, computing lap duration as `end_time - start_time`. If any sample in a lap has `In Pits = 1`, the entire lap is flagged as a pit lap.
* **Caching Layer:** Results are cached via `@st.cache_data` to prevent redundant re-parsing on every UI interaction.

### Phase 2: Performance Analytics Engine
* **Lap Validation Filter:** Automatically discards `Lap 0` (a MoTeC artifact), pit-lane laps, and any laps under 20 seconds (session-ending glitches or outlaps), keeping only clean flying laps for statistics.
* **Consistency Score:** A custom 0–100% metric derived from the standard deviation of valid lap times. Formula: `max(0, min(100, 100 - (std_dev × 10)))`. A score of 100% represents robotically identical lap times; each full second of deviation costs 10 points.
* **Variance & Average:** Standard statistical measures computed exclusively on valid clean laps.
* **Perfect Stint Detection:** Identifies contiguous blocks of ≥4 consecutive valid laps where all times are below the session average **and** the block's standard deviation is ≤ 0.25s, highlighting them with a golden bounding box on the chart.

### Phase 3: Interactive Visualization (Plotly)
* **Scatter Plot:** Each lap is plotted as a marker with semantic color coding:
  * 🔵 **Blue** → Valid clean lap
  * 🟣 **Purple** → Fastest lap of the session
  * 🔴 **Red (translucent)** → Pit-in lap
  * ⚫ **Black** → Invalid lap (glitch/outlap)
* **Color-Graded Connecting Lines:** Segments between consecutive laps are colored on a **Green → Red gradient** proportional to the delta between the two lap times — instantly revealing where the biggest swings occurred.
* **Pit Zone Shading:** Contiguous pit laps are overlaid with a red translucent background `vrect`.
* **Dynamic Y-Axis:** Axis range and tick marks are auto-scaled and formatted as `MM:SS.mmm` to show only the relevant time window, preventing visual noise from outlier laps.
* **Range Slider:** Full-session navigation slider at the bottom for easy zooming into specific stint segments.

### Phase 4: AI Race Engineer (Groq + Llama 3.3) — ![Status](https://img.shields.io/badge/Status-Future_Integration-yellow?style=flat-square)

> **🚧 Planned Feature** — This phase is currently under active development and is not yet fully integrated into the main branch. The architecture and design decisions are documented here as a roadmap reference.

* **Context-Aware Analysis:** Before calling the LLM, the app will build a structured race context string from the UI — including track name, car class, and whether the race is multiclass or a sprint. This is injected into the system prompt.
* **Structured Prompt Engineering:** The agent will receive the **full lap-by-lap history** as a plain-text telemetry log alongside global stats (average, consistency %, variance, valid lap count).
* **Inference via Groq LPU:** Will use the `groq` SDK to call `llama-3.3-70b-versatile` at `temperature=0.3` for analytical rigidity, minimizing hallucinations and maximizing factual commentary on the data.
* **Spanish-Language Debrief:** The LLM will be instructed to respond exclusively in Spanish, using authentic motorsport terminology (delta, pacing, lift and coast, graining, clean air, outlap, etc.) and ending every report with a mandatory **engineer's numerical rating** from 0 to 10.
* **Demo Mode:** A bundled `data/lap_times.json` will allow users to experience the full app without uploading a real MoTeC file.

---

## Technical Stack

| Component | Technology |
|---|---|
| **UI Framework** | Streamlit |
| **Charting** | Plotly (Graph Objects) |
| **Telemetry Parser** | Python `csv` + `io` (in-memory) |
| **LLM Inference Engine** | Groq Cloud (LPU hardware) |
| **AI Model** | Llama 3.3 70B Versatile |
| **Numerical Computing** | NumPy |
| **Language** | Python 3.10+ |
| **API Secret Management** | python-dotenv |

---

## Project Structure

```
Time_graph/
├── app.py              # Main Streamlit application (UI, charts, AI integration)
├── llm_agent.py        # Groq/Llama AI Race Engineer module
├── extract_laps.py     # Standalone CLI script to pre-process a MoTeC CSV → JSON
├── data/
│   └── lap_times.json  # Bundled demo session data
├── logo.png            # Application logo
├── requirements.txt    # Python dependencies
└── .env                # API keys (not committed — see setup below)
```

---

## Usage

### Option A — Upload a real MoTeC session
1. Export your session from **MoTeC i2** as a `.csv` file.
2. Use the **sidebar uploader** to load the file.
3. The app will parse all laps, compute statistics, and render the scatter plot automatically.

### Option B — Explore with Demo Data
1. Check the **"Use Demo Data"** checkbox in the sidebar.
2. The bundled Le Mans demo session will load instantly — no file needed.

