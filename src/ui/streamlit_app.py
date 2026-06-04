"""Optional Streamlit demo UI for the defense flow."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://app:8000").rstrip("/")


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def show_warnings(payload: dict[str, Any]) -> None:
    for warning in payload.get("warnings") or []:
        st.warning(warning)


def render_stats() -> None:
    st.header("Stats and Readiness")
    catalog = api_get("/stats/catalog")
    ml = api_get("/stats/ml")
    readiness = api_get("/stats/readiness")
    cols = st.columns(3)
    cols[0].metric("Source games", catalog.get("source_games", 0))
    cols[1].metric("Canonical games", catalog.get("canonical_games", 0))
    cols[2].metric("Candidate pairs", ml.get("candidate_pairs", 0))
    st.subheader("Readiness")
    st.json(readiness)
    show_warnings(catalog)
    show_warnings(ml)


def render_catalog() -> None:
    st.header("Catalog")
    search = st.text_input("Search", value="doom")
    catalog = api_get("/games", {"search": search, "limit": 20})
    show_warnings(catalog)
    items = catalog.get("items") or []
    if not items:
        st.info("No catalog rows available.")
        return
    selected = st.selectbox("Game", items, format_func=lambda row: row.get("name") or "")
    st.json(api_get(f"/games/{selected['canonical_game_id']}"))


def render_recommendations() -> None:
    st.header("Recommendations")
    search = st.text_input("Find seed game", value="doom", key="rec_search")
    catalog = api_get("/games", {"search": search, "limit": 20})
    items = catalog.get("items") or []
    if not items:
        show_warnings(catalog)
        st.info("No seed games available.")
        return
    selected = st.selectbox("Seed", items, format_func=lambda row: row.get("name") or "")
    algorithm = st.selectbox(
        "Algorithm",
        ["content_jaccard_v1", "hybrid_content_rating_v1"],
    )
    similar = api_get(
        f"/games/{selected['canonical_game_id']}/similar",
        {"limit": 10, "algorithm": algorithm},
    )
    show_warnings(similar)
    st.dataframe(similar.get("items") or [])


def render_manual_review() -> None:
    st.header("Manual Review Queue")
    status = st.selectbox("Status", ["pending", "reviewed", "all"])
    payload = api_get("/matches/review", {"limit": 50, "review_status": status})
    show_warnings(payload)
    st.dataframe(payload.get("items") or [])
    st.caption("Write updates are available through PATCH /matches/review/{pair_id}.")


def render_explanations() -> None:
    st.header("Grounded Explanations")
    tab_rec, tab_match = st.tabs(["Recommendation", "Match"])
    with tab_rec:
        payload = api_get("/explain/recommendation", {"limit": 10})
        show_warnings(payload)
        st.dataframe(payload.get("items") or [])
    with tab_match:
        payload = api_get("/explain/match", {"limit": 10})
        show_warnings(payload)
        st.dataframe(payload.get("items") or [])


def main() -> None:
    st.set_page_config(page_title="Game Intelligence Platform", layout="wide")
    st.title("Game Intelligence Platform Demo")
    st.caption(f"API base URL: {API_BASE_URL}")
    page = st.sidebar.radio(
        "Page",
        [
            "Stats/readiness",
            "Catalog",
            "Similar games",
            "Manual review",
            "Explanations",
        ],
    )
    try:
        if page == "Stats/readiness":
            render_stats()
        elif page == "Catalog":
            render_catalog()
        elif page == "Similar games":
            render_recommendations()
        elif page == "Manual review":
            render_manual_review()
        else:
            render_explanations()
    except Exception as exc:
        st.error(f"Demo UI failed to load API data: {exc}")
        st.info("Check that FastAPI is running and API_BASE_URL is correct.")


if __name__ == "__main__":
    main()
