"""Initial Desktop tasks. Expand as graders are added.

Each task spec carries:
  - app: APP_PRESETS key or raw launch command
  - resolution: [w, h]
  - instruction: the user-facing task to drive `get_prompt`
  - (optional) grader_command: shell command run at terminate time to score
"""

TASKS = [
    {
        "app": "firefox",
        "resolution": [1024, 768],
        "instruction": (
            "Open the Firefox URL bar, navigate to https://example.com, and confirm "
            "the page shows 'Example Domain'. Call terminate(status='success') once "
            "you can read 'Example Domain' on the screen."
        ),
        "grader_command": None,
    },
    {
        "app": "terminal",
        "resolution": [1024, 768],
        "instruction": (
            "Open xfce4-terminal (it should already be focused), then type the "
            "command `echo 'hello-rl'` and press enter. After 'hello-rl' is "
            "visible in the terminal output, call terminate(status='success')."
        ),
        "grader_command": None,
    },
    {
        "app": "libreoffice-calc",
        "resolution": [1024, 768],
        "instruction": (
            "In LibreOffice Calc: click cell A1 and type 23, press Tab, type 45, "
            "press Tab, then type =A1+B1 and press enter. Confirm cell C1 shows 68 "
            "before calling terminate(status='success')."
        ),
        "grader_command": None,
    },
]
