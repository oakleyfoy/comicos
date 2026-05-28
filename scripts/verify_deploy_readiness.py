from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CRITICAL_PREFIXES = (
    "apps/api/app/",
    "apps/api/alembic/versions/",
    "apps/api/tests/",
    "apps/web/src/",
    ".github/workflows/",
    "scripts/",
)
CRITICAL_FILES = {
    ".gitignore",
    "package.json",
    "apps/api/pyproject.toml",
    "apps/web/package.json",
}


def run(command: list[str], *, cwd: Path | None = None) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"\n==> {printable}")
    executable = shutil.which(command[0])
    if executable is None and sys.platform == "win32":
        executable = shutil.which(f"{command[0]}.cmd")
    if executable is None:
        print(f"Unable to find executable: {command[0]}")
        raise SystemExit(1)
    completed = subprocess.run([executable, *command[1:]], cwd=cwd or REPO_ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def normalized_git_paths(command: list[str]) -> list[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def is_critical_untracked(path: str) -> bool:
    if path in CRITICAL_FILES:
        return True
    return any(path.startswith(prefix) for prefix in CRITICAL_PREFIXES)


def verify_no_untracked_source_files() -> None:
    untracked = normalized_git_paths(["git", "ls-files", "--others", "--exclude-standard"])
    offenders = sorted(path for path in untracked if is_critical_untracked(path))
    if offenders:
        print("\nFound untracked source files in deploy-critical paths:")
        for path in offenders:
            print(f" - {path}")
        print(
            "\nCommit, remove, or intentionally ignore these files before pushing so "
            "Render and CI see the same source tree you tested locally."
        )
        raise SystemExit(1)


def verify_api_import() -> None:
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(REPO_ROOT / 'apps' / 'api')!r}); "
        "import app.main; "
        "print('api-import-ok')"
    )
    run([sys.executable, "-c", code], cwd=REPO_ROOT)


def verify_web_build() -> None:
    web_root = REPO_ROOT / "apps" / "web"
    typescript_bin = REPO_ROOT / "node_modules" / "typescript" / "bin" / "tsc"
    vite_bin = REPO_ROOT / "node_modules" / "vite" / "bin" / "vite.js"
    run(["node", str(typescript_bin), "-b"], cwd=web_root)
    run(["node", str(vite_bin), "build"], cwd=web_root)


def main() -> None:
    print("Running deploy readiness checks...")
    verify_no_untracked_source_files()
    verify_api_import()
    verify_web_build()
    print("\nDeploy readiness checks passed.")


if __name__ == "__main__":
    main()
