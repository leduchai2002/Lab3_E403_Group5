"""
app.py — Streamlit UI for Lab 3 (E403 Group 5)

Provides a unified chat interface for both the Baseline Chatbot and the
ReAct Agent.  Run with:

    streamlit run app.py

Environment variables (loaded from .env):
    DEFAULT_PROVIDER   — chatbot provider: openai | google | local  (default: openai)
    DEFAULT_MODEL      — model name passed to the provider           (default: gpt-4o)
    OPENAI_API_KEY     — required when provider is openai
    GEMINI_API_KEY     — required when provider is google
    LOCAL_MODEL_PATH   — path to .gguf file when provider is local
"""

import os
import sys
import io

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lab 3 — AI Chat UI",
    page_icon="🤖",
    layout="centered",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    # Mode selector
    mode = st.radio(
        "Mode",
        ["💬 Chatbot", "🤖 Agent"],
        key="mode_radio",
    )

    st.divider()

    # Provider selector (only meaningful for Chatbot; Agent always uses OpenAI)
    if mode == "💬 Chatbot":
        provider_name = st.selectbox(
            "Provider",
            ["openai", "google", "local"],
            index=["openai", "google", "local"].index(
                os.getenv("DEFAULT_PROVIDER", "openai")
            )
            if os.getenv("DEFAULT_PROVIDER", "openai") in ["openai", "google", "local"]
            else 0,
        )
    else:
        provider_name = "openai"
        default_model = os.getenv("DEFAULT_MODEL", "gpt-4o")
        st.info(f"Agent uses OpenAI — `{default_model}`")

    # Max steps slider (Agent only)
    if mode == "🤖 Agent":
        max_steps = st.slider("Max reasoning steps", min_value=3, max_value=10, value=5)
    else:
        max_steps = 5

    st.divider()

    # Clear conversation button
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chatbot = None
        st.session_state.agent = None
        st.rerun()

# ── Session state initialisation ─────────────────────────────────────────────
for key, default in [
    ("messages", []),
    ("chatbot", None),
    ("agent", None),
    ("last_mode", None),
    ("last_provider", None),
    ("last_max_steps", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Reset conversation when mode / provider / max_steps changes
config_changed = (
    st.session_state.last_mode != mode
    or st.session_state.last_provider != provider_name
    or st.session_state.last_max_steps != max_steps
)
if config_changed:
    st.session_state.messages = []
    st.session_state.chatbot = None
    st.session_state.agent = None
    st.session_state.last_mode = mode
    st.session_state.last_provider = provider_name
    st.session_state.last_max_steps = max_steps

# ── Main UI ──────────────────────────────────────────────────────────────────
mode_label = "Chatbot" if "Chatbot" in mode else "ReAct Agent"
st.title(f"{'💬' if 'Chatbot' in mode else '🤖'} {mode_label}")
st.caption("Lab 3 — E403 Group 5 | Baseline Chatbot vs ReAct Agent")

# ── Conversation history display ─────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # Show captured agent reasoning steps if present
        steps = msg.get("steps", "").strip()
        if steps:
            with st.expander("🔍 Agent reasoning steps", expanded=False):
                st.code(steps, language="text")

# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input("Type your message…")

if prompt:
    # ── Display user message immediately ──────────────────────────────────────
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # ── Generate assistant response ───────────────────────────────────────────
    with st.chat_message("assistant"):

        # ── Chatbot branch ────────────────────────────────────────────────────
        if "Chatbot" in mode:
            # Lazy-init the chatbot instance
            if st.session_state.chatbot is None:
                with st.spinner("Initialising provider…"):
                    try:
                        from src.chatbot.runner import build_provider
                        from src.chatbot.chatbot import BaselineChatbot

                        llm = build_provider(provider_name)
                        st.session_state.chatbot = BaselineChatbot(llm=llm)
                    except Exception as exc:
                        st.error(f"Failed to initialise provider `{provider_name}`: {exc}")
                        st.stop()

            with st.spinner("Thinking…"):
                try:
                    reply = st.session_state.chatbot.chat(prompt)
                except Exception as exc:
                    reply = f"[ERROR] {exc}"

            st.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

        # ── Agent branch ──────────────────────────────────────────────────────
        else:
            # Lazy-init the agent instance
            if st.session_state.agent is None:
                with st.spinner("Initialising agent…"):
                    try:
                        from src.core.openai_provider import OpenAIProvider
                        from src.agent.agent import ReActAgent
                        from src.tools.inventory_tools import INVENTORY_TOOLS

                        model = os.getenv("DEFAULT_MODEL", "gpt-4o")
                        llm = OpenAIProvider(model_name=model)
                        st.session_state.agent = ReActAgent(
                            llm=llm,
                            tools=INVENTORY_TOOLS,
                            max_steps=max_steps,
                        )
                    except Exception as exc:
                        st.error(f"Failed to initialise agent: {exc}")
                        st.stop()

            # Capture intermediate stdout (Tool calls + Observations printed
            # by ReActAgent._execute_tool) so we can display them in the UI.
            captured = io.StringIO()
            sys.stdout = captured
            try:
                with st.spinner("Running agent…"):
                    reply = st.session_state.agent.run(prompt)
            except Exception as exc:
                reply = f"[ERROR] {exc}"
            finally:
                sys.stdout = sys.__stdout__

            steps = captured.getvalue()

            st.write(reply)
            if steps.strip():
                with st.expander("🔍 Agent reasoning steps", expanded=True):
                    st.code(steps, language="text")

            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "steps": steps,
            })
