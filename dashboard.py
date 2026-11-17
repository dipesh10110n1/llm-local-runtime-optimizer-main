"""Streamlit dashboard that displays recorded CSV data without fabricating values."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"


@st.cache_data
def read_csv(name: str) -> pd.DataFrame:
    path = LOGS / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


st.set_page_config(page_title="Local LLM Runtime Optimizer", layout="wide")
st.title("Local LLM Runtime Optimizer")
page = st.sidebar.selectbox("Page", ["Overview", "Hardware Profile", "Model Registry", "Dataset Management", "Benchmark Experiments", "Quality Evaluation", "Performance Comparison", "Resource and Energy Analysis", "Optimization Recommendations", "Live Inference", "Experiment History"])

if page == "Overview":
    benchmark = read_csv("benchmark_results_v2.csv")
    quality = read_csv("combined_quality_scores.csv")
    st.metric("Recorded benchmark trials", len(benchmark))
    st.metric("Recorded quality reviews", len(quality))
    st.info("All values shown come from repository CSV records. Energy is unavailable until a real meter is integrated.")
elif page == "Hardware Profile":
    from hardware.hardware_profiler import profile_hardware
    st.json(profile_hardware())
elif page == "Model Registry":
    from config.model_registry import load_model_registry
    st.dataframe(pd.DataFrame(load_model_registry()), use_container_width=True)
elif page == "Dataset Management":
    import json
    st.write("Prepared datasets are opt-in. Run `python -m datasets.dataset_loader <dataset>` after reviewing its manifest and terms.")
    st.json(json.loads((ROOT / "datasets" / "manifests" / "official_datasets.json").read_text()))
elif page == "Quality Evaluation":
    dataframe = read_csv("combined_quality_scores.csv")
    if dataframe.empty:
        st.warning("No quality records are available.")
    else:
        st.plotly_chart(px.bar(dataframe, x="question_id", y="quality_percentage", color="task_type"), use_container_width=True)
        st.dataframe(dataframe)
elif page in ("Benchmark Experiments", "Performance Comparison", "Experiment History"):
    dataframe = read_csv("benchmark_results_v2.csv")
    if dataframe.empty:
        st.warning("No benchmark trials available.")
    else:
        st.plotly_chart(px.scatter(dataframe, x="trial_number", y="wall_time_seconds", color="model", hover_data=dataframe.columns), use_container_width=True)
        st.dataframe(dataframe)
elif page == "Resource and Energy Analysis":
    dataframe = read_csv("benchmark_results_v2.csv")
    if not dataframe.empty:
        st.plotly_chart(px.box(dataframe, y="peak_process_ram_mb", color="model"), use_container_width=True)
    st.warning("No direct energy telemetry has been recorded. CPU/GPU utilization is not energy consumption.")
elif page == "Optimization Recommendations":
    from optimizer.profile_loader import legacy_profiles
    st.write("Profiles are aggregate legacy measurements, not per-request guarantees.")
    st.json([{"configuration": x.configuration.as_dict(), "quality": x.quality, "latency_seconds": x.latency_seconds, "ram_mb": x.ram_mb, "sample_count": x.sample_count, "notes": x.notes} for x in legacy_profiles()])
else:
    st.info("Use the local API (`POST /api/v1/generate`) for live inference. This dashboard does not launch model servers or expose ports.")
