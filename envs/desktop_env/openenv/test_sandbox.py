"""
Quick test: spin up a LibreOffice Calc sandbox on E2B and take a screenshot.

Usage:
    E2B_API_KEY=e2b_xxx python test_sandbox.py
    # or
    python test_sandbox.py --app libreoffice-calc
    python test_sandbox.py --app blender
    python test_sandbox.py --app firefox
    python test_sandbox.py --app terminal
"""

import argparse
import os
import sys

# Load .env from jupyter agent if E2B_API_KEY not set
if not os.environ.get("E2B_API_KEY"):
    env_file = os.path.join(
        os.path.dirname(__file__),
        "..", "jupyter_agent", "jupyter-agent-openenv", ".env"
    )
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

from sandbox import DesktopSandbox


def main():
    parser = argparse.ArgumentParser(description="Test E2B Desktop Sandbox")
    parser.add_argument("--app", default="libreoffice-calc",
                        help="App preset: libreoffice-calc, libreoffice-writer, firefox, blender, terminal")
    parser.add_argument("--screenshot", default="screenshot.png",
                        help="Path to save screenshot")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Sandbox timeout in seconds")
    args = parser.parse_args()

    print(f"Starting {args.app} sandbox...")

    with DesktopSandbox(app=args.app) as sandbox:
        print(f"\nSandbox is running!")
        print(f"  ID: {sandbox.sandbox_id}")
        print(f"  Stream: {sandbox.stream_url}")
        print(f"\nOpen the stream URL in your browser to view the desktop.")
        print(f"Taking screenshot...")

        img = sandbox.screenshot(save_path=args.screenshot)
        print(f"Screenshot saved: {args.screenshot} ({img.size[0]}x{img.size[1]})")

        print(f"\nSandbox will stay alive for {args.timeout}s.")
        print("Press Ctrl+C to stop early.\n")

        try:
            import time
            time.sleep(args.timeout)
        except KeyboardInterrupt:
            print("\nStopping...")

    print("Done.")


if __name__ == "__main__":
    main()
