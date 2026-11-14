"""Validate the project version and identify a main-branch release."""

import json
import os
import re
import subprocess
from pathlib import Path


def parse(text):
    version = text.strip()
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise SystemExit("VERSION must contain a version such as 1.2.3")
    return version, tuple(map(int, version.split(".")))


def previous_version(commit):
    if not commit or commit == "0" * 40:
        return None
    exists = subprocess.check_output(["git", "ls-tree", "--name-only", commit, "--", "VERSION"], text=True)
    if not exists.strip():
        return None
    return parse(subprocess.check_output(["git", "show", f"{commit}:VERSION"], text=True))[1]


def main():
    version, current = parse(Path("VERSION").read_text(encoding="utf-8"))
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    main_push = os.environ["GITHUB_EVENT_NAME"] == "push" and os.environ["GITHUB_REF"] == "refs/heads/main"
    previous = previous_version(event.get("before")) if main_push else None
    if "pull_request" in event and event["pull_request"]["base"]["ref"] == "main":
        previous = previous_version(event["pull_request"]["base"]["sha"])
    if previous is not None and current < previous:
        raise SystemExit("VERSION cannot decrease on main")
    eligible = main_push and previous is not None and current > previous
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"version={version}", file=output)
        print(f"publish={str(eligible).lower()}", file=output)


if __name__ == "__main__":
    main()
