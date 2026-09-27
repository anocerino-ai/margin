"""Start API, queue worker and Vue locally. Ctrl-C stops all child processes."""

import os
import signal
import subprocess
import sys
import time

from margin.config import ROOT


def main():
    commands = [
        [sys.executable, "-m", "uvicorn", "margin.api.app:app", "--host", "127.0.0.1", "--port", "8000"],
        [sys.executable, "-m", "margin.jobs.worker"],
        ["npm", "run", "dev", "-w", "apps/web", "--", "--port", "5173", "--strictPort"],
    ]
    children = []
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, start_new_session=True))
        print("Margin: http://127.0.0.1:5173 — Ctrl-C to stop", flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in children:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
        for p in children:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
