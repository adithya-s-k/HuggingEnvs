"""Shared Desktop tasks. Used by every framework variant under desktop_env/."""

TASKS = [
    {
        "task": (
            "Open the Firefox URL bar, navigate to https://example.com, and "
            "confirm the page shows 'Example Domain'."
        ),
        "app": "firefox",
        "resolution": [1024, 768],
        "expected_output": "Example Domain",
    },
    {
        "task": (
            "In xfce4-terminal, type the command `echo hello-rl` and press enter. "
            "Confirm 'hello-rl' is visible."
        ),
        "app": "terminal",
        "resolution": [1024, 768],
        "expected_output": "hello-rl",
    },
    {
        "task": (
            "In LibreOffice Calc: click cell A1, type 23, press Tab, type 45, "
            "press Tab, then type =A1+B1 and press enter. Confirm cell C1 shows 68."
        ),
        "app": "libreoffice-calc",
        "resolution": [1024, 768],
        "expected_output": "68",
    },
]
