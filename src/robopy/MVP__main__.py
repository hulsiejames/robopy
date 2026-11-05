"""Robocopy Transfer Manager for Windows.

A Tkinter GUI that builds and runs Robocopy jobs, streams output into the GUI,
and supports copy, move, mirror, filters, dry runs, cancellation and command preview.
"""

from __future__ import annotations

# # # # IMPORTS # # # #
# Built-Ins
import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# # # # CONSTANTS # # # #
ROBOCOPY_SUCCESS_MAX = 7
DESTRUCTIVE_OPERATIONS = {"Move files", "Move tree", "Mirror"}


# # # # CLASSES # # # #
class RobocopyApp(tk.Tk):
    """Tkinter application for building and running Robocopy jobs."""

    def __init__(self) -> None:
        """Initialize application state, widgets, and background polling."""
        super().__init__()
        self.title("Robocopy Transfer Manager")
        self.geometry("1100x780")
        self.minsize(900, 650)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        self.operation = tk.StringVar(value="Copy")
        self.pattern = tk.StringVar(value="*.*")
        self.include_subdirs = tk.BooleanVar(value=True)
        self.include_empty = tk.BooleanVar(value=True)
        self.restartable = tk.BooleanVar(value=True)
        self.unbuffered = tk.BooleanVar(value=False)
        self.copy_security = tk.BooleanVar(value=False)
        self.dry_run = tk.BooleanVar(value=True)
        self.threads = tk.IntVar(value=16)
        self.retries = tk.IntVar(value=3)
        self.wait_seconds = tk.IntVar(value=5)
        self.exclude_files = tk.StringVar(value="*.tmp ~*.*")
        self.exclude_dirs = tk.StringVar(value=".git __pycache__")
        self.status = tk.StringVar(value="Ready")
        self.command_preview = tk.StringVar()

        self._build_ui()
        self._bind_updates()
        self._refresh_command()
        self.after(100, self._drain_output_queue)

    def _build_ui(self) -> None:
        """Construct and lay out all UI controls."""
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="Robocopy Transfer Manager", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        paths = ttk.LabelFrame(outer, text="Paths", padding=10)
        paths.grid(row=1, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)

        ttk.Label(paths, text="Source").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(paths, textvariable=self.source).grid(row=0, column=1, sticky="ew")
        ttk.Button(paths, text="Browse...", command=self._browse_source).grid(
            row=0, column=2, padx=(8, 0)
        )

        ttk.Label(paths, text="Destination").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0)
        )
        ttk.Entry(paths, textvariable=self.destination).grid(
            row=1, column=1, sticky="ew", pady=(8, 0)
        )
        ttk.Button(paths, text="Browse...", command=self._browse_destination).grid(
            row=1, column=2, padx=(8, 0), pady=(8, 0)
        )

        options = ttk.LabelFrame(outer, text="Transfer options", padding=10)
        options.grid(row=2, column=0, sticky="ew", pady=10)
        for col in range(6):
            options.columnconfigure(col, weight=1)

        ttk.Label(options, text="Operation").grid(row=0, column=0, sticky="w")
        operation_box = ttk.Combobox(
            options,
            textvariable=self.operation,
            values=("Copy", "Move files", "Move tree", "Mirror"),
            state="readonly",
            width=16,
        )
        operation_box.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(options, text="File pattern").grid(row=0, column=1, sticky="w")
        ttk.Entry(options, textvariable=self.pattern).grid(
            row=1, column=1, sticky="ew", padx=(0, 8)
        )

        ttk.Label(options, text="Threads (1-128)").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(options, from_=1, to=128, textvariable=self.threads).grid(
            row=1, column=2, sticky="ew", padx=(0, 8)
        )

        ttk.Label(options, text="Retries").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(options, from_=0, to=1000, textvariable=self.retries).grid(
            row=1, column=3, sticky="ew", padx=(0, 8)
        )

        ttk.Label(options, text="Wait seconds").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(options, from_=0, to=3600, textvariable=self.wait_seconds).grid(
            row=1, column=4, sticky="ew", padx=(0, 8)
        )

        ttk.Checkbutton(options, text="Dry run (/L)", variable=self.dry_run).grid(
            row=1, column=5, sticky="w"
        )

        checks = ttk.Frame(options)
        checks.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(checks, text="Subdirectories", variable=self.include_subdirs).pack(
            side="left", padx=(0, 15)
        )
        ttk.Checkbutton(checks, text="Include empty dirs", variable=self.include_empty).pack(
            side="left", padx=(0, 15)
        )
        ttk.Checkbutton(checks, text="Restartable (/Z)", variable=self.restartable).pack(
            side="left", padx=(0, 15)
        )
        ttk.Checkbutton(checks, text="Unbuffered (/J)", variable=self.unbuffered).pack(
            side="left", padx=(0, 15)
        )
        ttk.Checkbutton(
            checks, text="Copy security (/COPYALL)", variable=self.copy_security
        ).pack(side="left")

        ttk.Label(options, text="Exclude files (space separated)").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        ttk.Entry(options, textvariable=self.exclude_files).grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=(0, 8)
        )
        ttk.Label(options, text="Exclude directories (space separated)").grid(
            row=3, column=3, columnspan=2, sticky="w", pady=(10, 0)
        )
        ttk.Entry(options, textvariable=self.exclude_dirs).grid(
            row=4, column=3, columnspan=3, sticky="ew"
        )

        command_frame = ttk.LabelFrame(outer, text="Generated CMD command", padding=10)
        command_frame.grid(row=3, column=0, sticky="ew")
        command_frame.columnconfigure(0, weight=1)
        command_entry = ttk.Entry(
            command_frame, textvariable=self.command_preview, state="readonly"
        )
        command_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(command_frame, text="Copy command", command=self._copy_command).grid(
            row=0, column=1, padx=(8, 0)
        )

        output_frame = ttk.LabelFrame(outer, text="Robocopy output", padding=10)
        output_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(
            output_frame, wrap="none", font=("Consolas", 9), state="disabled"
        )
        y_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.output.yview)
        x_scroll = ttk.Scrollbar(output_frame, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.output.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        controls = ttk.Frame(outer)
        controls.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(controls, textvariable=self.status).pack(side="left")
        self.clear_button = ttk.Button(
            controls, text="Clear output", command=self._clear_output
        )
        self.clear_button.pack(side="right")
        self.cancel_button = ttk.Button(
            controls, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_button.pack(side="right", padx=8)
        self.run_button = ttk.Button(controls, text="Preview", command=self._start)
        self.run_button.pack(side="right")

    def _bind_updates(self) -> None:
        """Bind variable changes to command preview refresh."""
        variables = (
            self.source,
            self.destination,
            self.operation,
            self.pattern,
            self.include_subdirs,
            self.include_empty,
            self.restartable,
            self.unbuffered,
            self.copy_security,
            self.dry_run,
            self.threads,
            self.retries,
            self.wait_seconds,
            self.exclude_files,
            self.exclude_dirs,
        )
        for variable in variables:
            variable.trace_add("write", lambda *_: self._refresh_command())

    def _browse_source(self) -> None:
        """Prompt for a source directory and update the bound value."""
        selected = filedialog.askdirectory(title="Select source folder")
        if selected:
            self.source.set(selected)

    def _browse_destination(self) -> None:
        """Prompt for a destination directory and update the bound value."""
        selected = filedialog.askdirectory(title="Select destination folder")
        if selected:
            self.destination.set(selected)

    @staticmethod
    def _split_filters(value: str) -> list[str]:
        """Split whitespace-delimited filter text into individual tokens."""
        # Simple whitespace-separated filters. Paths containing spaces should be selected
        # through the main path fields rather than entered here.
        return value.split()

    def _build_args(self) -> list[str]:
        """Build the robocopy command arguments from current UI options."""
        args = [
            "robocopy",
            self.source.get().strip(),
            self.destination.get().strip(),
            self.pattern.get().strip() or "*.*",
        ]

        operation = self.operation.get()
        if operation == "Mirror":
            args.append("/MIR")
        elif self.include_subdirs.get():
            args.append("/E" if self.include_empty.get() else "/S")

        if operation == "Move files":
            args.append("/MOV")
        elif operation == "Move tree":
            args.append("/MOVE")

        if self.restartable.get():
            args.append("/Z")
        if self.unbuffered.get():
            args.append("/J")
        if self.copy_security.get():
            args.extend(("/COPYALL", "/DCOPY:DAT"))

        threads = max(1, min(128, self._safe_int(self.threads, 16)))
        retries = max(0, self._safe_int(self.retries, 3))
        wait = max(0, self._safe_int(self.wait_seconds, 5))
        args.extend((f"/MT:{threads}", f"/R:{retries}", f"/W:{wait}"))

        excluded_files = self._split_filters(self.exclude_files.get())
        if excluded_files:
            args.extend(("/XF", *excluded_files))
        excluded_dirs = self._split_filters(self.exclude_dirs.get())
        if excluded_dirs:
            args.extend(("/XD", *excluded_dirs))

        # /TEE is omitted because stdout is already captured and shown in the GUI.
        args.extend(("/ETA", "/BYTES"))
        if self.dry_run.get():
            args.append("/L")
        return args

    @staticmethod
    def _safe_int(variable: tk.IntVar, default: int) -> int:
        """Return a safe integer from a Tk variable, or a default fallback."""
        try:
            return int(variable.get())
        except (tk.TclError, ValueError):
            return default

    def _refresh_command(self) -> None:
        """Refresh the command preview and run button label."""
        try:
            args = self._build_args()
            self.command_preview.set(subprocess.list2cmdline(args))
            self.run_button.configure(text="Preview" if self.dry_run.get() else "Run")
        except tk.TclError:
            pass

    def _validate(self) -> bool:
        """Validate paths and options before running a job."""
        if shutil.which("robocopy") is None:
            messagebox.showerror(
                "Robocopy not found",
                "robocopy.exe was not found on PATH. This app must run on Windows.",
            )
            return False

        source_text = self.source.get().strip()
        destination_text = self.destination.get().strip()
        if not source_text or not destination_text:
            messagebox.showwarning(
                "Missing path", "Choose both a source and destination folder."
            )
            return False

        source = Path(source_text)
        if not source.is_dir():
            messagebox.showwarning(
                "Invalid source", f"The source folder does not exist:\n{source}"
            )
            return False

        try:
            source_resolved = source.resolve()
            destination_resolved = Path(destination_text).resolve()
            if source_resolved == destination_resolved:
                messagebox.showwarning(
                    "Same path", "Source and destination must be different."
                )
                return False
            if source_resolved in destination_resolved.parents:
                messagebox.showwarning(
                    "Unsafe destination", "The destination cannot be inside the source folder."
                )
                return False
        except OSError:
            pass

        if not self.dry_run.get() and self.operation.get() in DESTRUCTIVE_OPERATIONS:
            detail = (
                "Mirror can delete destination items not present in the source."
                if self.operation.get() == "Mirror"
                else "Move deletes source items after successful copying."
            )
            if not messagebox.askyesno(
                "Confirm destructive operation", f"{detail}\n\nContinue with the live run?"
            ):
                return False
        return True

    def _start(self) -> None:
        """Start a robocopy run in a background worker thread."""
        if self.process is not None or not self._validate():
            return
        args = self._build_args()
        self._append_output("\n> " + subprocess.list2cmdline(args) + "\n\n")
        self.status.set("Running dry-run preview..." if self.dry_run.get() else "Running...")
        self.run_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        threading.Thread(target=self._worker, args=(args,), daemon=True).start()

    def _worker(self, args: list[str]) -> None:
        """Execute robocopy and stream process output through a queue."""
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
            assert self.process.stdout is not None
            for line in iter(self.process.stdout.readline, ""):
                self.output_queue.put(("line", line))
            return_code = self.process.wait()
            self.output_queue.put(("done", return_code))
        except Exception as exc:
            self.output_queue.put(("error", str(exc)))
        finally:
            self.process = None

    def _drain_output_queue(self) -> None:
        """Handle queued output, completion, and error events on the UI thread."""
        try:
            while True:
                kind, value = self.output_queue.get_nowait()
                if kind == "line":
                    self._append_output(str(value))
                elif kind == "done":
                    code = int(value)
                    if code <= ROBOCOPY_SUCCESS_MAX:
                        self.status.set(f"Completed. Robocopy exit code {code} (non-fatal).")
                    else:
                        self.status.set(f"Failed. Robocopy exit code {code}.")
                        messagebox.showerror(
                            "Robocopy failed",
                            f"Robocopy returned exit code {code}. Review the output.",
                        )
                    self._set_idle()
                elif kind == "error":
                    self.status.set("Could not start Robocopy.")
                    messagebox.showerror("Execution error", str(value))
                    self._set_idle()
        except queue.Empty:
            pass
        self.after(100, self._drain_output_queue)

    def _cancel(self) -> None:
        """Request termination of the active robocopy process."""
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            self.status.set("Cancellation requested...")

    def _set_idle(self) -> None:
        """Restore idle UI state after a run completes or fails."""
        self.run_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _copy_command(self) -> None:
        """Copy the generated robocopy command to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.command_preview.get())
        self.status.set("Command copied to clipboard.")

    def _append_output(self, text: str) -> None:
        """Append text to the output pane and keep the view scrolled."""
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self) -> None:
        """Clear all text from the output pane."""
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")


def main() -> None:
    """Launch the GUI on Windows systems."""
    if os.name != "nt":
        raise SystemExit("This application requires Windows because it uses robocopy.exe.")
    app = RobocopyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
