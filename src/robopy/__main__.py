"""Python launcher for the styled Robocopy Transfer Manager.

Place this file beside robocopy_transfer_manager_styled.py, then run:
    py launch_robocopy_manager.py

The launcher installs CustomTkinter into the active Python environment if it is
missing, then starts the main application with the same Python interpreter.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

APP_FILE = "robocopy_transfer_manager_styled.py"
DEPENDENCY = "customtkinter>=5.2,<6"


def ensure_dependency() -> None:
    if importlib.util.find_spec("customtkinter") is not None:
        return

    print("CustomTkinter is not installed. Installing it now...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", DEPENDENCY],
        check=True,
    )


def launch_app() -> int:
    launcher_dir = Path(__file__).resolve().parent
    app_path = launcher_dir / APP_FILE

    if not app_path.is_file():
        raise FileNotFoundError(
            f"Could not find {APP_FILE}. Place both Python files in the same folder."
        )

    completed = subprocess.run(
        [sys.executable, str(app_path)],
        cwd=launcher_dir,
        check=False,
    )
    return completed.returncode


def main() -> None:
    try:
        ensure_dependency()
        return_code = launch_app()
    except subprocess.CalledProcessError as exc:
        print(f"Dependency installation failed with exit code {exc.returncode}.")
        input("Press Enter to close...")
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        print(f"Unable to launch the application: {exc}")
        input("Press Enter to close...")
        raise SystemExit(1) from exc

    if return_code != 0:
        print(f"The application closed with exit code {return_code}.")
        input("Press Enter to close...")
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
