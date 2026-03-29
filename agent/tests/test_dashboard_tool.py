"""Unit tests for the render_dashboard tool."""
import pytest
from tools.dashboard import make_dashboard_tool


class TestDashboardTool:
    def setup_method(self):
        self.tool = make_dashboard_tool()

    def test_tool_name(self):
        assert self.tool.name == "render_dashboard"

    def test_returns_html_unchanged(self):
        html = "<table><tr><td>CVA</td><td>1.5M</td></tr></table>"
        result = self.tool.invoke({"html": html})
        assert result == html

    def test_returns_chart_html_unchanged(self):
        html = '<canvas id="c"></canvas><script>new Chart(document.getElementById("c"),{});</script>'
        result = self.tool.invoke({"html": html})
        assert result == html

    def test_returns_empty_string(self):
        result = self.tool.invoke({"html": ""})
        assert result == ""

    def test_returns_plain_text_unchanged(self):
        # Even non-HTML input is returned as-is — the tool is a passthrough.
        result = self.tool.invoke({"html": "just text"})
        assert result == "just text"

    def test_make_dashboard_tool_returns_new_instances(self):
        """Each call to make_dashboard_tool() returns an independent tool object."""
        t1 = make_dashboard_tool()
        t2 = make_dashboard_tool()
        assert t1 is not t2
        assert t1.name == t2.name
