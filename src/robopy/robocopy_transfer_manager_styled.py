"""Styled Robocopy Transfer Manager for Windows."""

from __future__ import annotations

import os
import queue
import shlex
import shutil
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
BG = "#020617"
PANEL = "#0f172a"
DARK = "#071020"
FIELD = "#172033"
BORDER = "#273653"
TEXT = "#f8fafc"
MUTED = "#9fb4d0"
CYAN = "#06d7f5"
CYAN_HOVER = "#22e2fa"
TEAL = "#082f35"
TEAL_BORDER = "#0f766e"
TEAL_TEXT = "#45f0d0"
AMBER = "#facc15"
BLACK = "#000000"
DESTRUCTIVE = {"Move files", "Move tree", "Mirror"}


class TransferManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Robocopy Transfer Manager")
        self.geometry("1180x900")
        self.minsize(1000, 760)
        self.configure(fg_color=BG)
        self.process = None
        self.events = queue.Queue()
        self.source = ctk.StringVar(value=r"C:\Work\Source")
        self.destination = ctk.StringVar(value=r"D:\Work\Destination")
        self.operation = ctk.StringVar(value="Copy files and folders")
        self.pattern = ctk.StringVar(value="*.*")
        self.subdirs = ctk.BooleanVar(value=True)
        self.empty_dirs = ctk.BooleanVar(value=True)
        self.restartable = ctk.BooleanVar(value=True)
        self.security = ctk.BooleanVar(value=False)
        self.dry_run = ctk.BooleanVar(value=True)
        self.unbuffered = ctk.BooleanVar(value=False)
        self.threads = ctk.StringVar(value="16")
        self.retries = ctk.StringVar(value="3")
        self.wait = ctk.StringVar(value="5")
        self.exclude_files = ctk.StringVar(value="*.tmp ~*.*")
        self.exclude_dirs = ctk.StringVar(value=".git __pycache__")
        self.command = ctk.StringVar()
        self.status = ctk.StringVar(value="Ready")
        self._build()
        self._bind()
        self._refresh()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _panel(self, parent):
        return ctk.CTkFrame(
            parent, fg_color=PANEL, border_width=1, border_color=BORDER, corner_radius=14
        )

    def _entry(self, parent, var):
        return ctk.CTkEntry(
            parent,
            textvariable=var,
            height=34,
            fg_color=FIELD,
            border_color=BORDER,
            text_color=TEXT,
            font=("Cascadia Mono", 11),
        )

    def _build(self):
        shell = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=1)
        page = ctk.CTkFrame(shell, fg_color="transparent", width=1040)
        page.grid(row=0, column=0, padx=34, pady=(14, 30), sticky="nsew")
        page.grid_columnconfigure(0, weight=5)
        page.grid_columnconfigure(1, weight=3)
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Transfer Manager", font=("Segoe UI", 30, "bold"), text_color=TEXT
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Build safe, repeatable copy, move and mirror jobs with a live command preview and streamed output.",
            font=("Segoe UI", 12),
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w")
        buttons = ctk.CTkFrame(header, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkButton(
            buttons,
            text="↶  Reset",
            width=92,
            height=34,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            hover_color=FIELD,
            command=self._reset,
        ).pack(side="left", padx=(0, 10))
        self.run_button = ctk.CTkButton(
            buttons,
            text="▷  Preview job",
            width=130,
            height=34,
            fg_color=CYAN,
            hover_color=CYAN_HOVER,
            text_color="#001018",
            command=self._start,
        )
        self.run_button.pack(side="left")

        setup = self._panel(page)
        setup.grid(row=1, column=0, sticky="nsew", padx=(0, 9))
        setup.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            setup, text="▱  Transfer setup", font=("Segoe UI", 15, "bold"), text_color=TEXT
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=22, pady=(20, 17))
        self._path_field(setup, "Source path", self.source, 1, 0, self._browse_source)
        self._path_field(
            setup, "Destination path", self.destination, 1, 1, self._browse_destination
        )
        ctk.CTkLabel(
            setup, text="Operation", font=("Segoe UI", 11, "bold"), text_color=TEXT
        ).grid(row=3, column=0, sticky="w", padx=(22, 8), pady=(12, 4))
        ctk.CTkOptionMenu(
            setup,
            variable=self.operation,
            values=["Copy files and folders", "Move files", "Move tree", "Mirror"],
            fg_color=FIELD,
            button_color=FIELD,
            button_hover_color=BORDER,
            text_color=TEXT,
            dropdown_fg_color=FIELD,
            command=lambda _: self._refresh(),
            height=34,
        ).grid(row=4, column=0, sticky="ew", padx=(22, 8))
        ctk.CTkLabel(
            setup, text="File pattern", font=("Segoe UI", 11, "bold"), text_color=TEXT
        ).grid(row=3, column=1, sticky="w", padx=(8, 22), pady=(12, 4))
        self._entry(setup, self.pattern).grid(row=4, column=1, sticky="ew", padx=(8, 22))
        tabs = ctk.CTkTabview(
            setup,
            fg_color="transparent",
            segmented_button_fg_color=DARK,
            segmented_button_selected_color=FIELD,
            segmented_button_selected_hover_color=FIELD,
            segmented_button_unselected_color=DARK,
            segmented_button_unselected_hover_color=FIELD,
            text_color=TEXT,
            height=190,
        )
        tabs.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(15, 14))
        common = tabs.add("Common")
        perf = tabs.add("Performance")
        filters = tabs.add("Filters")
        common.grid_columnconfigure((0, 1), weight=1)
        for i, (label, var) in enumerate(
            [
                ("Include subdirectories", self.subdirs),
                ("Include empty directories", self.empty_dirs),
                ("Restart interrupted copies", self.restartable),
                ("Preserve ACLs and ownership", self.security),
                ("Dry run, change nothing", self.dry_run),
                ("Unbuffered I/O for large files", self.unbuffered),
            ]
        ):
            box = ctk.CTkFrame(
                common, fg_color=DARK, border_width=1, border_color=BORDER, corner_radius=11
            )
            box.grid(row=i // 2, column=i % 2, sticky="ew", padx=5, pady=5)
            ctk.CTkCheckBox(
                box,
                text=label,
                variable=var,
                fg_color=CYAN,
                hover_color=CYAN_HOVER,
                border_color=BORDER,
                text_color=TEXT,
                font=("Segoe UI", 11),
                command=self._refresh,
            ).pack(anchor="w", padx=11, pady=10)
        perf.grid_columnconfigure((0, 1, 2), weight=1)
        for col, (label, var) in enumerate(
            [
                ("Threads, 1 to 128", self.threads),
                ("Retries", self.retries),
                ("Wait between retries, sec", self.wait),
            ]
        ):
            ctk.CTkLabel(
                perf, text=label, text_color=TEXT, font=("Segoe UI", 11, "bold")
            ).grid(row=0, column=col, sticky="w", padx=7, pady=(12, 4))
            self._entry(perf, var).grid(row=1, column=col, sticky="ew", padx=7)
        filters.grid_columnconfigure(0, weight=1)
        for row, (label, var) in enumerate(
            [
                ("Exclude files, space separated", self.exclude_files),
                ("Exclude directories, space separated", self.exclude_dirs),
            ]
        ):
            ctk.CTkLabel(
                filters, text=label, text_color=TEXT, font=("Segoe UI", 11, "bold")
            ).grid(row=row * 2, column=0, sticky="w", padx=7, pady=(8, 4))
            self._entry(filters, var).grid(row=row * 2 + 1, column=0, sticky="ew", padx=7)

        safety = self._panel(page)
        safety.grid(row=1, column=1, sticky="nsew", padx=(9, 0))
        ctk.CTkLabel(
            safety, text="Safety and status", font=("Segoe UI", 15, "bold"), text_color=TEXT
        ).pack(anchor="w", padx=22, pady=(20, 20))
        self._info(
            safety,
            "◉  Recommended defaults",
            "Restartable mode, 16 threads, 3 retries, 5 second wait and a dry run before execution.",
            TEAL,
            TEAL_BORDER,
            TEAL_TEXT,
        )
        self._info(
            safety,
            "⚠  Exit-code handling",
            "Robocopy codes 0 to 7 are non-fatal; 8 or above indicates failure.",
            DARK,
            BORDER,
            AMBER,
        )
        self._info(
            safety,
            "Archive note",
            "A ZIP can be selected as a single source file. Robocopy copies the archive itself; it does not extract it.",
            DARK,
            BORDER,
            TEXT,
        )
        self.danger = ctk.CTkLabel(
            safety,
            text="",
            wraplength=300,
            justify="left",
            font=("Segoe UI", 11, "bold"),
            text_color="#f59e0b",
        )
        self.danger.pack(anchor="w", padx=22, pady=(4, 18))

        cmd = self._panel(page)
        cmd.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        cmd.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cmd, text="Generated CMD command", font=("Segoe UI", 15, "bold"), text_color=TEXT
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(20, 7))
        ctk.CTkButton(
            cmd,
            text="▣  Copy",
            width=130,
            height=30,
            fg_color=FIELD,
            hover_color=BORDER,
            border_width=1,
            border_color=BORDER,
            command=self._copy,
        ).grid(row=1, column=0, sticky="w", padx=22)
        self.command_box = ctk.CTkTextbox(
            cmd,
            height=54,
            fg_color=BLACK,
            border_width=1,
            border_color=BORDER,
            corner_radius=11,
            text_color="#67f6ff",
            font=("Cascadia Mono", 11),
            wrap="none",
        )
        self.command_box.grid(row=2, column=0, sticky="ew", padx=22, pady=(16, 20))
        out = self._panel(page)
        out.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        out.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            out, text="Live output", font=("Segoe UI", 15, "bold"), text_color=TEXT
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(20, 10))
        self.output = ctk.CTkTextbox(
            out,
            height=210,
            fg_color=BLACK,
            border_width=1,
            border_color=BORDER,
            corner_radius=11,
            text_color="#dbeafe",
            font=("Cascadia Mono", 11),
            wrap="none",
        )
        self.output.grid(row=1, column=0, sticky="nsew", padx=22)
        self.output.insert(
            "end",
            "Ready. Review the generated command before running it.\nDry run is enabled by default.\n",
        )
        footer = ctk.CTkFrame(out, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=22, pady=(10, 17))
        ctk.CTkLabel(footer, textvariable=self.status, text_color=MUTED).pack(side="left")
        ctk.CTkButton(
            footer,
            text="Clear output",
            width=100,
            fg_color=FIELD,
            hover_color=BORDER,
            command=lambda: self.output.delete("1.0", "end"),
        ).pack(side="right")
        self.cancel_button = ctk.CTkButton(
            footer,
            text="Cancel",
            width=85,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            state="disabled",
            command=self._cancel,
        )
        self.cancel_button.pack(side="right", padx=8)

    def _path_field(self, parent, label, var, row, col, browse):
        pad = (22, 8) if col == 0 else (8, 22)
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11, "bold"), text_color=TEXT).grid(
            row=row, column=col, sticky="w", padx=pad
        )
        h = ctk.CTkFrame(parent, fg_color="transparent")
        h.grid(row=row + 1, column=col, sticky="ew", padx=pad, pady=(4, 0))
        h.grid_columnconfigure(0, weight=1)
        self._entry(h, var).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            h,
            text="…",
            width=36,
            height=34,
            fg_color=FIELD,
            hover_color=BORDER,
            border_width=1,
            border_color=BORDER,
            command=browse,
        ).grid(row=0, column=1, padx=(6, 0))

    def _info(self, parent, title, body, color, border, title_color):
        box = ctk.CTkFrame(
            parent, fg_color=color, border_width=1, border_color=border, corner_radius=12
        )
        box.pack(fill="x", padx=22, pady=(0, 14))
        ctk.CTkLabel(
            box, text=title, text_color=title_color, font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=14, pady=(13, 5))
        ctk.CTkLabel(
            box,
            text=body,
            wraplength=310,
            justify="left",
            text_color="#c9dcf4",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=14, pady=(0, 14))

    def _bind(self):
        for v in (
            self.source,
            self.destination,
            self.pattern,
            self.subdirs,
            self.empty_dirs,
            self.restartable,
            self.security,
            self.dry_run,
            self.unbuffered,
            self.threads,
            self.retries,
            self.wait,
            self.exclude_files,
            self.exclude_dirs,
        ):
            v.trace_add("write", lambda *_: self._refresh())

    def _normalised_source(self):
        source = Path(self.source.get().strip())
        pattern = self.pattern.get().strip() or "*.*"
        return (
            (source.parent, source.name, True)
            if source.is_file()
            else (source, pattern, False)
        )

    def _browse_source(self):
        file_mode = messagebox.askyesnocancel(
            "Select source type",
            "Yes: select one file, including a ZIP.\n\nNo: select a folder.\n\nCancel: return.",
        )
        if file_mode is None:
            return
        if file_mode:
            selected = filedialog.askopenfilename(
                title="Select source file",
                filetypes=[
                    ("All files", "*.*"),
                    ("ZIP archives", "*.zip"),
                    ("CSV files", "*.csv"),
                ],
            )
            if selected:
                self.source.set(selected)
                self.pattern.set(Path(selected).name)
        else:
            selected = filedialog.askdirectory(title="Select source folder")
            if selected:
                self.source.set(selected)
                self.pattern.set("*.*")

    def _browse_destination(self):
        selected = filedialog.askdirectory(title="Select destination folder")
        if selected:
            self.destination.set(selected)

    @staticmethod
    def _num(var, default, low, high):
        try:
            value = int(var.get())
        except ValueError:
            value = default
        return min(max(value, low), high)

    def _args(self):
        source, pattern, single = self._normalised_source()
        args = ["robocopy", str(source), self.destination.get().strip(), pattern]
        op = self.operation.get()
        if op == "Mirror":
            args.append("/MIR")
        elif self.subdirs.get() and not single:
            args.append("/E" if self.empty_dirs.get() else "/S")
        if op == "Move files":
            args.append("/MOV")
        elif op == "Move tree":
            args.append("/MOVE")
        if self.restartable.get():
            args.append("/Z")
        if self.unbuffered.get():
            args.append("/J")
        if self.security.get():
            args.extend(["/COPYALL", "/DCOPY:DAT"])
        args.extend(
            [
                f"/MT:{self._num(self.threads, 16, 1, 128)}",
                f"/R:{self._num(self.retries, 3, 0, 1000)}",
                f"/W:{self._num(self.wait, 5, 0, 3600)}",
            ]
        )
        if self.exclude_files.get().strip():
            args.extend(["/XF", *shlex.split(self.exclude_files.get(), posix=False)])
        if self.exclude_dirs.get().strip() and not single:
            args.extend(["/XD", *shlex.split(self.exclude_dirs.get(), posix=False)])
        args.extend(["/ETA", "/BYTES"])
        if self.dry_run.get():
            args.append("/L")
        return args

    def _refresh(self):
        command = subprocess.list2cmdline(self._args())
        self.command.set(command)
        if hasattr(self, "command_box"):
            self.command_box.delete("1.0", "end")
            self.command_box.insert("1.0", command)
        if hasattr(self, "run_button"):
            self.run_button.configure(
                text="▷  Preview job" if self.dry_run.get() else "▷  Run job"
            )
        if hasattr(self, "danger"):
            self.danger.configure(
                text="⚠ Destructive mode selected. Preview first."
                if self.operation.get() in DESTRUCTIVE
                else ""
            )

    def _validate(self):
        if os.name != "nt" or shutil.which("robocopy") is None:
            messagebox.showerror(
                "Robocopy unavailable", "Windows and robocopy.exe are required."
            )
            return False
        raw = Path(self.source.get().strip())
        dst_text = self.destination.get().strip()
        if not raw.exists():
            messagebox.showwarning("Invalid source", f"The source does not exist:\n{raw}")
            return False
        if not dst_text:
            messagebox.showwarning("Invalid destination", "Choose a destination folder.")
            return False
        src, _, single = self._normalised_source()
        dst = Path(dst_text)
        if self.operation.get() == "Mirror" and single:
            messagebox.showwarning(
                "Invalid operation", "Mirror requires a source folder, not one file."
            )
            return False
        try:
            if src.resolve() == dst.resolve():
                messagebox.showwarning(
                    "Invalid destination", "Source and destination must differ."
                )
                return False
            if not single and src.resolve() in dst.resolve().parents:
                messagebox.showwarning(
                    "Unsafe destination", "Destination cannot be inside the source folder."
                )
                return False
        except OSError:
            pass
        if not self.dry_run.get() and self.operation.get() in DESTRUCTIVE:
            return messagebox.askyesno(
                "Confirm destructive job",
                "This job can delete files. Continue with the live run?",
            )
        return True

    def _start(self):
        if self.process is not None or not self._validate():
            return
        args = self._args()
        self.output.insert("end", f"\n> {subprocess.list2cmdline(args)}\n\n")
        self.output.see("end")
        self.status.set("Running preview..." if self.dry_run.get() else "Running...")
        self.run_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        threading.Thread(target=self._worker, args=(args,), daemon=True).start()

    def _worker(self, args):
        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in self.process.stdout or ():
                self.events.put(("line", line))
            self.events.put(("done", self.process.wait()))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.process = None

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self.output.insert("end", str(value))
                    self.output.see("end")
                elif kind == "done":
                    code = int(value)
                    self.status.set(
                        f"Completed, exit code {code}."
                        if code <= 7
                        else f"Failed, exit code {code}."
                    )
                    self._idle()
                    if code > 7:
                        messagebox.showerror(
                            "Robocopy failed", f"Robocopy returned exit code {code}."
                        )
                else:
                    self.status.set("Execution failed.")
                    self._idle()
                    messagebox.showerror("Execution error", str(value))
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _idle(self):
        self.run_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _cancel(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status.set("Cancellation requested...")

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.command.get())
        self.status.set("Command copied.")

    def _reset(self):
        self.operation.set("Copy files and folders")
        self.pattern.set("*.*")
        self.subdirs.set(True)
        self.empty_dirs.set(True)
        self.restartable.set(True)
        self.security.set(False)
        self.dry_run.set(True)
        self.unbuffered.set(False)
        self.threads.set("16")
        self.retries.set("3")
        self.wait.set("5")
        self.exclude_files.set("*.tmp ~*.*")
        self.exclude_dirs.set(".git __pycache__")
        self.status.set("Settings reset.")

    def _close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Job running", "Cancel the active job and close?"):
                return
            self.process.terminate()
        self.destroy()


if __name__ == "__main__":
    TransferManager().mainloop()
