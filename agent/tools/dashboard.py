"""Dashboard rendering tool for the agent.

Registers a ``render_dashboard`` LangChain tool that the LLM can call to
display a financial dashboard in the browser UI.  The tool returns the HTML
fragment as-is; the agent dispatch loop (``IntegratedAgent.stream_events``)
detects the tool name and routes it to an ``AgentEvent.board`` event instead
of the normal ``tool_call`` pill.

Chart.js is pre-loaded in the iframe template on the frontend, so the LLM can
write ``new Chart(...)`` directly without referencing any external CDN.
Tables should use plain ``<table>`` HTML — no library needed.
"""

from langchain_core.tools import tool as lc_tool


def make_dashboard_tool():
    """Return a LangChain ``render_dashboard`` tool instance."""

    @lc_tool
    def render_dashboard(html: str) -> str:
        """Render a financial dashboard in the UI panel.

        Use this tool whenever the user asks to draw, visualize, show, or
        render a chart, table, board, or dashboard with data.

        Chart.js is pre-loaded — use ``new Chart(document.getElementById(...), {...})``
        for charts.  For tabular data use plain ``<table>`` HTML.  For KPI
        cards, use ``<div>`` elements with inline styles.

        Return a self-contained HTML fragment.  Do NOT include ``<html>``,
        ``<head>``, or ``<body>`` tags — the fragment is injected into a
        pre-styled page that already loads Chart.js.

        Args:
            html: Valid HTML fragment containing charts, tables, or KPI cards.
        """
        return html  # routed to AgentEvent.board by the dispatch loop

    return render_dashboard
