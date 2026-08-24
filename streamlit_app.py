import requests
import streamlit as st

st.set_page_config(page_title="Transit Alert Assistant", page_icon="🚇")

# Point this at your local FastAPI server, or your EC2 public IP/domain
# once you're ready to demo against the live deployment.
API_BASE_URL = st.sidebar.text_input(
    "API base URL",
    value="http://127.0.0.1:8000",
    help="Use http://127.0.0.1:8000 for local testing, or your EC2 URL for the live version.",
)

st.title("🚇 NYC Transit Alert Assistant")
st.caption("Ask a natural-language question about current subway service alerts.")

# --- Health status in the sidebar, so you can show it's actually live ---
with st.sidebar:
    st.subheader("System status")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=5).json()
        if health.get("status") == "ok":
            st.success("API is up")
        else:
            st.warning(f"API status: {health.get('status')}")

        if health.get("feed_ok"):
            st.success("Feed: live")
        else:
            st.error(f"Feed error: {health.get('feed_error')}")

        if health.get("alerts_last_updated"):
            st.caption(f"Alerts last updated: {health['alerts_last_updated']}")
    except requests.RequestException as exc:
        st.error(f"Can't reach API at {API_BASE_URL}\n\n{exc}")

# --- Keep a running chat history in the session ---
if "history" not in st.session_state:
    st.session_state.history = []

for entry in st.session_state.history:
    with st.chat_message("user"):
        st.write(entry["question"])
    with st.chat_message("assistant"):
        st.write(entry["answer"])
        if entry.get("stale"):
            st.caption("⚠️ Answer based on possibly stale alert data.")

question = st.chat_input("Ask about subway delays, service changes, etc.")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Checking current alerts..."):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/ask",
                    params={"question": question},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                answer = data.get("answer", "No answer returned.")
                stale = data.get("stale", False)

                st.write(answer)
                if stale:
                    st.caption("⚠️ Answer based on possibly stale alert data.")

                st.session_state.history.append(
                    {"question": question, "answer": answer, "stale": stale}
                )
            except requests.RequestException as exc:
                st.error(f"Request failed: {exc}")
