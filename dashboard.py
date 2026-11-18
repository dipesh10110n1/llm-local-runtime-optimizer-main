"""Orbit: a focused, local-first chat workspace."""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from core.model_registry import load_models
from optimizer.live_comparator import compare_on_spot
from optimizer.request_router import record_selection, selection_caption
from runtime.clients import InferenceError, backend_health
from runtime.supervisor import RuntimeSwitchError, ensure_runtime

st.set_page_config(
    page_title="Orbit",
    page_icon=":material/smart_toy:",
    layout="centered",
    initial_sidebar_state="expanded",
)

SUGGESTIONS = {
    ":material/lightbulb: Brainstorm an idea": "Help me brainstorm a practical project idea.",
    ":material/edit_note: Improve my writing": "Help me improve this writing: ",
    ":material/code: Solve a coding problem": "Help me solve this programming problem: ",
}


@st.cache_data(ttl=2)
def model_is_ready() -> bool:
    return backend_health("llama.cpp")


def local_models() -> list[dict[str, Any]]:
    return [model for model in load_models() if model["available_locally"]]


def clear_conversation() -> None:
    st.session_state.messages = []
    st.session_state.last_telemetry = None


if "messages" not in st.session_state:
    st.session_state.messages: list[dict[str, Any]] = []
if "last_telemetry" not in st.session_state:
    st.session_state.last_telemetry: dict[str, Any] | None = None

models = local_models()
runtime_model = models[0] if models else None
ready = model_is_ready()

with st.sidebar:
    st.title("Orbit", icon=":material/smart_toy:")
    st.caption("Your local AI workspace")
    if ready:
        st.badge("Local model online", icon=":material/check_circle:", color="green")
    else:
        st.badge("Local model offline", icon=":material/pending:", color="orange")
    st.space("medium")
    if st.button("New chat", icon=":material/add:", width="stretch", key="new_chat"):
        clear_conversation()
        st.rerun()
    st.space("small")
    temperature = st.slider("Creative latitude", 0.0, 1.0, 0.2, 0.1, key="temperature")
    max_tokens = st.slider("Response length", 64, 512, 256, 32, key="max_tokens")
    st.space("medium")
    st.caption("Private by design. Requests stay on this machine.")

if not st.session_state.messages:
    st.space("large")
    st.title("What can we figure out?", icon=":material/auto_awesome:")
    st.caption("Orbit is ready to help you reason, write, code, and explore.")
    st.space("medium")
    selected_suggestion = st.pills(
        "Start a conversation",
        list(SUGGESTIONS),
        selection_mode="single",
        label_visibility="collapsed",
        key="suggestions",
    )
else:
    st.title("Orbit", icon=":material/smart_toy:")
    st.caption("A private conversation with your local model")
    selected_suggestion = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("runtime"):
            st.caption(message["runtime"])

prompt = st.chat_input("Message Orbit", submit_mode="disable", key="chat_input")
if selected_suggestion:
    prompt = SUGGESTIONS[selected_suggestion]

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        selected = None
        decision: dict[str, Any] | None = None
        runtime_note: str | None = None
        if runtime_model is None:
            response_text = "No local GGUF model is registered. Add a model to the models folder, then restart Orbit."
            st.error(response_text, icon=":material/error:")
        else:
            started = time.perf_counter()
            completed = False
            with st.status(":shimmer[Comparing local Qwen responses for this prompt]", type="compact") as status:
                try:
                    decision = compare_on_spot(prompt, models, max_tokens, temperature)
                    selected = decision.get("selected")
                    if selected is None:
                        response_text = decision["reason"]
                        status.update(label="No safe local runtime", state="error")
                        st.warning(response_text, icon=":material/memory:")
                    else:
                        selected_model = selected["model"]
                        runtime_state = ensure_runtime(selected_model, decision["configuration"])
                        winner = decision["live_comparison"][decision["winner_index"]]
                        # Use the exact response that won the live comparison. Regenerating here
                        # would sample a different response after the model decision was made.
                        response_text = winner["draft"]
                        result = {
                            "answer": response_text,
                            "backend": "llama.cpp",
                            "end_to_end_seconds": winner["latency_seconds"],
                            "generated_tokens": winner.get("generated_tokens"),
                            "generation_tokens_per_second": winner.get("generation_tokens_per_second"),
                            "measurement_kind": "selected_candidate_response",
                        }
                        elapsed = round(time.perf_counter() - started, 1)
                        status.update(label=f"Selected response ready · {elapsed}s", state="complete")
                        st.session_state.last_telemetry = {
                            "final_generation": result,
                            "runtime_state": runtime_state,
                            "decision": decision,
                        }
                        record_selection(decision, result | {"runtime_switched": runtime_state["switched"]})
                        runtime_note = selection_caption(decision)
                        completed = True
                except (InferenceError, RuntimeSwitchError) as error:
                    response_text = f"Orbit could not complete that request: {error}"
                    status.update(label="Response unavailable", state="error")
                    st.error(response_text, icon=":material/error:")
            if completed:
                st.markdown(response_text)
                st.caption(runtime_note)
    st.session_state.messages.append({"role": "assistant", "content": response_text, "runtime": runtime_note})

if st.session_state.last_telemetry:
    with st.expander("Response details", icon=":material/info:"):
        details = st.session_state.last_telemetry
        decision = details.get("decision", {})
        comparison = decision.get("live_comparison", [])
        if comparison:
            st.subheader("On-the-spot model comparison")
            st.caption("Each complete response was generated sequentially from the same prompt. The answer above is the exact response selected by the local judge.")
            rows = []
            selected_id = decision.get("selected", {}).get("model", {}).get("model_id")
            for index, entry in enumerate(comparison, start=1):
                configuration = entry["configuration"]
                model_id = entry["candidate"]["model"]["model_id"]
                rows.append({
                    "Candidate": index,
                    "Model": model_id,
                    "Selected": model_id == selected_id,
                    "Backend": configuration["backend"],
                    "Threads": configuration["threads"],
                    "Context": configuration["context_size"],
                    "Cache": configuration["cache"],
                    "Response latency (s)": round(entry["latency_seconds"], 3),
                    "Generated tokens": entry.get("generated_tokens"),
                    "Tokens / second": round(entry["generation_tokens_per_second"], 2) if entry.get("generation_tokens_per_second") else None,
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption(f"Judge: {decision.get('judge_model_id', 'unavailable')} — {decision.get('reason', 'No decision reason recorded.')}")
            st.subheader("Judge verdict")
            st.code(decision.get("judge_output", "No judge verdict was recorded."), language=None)
            st.subheader("Complete candidate responses")
            for index, entry in enumerate(comparison, start=1):
                st.markdown(f"**Candidate {index} — {entry['candidate']['model']['model_id']}**")
                st.code(entry["draft"], language=None)
        st.subheader("Selected response telemetry")
        st.json({
            "selected_model": decision.get("selected", {}).get("model", {}).get("model_id"),
            "configuration": decision.get("configuration"),
            "runtime_switched": details.get("runtime_state", {}).get("switched"),
            "telemetry": details.get("final_generation"),
        })
