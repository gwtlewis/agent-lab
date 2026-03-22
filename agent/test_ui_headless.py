"""
Headless browser tests for the Agent Lab chat UI.

Strategy:
- Spin up the FastAPI server in a background thread (in-process).
- Each test injects a mock WebSocket (via Playwright add_init_script) that speaks
  the agent protocol without hitting a real LLM or Ollama.
- Playwright drives Chromium headlessly and asserts on DOM/behaviour.

Mock design:
- `_ws_mock_script(init_events, response_batches)` injects an init script that
  replaces window.WebSocket with a fake that:
    * supports addEventListener (the pattern app.js uses)
    * fires `open` then `init_events` immediately after page load
    * on each send() call (non-ping, non-clear), fires the next response batch
    * on send({type:"clear"}), automatically replies with a `cleared` event

All tests are deterministic — no live Ollama or real LLM calls.
"""

from __future__ import annotations

import json
import re
import threading
import time
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── Server fixture ────────────────────────────────────────────────────────────

SERVER_PORT = 18765  # non-standard port to avoid conflicts


def _build_mock_agent(chunks):
    """Return a mocked IntegratedAgent whose stream_events yields chunks."""
    agent = MagicMock()
    agent.stream_events.return_value = iter(chunks)
    agent.clear_memory = MagicMock()
    return agent


@pytest.fixture(scope="session")
def server_url():
    """Start the FastAPI server once for the whole test session."""
    from event_model import AgentEvent

    default_chunks = [
        AgentEvent.status("thinking"),
        AgentEvent.token("Hello"),
        AgentEvent.final("Hello"),
    ]

    with (
        patch("web_server.IntegratedAgent") as mock_cls,
        patch("agent.requests.get") as mock_get,
        patch("agent.ChatOllama"),
    ):
        resp = MagicMock()
        resp.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        mock_get.return_value = resp
        mock_cls.return_value = _build_mock_agent(default_chunks)

        from web_server import app

        config = uvicorn.Config(app, host="127.0.0.1", port=SERVER_PORT, log_level="error")
        server = uvicorn.Server(config)

        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(30):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{SERVER_PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.3)

        yield f"http://127.0.0.1:{SERVER_PORT}"
        server.should_exit = True


@pytest.fixture()
def page(server_url) -> Generator[Page, None, None]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        p = ctx.new_page()
        yield p
        ctx.close()
        browser.close()


# ── Mock WebSocket helper ─────────────────────────────────────────────────────

def _connected_event(provider="ollama", model="qwen3:8b"):
    return {"type": "status", "content": "connected",
            "metadata": {"provider": provider, "model": model}}


def _ws_mock_script(init_events: list, response_batches: list | None = None) -> str:
    """Return a Playwright init-script that replaces window.WebSocket.

    Args:
        init_events:      Events fired right after the 'open' event (normally
                          just the connected status handshake).
        response_batches: A list of event-lists.  Each inner list is fired (in
                          order) when the JS app calls send() with a non-ping,
                          non-clear message.  Send({type:"clear"}) automatically
                          gets a {type:"cleared"} reply regardless of this list.
    """
    init_json = json.dumps(init_events)
    resp_json = json.dumps(response_batches or [])
    return f"""
    (function () {{
      const INIT_EVENTS = {init_json};
      const RESPONSE_BATCHES = {resp_json};
      let batchIdx = 0;

      window.WebSocket = function (url) {{
        const self = this;
        const _listeners = {{}};

        /* readyState = OPEN from the start so sendMessage() passes its guard */
        self.readyState = 1;

        /* app.js uses addEventListener — the mock must support it */
        self.addEventListener = function (type, fn) {{
          if (!_listeners[type]) _listeners[type] = [];
          _listeners[type].push(fn);
        }};

        function dispatch(type, eventObj) {{
          (_listeners[type] || []).forEach(function (fn) {{ fn(eventObj); }});
          if (typeof self['on' + type] === 'function') {{
            self['on' + type](eventObj);
          }}
        }}

        function sendMsg(ev) {{
          dispatch('message', {{ data: JSON.stringify(ev) }});
        }}

        self.send = function (raw) {{
          let msg;
          try {{ msg = JSON.parse(raw); }} catch (e) {{ return; }}
          if (msg.type === 'ping') return;
          if (msg.type === 'clear') {{
            /* server always replies with cleared */
            setTimeout(function () {{
              sendMsg({{ type: 'cleared', content: '', metadata: {{}} }});
            }}, 30);
            return;
          }}
          /* regular message: fire next response batch */
          var batch = RESPONSE_BATCHES[batchIdx] || [];
          batchIdx++;
          setTimeout(function () {{
            batch.forEach(function (ev) {{ sendMsg(ev); }});
          }}, 30);
        }};

        self.close = function () {{}};

        /* Fire open + init events shortly after construction */
        setTimeout(function () {{
          dispatch('open', {{}});
          INIT_EVENTS.forEach(function (ev) {{ sendMsg(ev); }});
        }}, 30);

        window.__mockWS = self;
      }};

      window.WebSocket.OPEN   = 1;
      window.WebSocket.CLOSED = 3;
    }})();
    """


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPageLoad:
    def test_page_title(self, page, server_url):
        page.goto(server_url)
        expect(page).to_have_title("Agent Lab")

    def test_header_visible(self, page, server_url):
        page.goto(server_url)
        expect(page.locator(".app-name")).to_have_text("Agent Lab")

    def test_empty_state_shown_initially(self, page, server_url):
        page.goto(server_url)
        expect(page.locator("#empty-state")).to_be_visible()

    def test_send_button_present(self, page, server_url):
        page.goto(server_url)
        expect(page.locator("#send-btn")).to_be_visible()

    def test_input_focusable(self, page, server_url):
        page.goto(server_url)
        page.locator("#user-input").click()
        expect(page.locator("#user-input")).to_be_focused()


