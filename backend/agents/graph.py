"""LangGraph configuration for campaign flow with persistent auth gate."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from agents.nodes import (
    campaign_manager_node,
    check_auth_status_node,
    digital_scout_node,
    job_enricher_node,
    vetting_officer_node,
    wait_for_login_node,
)
from agents.state import AgentState


def _route_after_auth(state: AgentState) -> Literal["campaign", "wait_for_login"]:
    if str(state.get("auth_status", "")).lower() == "authenticated":
        return "campaign"
    return "wait_for_login"


def _route_after_wait(state: AgentState) -> Literal["campaign", "wait_for_login", "end"]:
    status = str(state.get("auth_status", "")).lower()
    if status == "authenticated":
        return "campaign"
    if status == "waiting_for_login":
        return "end"
    return "end"


def build_campaign_graph():
    """
    Build workflow with auth gate.

    Flow:
      scout -> enricher -> vetting -> check_auth_status
      check_auth_status -> campaign (if authenticated)
      check_auth_status -> wait_for_login (if auth required)
      wait_for_login -> END (paused) OR campaign (on Resume)
      campaign -> END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("scout", digital_scout_node)
    workflow.add_node("enricher", job_enricher_node)
    workflow.add_node("vetting", vetting_officer_node)
    workflow.add_node("check_auth_status", check_auth_status_node)
    workflow.add_node("wait_for_login", wait_for_login_node)
    workflow.add_node("campaign", campaign_manager_node)

    workflow.set_entry_point("scout")
    workflow.add_edge("scout", "enricher")
    workflow.add_edge("enricher", "vetting")
    workflow.add_edge("vetting", "check_auth_status")

    workflow.add_conditional_edges(
        "check_auth_status",
        _route_after_auth,
        {
            "campaign": "campaign",
            "wait_for_login": "wait_for_login",
        },
    )

    workflow.add_conditional_edges(
        "wait_for_login",
        _route_after_wait,
        {
            "campaign": "campaign",
            "wait_for_login": "wait_for_login",
            "end": END,
        },
    )

    workflow.add_edge("campaign", END)

    return workflow.compile()


def mark_resume_command(state: AgentState) -> AgentState:
    """Helper to signal manual-login completion from terminal command."""
    updated = dict(state)
    updated["login_resume_requested"] = True
    updated["resume_command"] = "resume"
    return updated
