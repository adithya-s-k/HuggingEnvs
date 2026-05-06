"""
Gradio UI for the Desktop Computer-Use environment.

Directly drives the DesktopEnvironment instance — no MCP layer in between.
"""

import base64
import io
from typing import Any, Optional

import gradio as gr
from PIL import Image


APP_CHOICES = [
    "libreoffice-calc",
    "libreoffice-writer",
    "libreoffice-impress",
    "firefox",
    "blender",
    "gimp",
    "terminal",
    "desktop",
]


def desktop_ui_builder(env_factory, **kwargs) -> gr.Blocks:
    """Build the Gradio Blocks UI for the desktop environment."""

    # Single shared env instance for the UI session
    _env = {"instance": None}

    def _get_env():
        if _env["instance"] is None:
            _env["instance"] = env_factory()
        return _env["instance"]

    with gr.Blocks(title="Desktop Computer-Use Environment") as demo:
        action_log_state = gr.State([])

        gr.Markdown("# Desktop Computer-Use Environment")
        gr.Markdown("Interact with a cloud desktop via E2B. Select an app, reset, then use the controls below.")

        with gr.Row():
            # ── Left Column: Controls ──
            with gr.Column(scale=1):
                gr.Markdown("### Setup")
                app_dropdown = gr.Dropdown(
                    choices=APP_CHOICES,
                    value="libreoffice-calc",
                    label="Application",
                )
                custom_cmd = gr.Textbox(
                    label="Custom launch command (optional)",
                    placeholder="e.g., inkscape",
                )
                reset_btn = gr.Button("Reset (New Sandbox)", variant="primary")
                status_box = gr.Textbox(label="Status", interactive=False, lines=3)
                stream_link = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("### Mouse Actions")
                with gr.Row():
                    x_input = gr.Number(label="X", value=500, precision=0)
                    y_input = gr.Number(label="Y", value=300, precision=0)
                click_btn = gr.Button("Click")
                dbl_click_btn = gr.Button("Double Click")
                r_click_btn = gr.Button("Right Click")

                gr.Markdown("### Keyboard")
                text_input = gr.Textbox(label="Type Text", placeholder="Hello world")
                type_btn = gr.Button("Type")
                key_input = gr.Textbox(label="Press Key", placeholder="enter, ctrl+s, etc.")
                key_btn = gr.Button("Press Key")

                gr.Markdown("### Scroll")
                with gr.Row():
                    scroll_dir = gr.Dropdown(choices=["down", "up"], value="down", label="Direction")
                    scroll_amt = gr.Number(label="Amount", value=3, precision=0)
                scroll_btn = gr.Button("Scroll")

                gr.Markdown("### Shell")
                cmd_input = gr.Textbox(label="Command", placeholder="ls -la")
                cmd_btn = gr.Button("Run Command")
                cmd_output = gr.Textbox(label="Output", interactive=False, lines=5)

            # ── Right Column: Screenshot + History ──
            with gr.Column(scale=2):
                gr.Markdown("### Desktop View")
                screenshot_btn = gr.Button("Take Screenshot", variant="secondary")
                screenshot_img = gr.Image(label="Screenshot", type="pil", height=600)

                gr.Markdown("### Action History")
                action_log = gr.Textbox(
                    label="Actions",
                    interactive=False,
                    lines=10,
                    max_lines=20,
                )

        # ── Helpers ──

        def _format_log(log):
            if not log:
                return ""
            numbered = [f"{i+1}. {a}" for i, a in enumerate(log[-20:])]
            return "\n".join(reversed(numbered))

        # ── Event Handlers — directly call E2B sandbox ──

        def on_reset(app_name, custom):
            app = custom.strip() if custom.strip() else app_name
            env = _get_env()
            try:
                obs = env.reset(app=app)
                meta = obs.metadata or {}
                url = meta.get("stream_url", "")
                sandbox_id = meta.get("sandbox_id", "?")
                msg = meta.get("message", "Ready")
                link_md = f"**[Open Desktop Stream]({url})**" if url else ""
                return (
                    f"App: {app}\nSandbox: {sandbox_id}\n{msg}",
                    link_md,
                    [],
                    "",
                    None,
                )
            except Exception as e:
                import traceback
                return f"Error: {e}\n{traceback.format_exc()}", "", [], "", None

        def on_screenshot(log):
            env = _get_env()
            try:
                if not env._sandbox:
                    log = log or []
                    log.append("ERROR: Reset first!")
                    return None, _format_log(log), log
                data = env._sandbox.screenshot()
                img = Image.open(io.BytesIO(data))
                log = log or []
                log.append("screenshot")
                return img, _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"screenshot ERROR: {e}")
                return None, _format_log(log), log

        def on_click(x, y, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                env._sandbox.left_click(int(x), int(y))
                log = log or []
                log.append(f"click({int(x)}, {int(y)})")
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"click ERROR: {e}")
                return _format_log(log), log

        def on_dbl_click(x, y, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                env._sandbox.double_click(int(x), int(y))
                log = log or []
                log.append(f"double_click({int(x)}, {int(y)})")
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"double_click ERROR: {e}")
                return _format_log(log), log

        def on_right_click(x, y, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                env._sandbox.right_click(int(x), int(y))
                log = log or []
                log.append(f"right_click({int(x)}, {int(y)})")
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"right_click ERROR: {e}")
                return _format_log(log), log

        def on_type(text, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                env._sandbox.write(text)
                log = log or []
                log.append(f'type("{text[:40]}")')
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"type ERROR: {e}")
                return _format_log(log), log

        def on_press_key(key, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                if "+" in key:
                    keys = [k.strip() for k in key.split("+")]
                    env._sandbox.press(keys)
                else:
                    env._sandbox.press(key)
                log = log or []
                log.append(f"press({key})")
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"press ERROR: {e}")
                return _format_log(log), log

        def on_scroll(direction, amount, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", log
                env._sandbox.scroll(direction=direction, amount=int(amount))
                log = log or []
                log.append(f"scroll({direction}, {int(amount)})")
                return _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"scroll ERROR: {e}")
                return _format_log(log), log

        def on_command(cmd, log):
            env = _get_env()
            try:
                if not env._sandbox:
                    return "Reset first!", "Reset first!", log
                result = env._sandbox.commands.run(cmd, timeout=60)
                output = result.stdout or ""
                if result.exit_code != 0 and result.stderr:
                    output += f"\nSTDERR: {result.stderr}"
                log = log or []
                log.append(f"$ {cmd}")
                return output or "(no output)", _format_log(log), log
            except Exception as e:
                log = log or []
                log.append(f"command ERROR: {e}")
                return str(e), _format_log(log), log

        # ── Wire up events ──
        reset_btn.click(
            on_reset,
            inputs=[app_dropdown, custom_cmd],
            outputs=[status_box, stream_link, action_log_state, action_log, screenshot_img],
        )
        screenshot_btn.click(
            on_screenshot,
            inputs=[action_log_state],
            outputs=[screenshot_img, action_log, action_log_state],
        )
        click_btn.click(
            on_click,
            inputs=[x_input, y_input, action_log_state],
            outputs=[action_log, action_log_state],
        )
        dbl_click_btn.click(
            on_dbl_click,
            inputs=[x_input, y_input, action_log_state],
            outputs=[action_log, action_log_state],
        )
        r_click_btn.click(
            on_right_click,
            inputs=[x_input, y_input, action_log_state],
            outputs=[action_log, action_log_state],
        )
        type_btn.click(
            on_type,
            inputs=[text_input, action_log_state],
            outputs=[action_log, action_log_state],
        )
        key_btn.click(
            on_press_key,
            inputs=[key_input, action_log_state],
            outputs=[action_log, action_log_state],
        )
        scroll_btn.click(
            on_scroll,
            inputs=[scroll_dir, scroll_amt, action_log_state],
            outputs=[action_log, action_log_state],
        )
        cmd_btn.click(
            on_command,
            inputs=[cmd_input, action_log_state],
            outputs=[cmd_output, action_log, action_log_state],
        )

    return demo
