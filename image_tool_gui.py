#!/usr/bin/env python3
"""
Simple GUI wrapper for image_tool.py.
"""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except ImportError:
    BaseTk = tk.Tk
    DND_AVAILABLE = False


class ImageToolGUI(BaseTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Image Lossless Tool")
        self.geometry("760x520")
        self.minsize(720, 480)

        self.script_path = Path(__file__).with_name("image_tool.py")

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.mode = tk.StringVar(value="compress")
        self.target_format = tk.StringVar(value="png")

        self.recursive = tk.BooleanVar(value=True)
        self.overwrite = tk.BooleanVar(value=False)
        self.keep_when_larger = tk.BooleanVar(value=False)
        self.allow_lossy = tk.BooleanVar(value=False)
        self.input_batch_files: list[str] = []

        self._build_ui()
        self._refresh_mode_controls()
        self._bind_drag_and_drop()

        if DND_AVAILABLE:
            self._append_log("Drag & drop enabled: drop file/folder on Input or Output field.")
        else:
            self._append_log(
                "Drag & drop unavailable. Install dependency: pip install tkinterdnd2"
            )

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=12, pady=12)

        # Path section
        path_frame = ttk.LabelFrame(root, text="Paths")
        path_frame.pack(fill="x")

        ttk.Label(path_frame, text="Input:").grid(row=0, column=0, sticky="w", **pad)
        self.input_entry = ttk.Entry(path_frame, textvariable=self.input_path)
        self.input_entry.grid(
            row=0, column=1, sticky="ew", **pad
        )
        ttk.Button(path_frame, text="File", command=self._pick_input_file).grid(
            row=0, column=2, sticky="ew", **pad
        )
        ttk.Button(path_frame, text="Folder", command=self._pick_input_dir).grid(
            row=0, column=3, sticky="ew", **pad
        )

        ttk.Label(path_frame, text="Output:").grid(row=1, column=0, sticky="w", **pad)
        self.output_entry = ttk.Entry(path_frame, textvariable=self.output_path)
        self.output_entry.grid(
            row=1, column=1, sticky="ew", **pad
        )
        ttk.Button(path_frame, text="Folder", command=self._pick_output_dir).grid(
            row=1, column=2, sticky="ew", **pad
        )

        path_frame.columnconfigure(1, weight=1)

        # Mode section
        mode_frame = ttk.LabelFrame(root, text="Mode")
        mode_frame.pack(fill="x", pady=10)

        ttk.Radiobutton(
            mode_frame,
            text="Lossless Compress",
            value="compress",
            variable=self.mode,
            command=self._refresh_mode_controls,
        ).grid(row=0, column=0, sticky="w", **pad)
        ttk.Radiobutton(
            mode_frame,
            text="Format Convert",
            value="convert",
            variable=self.mode,
            command=self._refresh_mode_controls,
        ).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(mode_frame, text="Target Format:").grid(
            row=1, column=0, sticky="w", **pad
        )
        self.format_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.target_format,
            values=["png", "jpeg", "webp", "tiff", "bmp", "gif"],
            state="readonly",
            width=10,
        )
        self.format_combo.grid(row=1, column=1, sticky="w", **pad)

        # Options section
        options_frame = ttk.LabelFrame(root, text="Options")
        options_frame.pack(fill="x")

        ttk.Checkbutton(options_frame, text="Recursive", variable=self.recursive).grid(
            row=0, column=0, sticky="w", **pad
        )
        ttk.Checkbutton(options_frame, text="Overwrite", variable=self.overwrite).grid(
            row=0, column=1, sticky="w", **pad
        )

        self.keep_larger_check = ttk.Checkbutton(
            options_frame,
            text="Keep compressed file even if larger",
            variable=self.keep_when_larger,
        )
        self.keep_larger_check.grid(row=1, column=0, sticky="w", columnspan=2, **pad)

        self.allow_lossy_check = ttk.Checkbutton(
            options_frame,
            text="Allow lossy target (JPEG)",
            variable=self.allow_lossy,
        )
        self.allow_lossy_check.grid(row=2, column=0, sticky="w", columnspan=2, **pad)

        # Action section
        action_frame = ttk.Frame(root)
        action_frame.pack(fill="x", pady=10)
        self.run_button = ttk.Button(action_frame, text="Run", command=self._run)
        self.run_button.pack(side="left")
        ttk.Button(action_frame, text="Clear Log", command=self._clear_log).pack(side="left", padx=8)

        # Log section
        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

    def _bind_drag_and_drop(self) -> None:
        if not DND_AVAILABLE:
            return
        self.input_entry.drop_target_register(DND_FILES)
        self.output_entry.drop_target_register(DND_FILES)
        self.input_entry.dnd_bind("<<Drop>>", self._on_input_drop)
        self.output_entry.dnd_bind("<<Drop>>", self._on_output_drop)

    def _extract_drop_paths(self, raw_data: str) -> list[str]:
        data = raw_data.strip()
        if not data:
            return []
        try:
            candidates = self.tk.splitlist(data)
        except tk.TclError:
            candidates = (data,)
        values: list[str] = []
        for item in candidates:
            path = str(item).strip()
            if path.startswith("{") and path.endswith("}"):
                path = path[1:-1]
            if path:
                values.append(path)
        return values

    def _on_input_drop(self, event: tk.Event) -> None:
        paths = self._extract_drop_paths(event.data)
        if not paths:
            return
        self._set_input_from_paths(paths)

    def _on_output_drop(self, event: tk.Event) -> None:
        paths = self._extract_drop_paths(event.data)
        if not paths:
            return
        candidate = Path(paths[0])
        output = str(candidate.parent if candidate.is_file() else candidate)
        self.output_path.set(output)
        self._append_log(f"[drop] output <- {output}")

    def _set_input_from_paths(self, paths: list[str]) -> None:
        if len(paths) == 1:
            self.input_batch_files = []
            self.input_path.set(paths[0])
            self._append_log(f"[input] {paths[0]}")
            self._auto_adjust_for_input()
            return

        all_files = all(Path(p).is_file() for p in paths)
        if all_files:
            self.input_batch_files = paths
            self.input_path.set(f"{paths[0]} (+{len(paths) - 1} files)")
            self.recursive.set(False)
            self._append_log(f"[input] {len(paths)} files selected (batch mode)")
            if not self.output_path.get().strip():
                self.output_path.set(str(Path(paths[0]).parent / "output_batch"))
            return

        self.input_batch_files = []
        self.input_path.set(paths[0])
        self._append_log("[input] mixed drag items detected, fallback to first")
        self._auto_adjust_for_input()

    def _auto_adjust_for_input(self) -> None:
        if self.input_batch_files:
            self.recursive.set(False)
            return

        raw = self.input_path.get().strip()
        if not raw:
            return

        path = Path(raw)
        if path.is_file():
            self.recursive.set(False)
            if not self.output_path.get().strip():
                self.output_path.set(str(path.parent / "output"))
        elif path.is_dir():
            self.recursive.set(True)
            if not self.output_path.get().strip():
                self.output_path.set(str(path.parent / f"{path.name}_output"))

    def _pick_input_file(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select input image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp *.gif"),
                ("All files", "*.*"),
            ],
        )
        paths = [str(item) for item in selected if str(item).strip()]
        if paths:
            self._set_input_from_paths(paths)

    def _pick_input_dir(self) -> None:
        selected = filedialog.askdirectory(title="Select input folder")
        if selected:
            self.input_batch_files = []
            self.input_path.set(selected)
            self._auto_adjust_for_input()

    def _pick_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="Select output folder")
        if selected:
            self.output_path.set(selected)

    def _refresh_mode_controls(self) -> None:
        is_convert = self.mode.get() == "convert"
        if is_convert:
            self.format_combo.configure(state="readonly")
            self.allow_lossy_check.state(["!disabled"])
            self.keep_larger_check.state(["disabled"])
        else:
            self.format_combo.configure(state="disabled")
            self.allow_lossy_check.state(["disabled"])
            self.keep_larger_check.state(["!disabled"])

    def _append_log(self, content: str) -> None:
        self.log_text.insert("end", content + "\n")
        self.log_text.see("end")

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def _build_cmd(self, input_path: str) -> list[str]:
        output_path = self.output_path.get().strip()
        if not input_path or not output_path:
            raise ValueError("Please set input and output path.")

        cmd = ["python3", str(self.script_path), self.mode.get(), "--input", input_path, "--output", output_path]

        if self.recursive.get():
            cmd.append("--recursive")
        if self.overwrite.get():
            cmd.append("--overwrite")

        if self.mode.get() == "compress":
            if self.keep_when_larger.get():
                cmd.append("--keep-when-larger")
        else:
            cmd.extend(["--to", self.target_format.get()])
            if self.allow_lossy.get():
                cmd.append("--allow-lossy")

        return cmd

    def _run(self) -> None:
        if self.mode.get() == "convert" and self.target_format.get() == "jpeg" and not self.allow_lossy.get():
            messagebox.showerror("Error", "JPEG is lossy. Please enable 'Allow lossy target (JPEG)'.")
            return

        try:
            if self.input_batch_files:
                commands = [self._build_cmd(path) for path in self.input_batch_files]
            else:
                commands = [self._build_cmd(self.input_path.get().strip())]
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.run_button.configure(state="disabled")
        self._append_log(f"[run] {len(commands)} task(s)")
        for cmd in commands:
            self._append_log("$ " + " ".join(cmd))

        thread = threading.Thread(target=self._run_subprocess, args=(commands,), daemon=True)
        thread.start()

    def _run_subprocess(self, commands: list[list[str]]) -> None:
        try:
            for cmd in commands:
                completed = subprocess.run(
                    cmd,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if completed.stdout.strip():
                    self.after(0, lambda out=completed.stdout.rstrip(): self._append_log(out))
                if completed.stderr.strip():
                    self.after(
                        0,
                        lambda err=completed.stderr.rstrip(): self._append_log("[stderr]\n" + err),
                    )
                self.after(
                    0,
                    lambda code=completed.returncode: self._append_log(f"[exit_code] {code}"),
                )
        except Exception as exc:  # pylint: disable=broad-except
            self.after(0, lambda: self._append_log(f"[error] {exc}"))
        finally:
            self.after(0, lambda: self.run_button.configure(state="normal"))


def main() -> None:
    app = ImageToolGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
