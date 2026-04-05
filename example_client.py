#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


DEVKIT_ROOT = Path(__file__).resolve().parent


def send(proc: subprocess.Popen[str], payload: dict) -> dict:
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


def main() -> int:
    cmd = [
        sys.executable,
        str(DEVKIT_ROOT / "server.py"),
        "--dataset",
        str(DEVKIT_ROOT / "assets/datasets/env_task_set_50_simple_unseen_item.pik"),
        "--exec_path",
        str(DEVKIT_ROOT / "assets/unity/linux_exec.v2.2.5_beta.x86_64"),
        "--base_port",
        "8085",
        "--unity_port_id",
        "5",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=DEVKIT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = proc.stdout.readline()
    print("READY", ready.strip())
    print("RESET", send(proc, {"cmd": "reset", "task_id": 0}))
    print("VALID", send(proc, {"cmd": "valid_actions"}))
    print("OBSERVE", send(proc, {"cmd": "observe"}))
    action = send(proc, {"cmd": "valid_actions"})["result"]["valid_actions"][0]
    print("STEP", send(proc, {"cmd": "step", "action": action}))
    print("CLOSE", send(proc, {"cmd": "close"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