class TestConnectionStatus:
    def test_status_dot_becomes_connected(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(300)
        dot = page.locator("#status-dot")
        # setStatus("connected") sets class to "status-dot status-dot--connected"
        expect(dot).to_have_class(re.compile(r"status-dot--connected"))

    def test_provider_badge_populated(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(300)
        expect(page.locator("#provider-badge")).not_to_have_text("—")


class TestSendMessage:
    def test_user_bubble_appears(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status", "content": "thinking", "metadata": {}},
                {"type": "token",  "content": "hi",       "metadata": {}},
                {"type": "final",  "content": "hi",
                 "metadata": {"reasoning_shown": False}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("Hello there")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(400)
        expect(page.locator(".message--user .bubble").first).to_have_text("Hello there")

    def test_agent_bubble_appears(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status",  "content": "thinking",    "metadata": {}},
                {"type": "token",   "content": "Hello World", "metadata": {}},
                {"type": "final",   "content": "Hello World",
                 "metadata": {"reasoning_shown": False}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("greet me")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(500)
        expect(page.locator(".message--agent .bubble").first).to_have_text("Hello World")

    def test_empty_state_disappears_on_send(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "final", "content": "ok",
                 "metadata": {"reasoning_shown": False}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("test")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(300)
        expect(page.locator("#empty-state")).not_to_be_visible()


class TestInputConstraints:
    def test_send_button_disabled_during_streaming(self, page, server_url):
        # No response batch → app stays in streaming state indefinitely
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("msg")
        page.locator("#send-btn").click()
        expect(page.locator("#send-btn")).to_be_disabled()

    def test_empty_input_does_not_send(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#send-btn").click()
        expect(page.locator("#empty-state")).to_be_visible()

    def test_shift_enter_does_not_send(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("line one")
        page.keyboard.press("Shift+Enter")  # should insert newline, not send
        expect(page.locator("#empty-state")).to_be_visible()


class TestReasoningPanel:
    def test_reasoning_panel_hidden_by_default(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(200)
        expect(page.locator("#reasoning-panel")).not_to_be_visible()

    def test_reasoning_panel_shows_on_reasoning_event(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status",    "content": "thinking",      "metadata": {}},
                {"type": "reasoning", "content": "Let me think…", "metadata": {}},
                {"type": "token",     "content": "result",        "metadata": {}},
                {"type": "final",     "content": "result",
                 "metadata": {"reasoning_shown": True}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("complex question")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(500)
        expect(page.locator("#reasoning-panel")).to_be_visible()

    def test_reasoning_toggle_expands_body(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status",    "content": "thinking",         "metadata": {}},
                {"type": "reasoning", "content": "thinking content", "metadata": {}},
                {"type": "final",     "content": "done",
                 "metadata": {"reasoning_shown": True}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("q")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(500)
        # Panel is visible; body starts collapsed — toggle expands it
        page.locator("#reasoning-toggle").click()
        expect(page.locator("#reasoning-body")).to_be_visible()


class TestClearConversation:
    def test_clear_button_removes_messages(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status", "content": "thinking", "metadata": {}},
                {"type": "final",  "content": "yes",
                 "metadata": {"reasoning_shown": False}},
            ]],
            # clear button automatically gets {type:"cleared"} from the mock
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("hi")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(400)
        page.locator("#clear-btn").click()
        page.wait_for_timeout(300)
        expect(page.locator(".message")).to_have_count(0)


class TestErrorHandling:
    def test_error_event_renders_in_bubble(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status", "content": "thinking",       "metadata": {}},
                {"type": "error",  "content": "LLM unavailable","metadata": {}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("q")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(400)
        err_bubble = page.locator(".bubble--error")
        expect(err_bubble).to_be_visible()
        expect(err_bubble).to_have_text("LLM unavailable")

    def test_input_re_enabled_after_error(self, page, server_url):
        page.add_init_script(_ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status", "content": "thinking", "metadata": {}},
                {"type": "error",  "content": "boom",     "metadata": {}},
            ]],
        ))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("q")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(400)
        expect(page.locator("#send-btn")).not_to_be_disabled()


class TestKeyboardAccessibility:
    def test_tab_to_send_button(self, page, server_url):
        page.add_init_script(_ws_mock_script([_connected_event()]))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.keyboard.press("Tab")
        focused = page.evaluate("() => document.activeElement.tagName")
        assert focused in ("BUTTON", "INPUT", "TEXTAREA", "A")


# ── Markdown rendering ────────────────────────────────────────────────────────

class TestMarkdownRendering:
    """Verify that agent responses are rendered as HTML from Markdown."""

    def _script(self, md_text: str) -> str:
        """Inject mock that replies with a single final event containing md_text."""
        return _ws_mock_script(
            init_events=[_connected_event()],
            response_batches=[[
                {"type": "status", "content": "thinking", "metadata": {}},
                {"type": "final",  "content": md_text,
                 "metadata": {"reasoning_shown": False}},
            ]],
        )

    def _send(self, page, server_url: str, md_text: str, wait_ms: int = 400):
        """Navigate, inject mock, send one message, wait for response."""
        page.add_init_script(self._script(md_text))
        page.goto(server_url)
        page.wait_for_timeout(200)
        page.locator("#user-input").fill("q")
        page.locator("#user-input").press("Enter")
        page.wait_for_timeout(wait_ms)

    # ── structural elements ──────────────────────────────────────────────────

    def test_bold_renders_as_strong(self, page, server_url):
        self._send(page, server_url, "This is **bold** text.")
        expect(page.locator(".message--agent .bubble strong")).to_be_visible()
        expect(page.locator(".message--agent .bubble strong")).to_have_text("bold")

    def test_italic_renders_as_em(self, page, server_url):
        self._send(page, server_url, "This is *italic* text.")
        expect(page.locator(".message--agent .bubble em")).to_be_visible()
        expect(page.locator(".message--agent .bubble em")).to_have_text("italic")

    def test_inline_code_renders_as_code(self, page, server_url):
        self._send(page, server_url, "Call `print()` to output.")
        code = page.locator(".message--agent .bubble code")
        expect(code).to_be_visible()
        expect(code).to_have_text("print()")

    def test_fenced_code_block_renders_as_pre(self, page, server_url):
        self._send(page, server_url, "```python\nx = 42\n```")
        expect(page.locator(".message--agent .bubble pre")).to_be_visible()
        expect(page.locator(".message--agent .bubble pre")).to_contain_text("x = 42")

    def test_heading_renders_as_h2(self, page, server_url):
        self._send(page, server_url, "## Section Title")
        h2 = page.locator(".message--agent .bubble h2")
        expect(h2).to_be_visible()
        expect(h2).to_have_text("Section Title")

    def test_bullet_list_renders_as_ul_li(self, page, server_url):
        self._send(page, server_url, "- Alpha\n- Beta\n- Gamma")
        items = page.locator(".message--agent .bubble ul li")
        expect(items).to_have_count(3)
        expect(items.first).to_have_text("Alpha")

    def test_ordered_list_renders_as_ol_li(self, page, server_url):
        self._send(page, server_url, "1. First\n2. Second")
        items = page.locator(".message--agent .bubble ol li")
        expect(items).to_have_count(2)

    def test_link_renders_as_anchor_with_href(self, page, server_url):
        self._send(page, server_url, "[GitHub](https://github.com)")
        link = page.locator(".message--agent .bubble a")
        expect(link).to_be_visible()
        expect(link).to_have_text("GitHub")
        expect(link).to_have_attribute("href", "https://github.com")

    def test_blockquote_renders(self, page, server_url):
        self._send(page, server_url, "> Famous quote here.")
        bq = page.locator(".message--agent .bubble blockquote")
        expect(bq).to_be_visible()
        expect(bq).to_contain_text("Famous quote here.")

    # ── plain-text passthrough ───────────────────────────────────────────────

    def test_plain_text_still_displays(self, page, server_url):
        self._send(page, server_url, "Just plain text.")
        expect(page.locator(".message--agent .bubble")).to_contain_text("Just plain text.")

    # ── XSS safety ──────────────────────────────────────────────────────────

    def test_script_tag_is_stripped(self, page, server_url):
        self._send(page, server_url,
                   "Hello <script>window.__xss_marker=1</script> World")
        # No <script> element should exist inside the bubble
        assert page.locator(".message--agent .bubble script").count() == 0
        # The injected JS must not have run
        ran = page.evaluate("() => typeof window.__xss_marker !== 'undefined'")
        assert not ran, "XSS payload executed — DOMPurify did not sanitize"

    def test_onclick_attribute_is_stripped(self, page, server_url):
        self._send(page, server_url,
                   '<a href="#" onclick="window.__onclick_ran=1">click</a>')
        ran = page.evaluate("() => typeof window.__onclick_ran !== 'undefined'")
        assert not ran

    # ── history restore ──────────────────────────────────────────────────────

    def test_markdown_preserved_across_history_restore(self, page, server_url):
        """Reload the page (same session) and verify markdown re-renders correctly."""
        self._send(page, server_url, "This is **bold** text.")
        # Navigate away and back to trigger restoreHistory
        page.goto("about:blank")
        page.goto(server_url)
        page.wait_for_timeout(400)
        # The restored bubble should still have a <strong> element
        expect(page.locator(".message--agent .bubble strong")).to_be_visible()

