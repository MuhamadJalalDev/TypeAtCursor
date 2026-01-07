import time
import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import pyautogui

# Safety: move mouse to TOP-LEFT corner to stop immediately
pyautogui.FAILSAFE = True


class AutoTyperGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Typer (Types into Active Cursor)")
        self.geometry("720x480")
        self.minsize(680, 440)

        self._worker_thread = None
        self._stop_flag = threading.Event()

        # Defaults
        self.prep_delay = tk.IntVar(value=5)
        self.typing_interval = tk.DoubleVar(value=0.03)

        self.enable_variation = tk.BooleanVar(value=True)
        self.variation_every_n = tk.IntVar(value=12)
        self.extra_pause_min = tk.DoubleVar(value=0.02)
        self.extra_pause_max = tk.DoubleVar(value=0.12)

        self.status_text = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self):
        # Top instructions
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(
            top,
            text="Paste or type your text below. Click Start, then focus Word (or any app) within the countdown.",
            wraplength=680
        ).pack(anchor="w")

        # Text box
        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(fill="both", expand=True)

        self.text_box = tk.Text(mid, wrap="word", height=12)
        self.text_box.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(mid, command=self.text_box.yview)
        scroll.pack(fill="y", side="right")
        self.text_box.configure(yscrollcommand=scroll.set)

        # Controls
        controls = ttk.LabelFrame(self, text="Settings", padding=10)
        controls.pack(fill="x", padx=10, pady=(0, 10))

        # Row 1
        r1 = ttk.Frame(controls)
        r1.pack(fill="x")

        ttk.Label(r1, text="Preparation delay (seconds):").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(r1, from_=1, to=30, textvariable=self.prep_delay, width=6).grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(r1, text="Typing interval (seconds/char):").grid(row=0, column=2, sticky="w")
        ttk.Entry(r1, textvariable=self.typing_interval, width=8).grid(row=0, column=3, sticky="w", padx=(8, 0))

        # Row 2 (variation)
        r2 = ttk.Frame(controls)
        r2.pack(fill="x", pady=(8, 0))

        ttk.Checkbutton(r2, text="Enable human-like variation", variable=self.enable_variation).grid(row=0, column=0, sticky="w")

        ttk.Label(r2, text="Extra pause every N chars:").grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Spinbox(r2, from_=2, to=100, textvariable=self.variation_every_n, width=6).grid(row=0, column=2, sticky="w", padx=(8, 20))

        ttk.Label(r2, text="Extra pause range (sec):").grid(row=0, column=3, sticky="w")
        ttk.Entry(r2, textvariable=self.extra_pause_min, width=6).grid(row=0, column=4, sticky="w", padx=(8, 4))
        ttk.Label(r2, text="to").grid(row=0, column=5, sticky="w")
        ttk.Entry(r2, textvariable=self.extra_pause_max, width=6).grid(row=0, column=6, sticky="w", padx=(4, 0))

        # Buttons + status
        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")

        self.start_btn = ttk.Button(bottom, text="Start Typing", command=self.start_typing)
        self.start_btn.pack(side="left")

        self.stop_btn = ttk.Button(bottom, text="Stop", command=self.stop_typing, state="disabled")
        self.stop_btn.pack(side="left", padx=(10, 0))

        ttk.Label(bottom, textvariable=self.status_text).pack(side="right")

        # Failsafe note
        ttk.Label(
            self,
            text="Emergency stop: move mouse to top-left corner (pyautogui.FAILSAFE).",
            foreground="gray"
        ).pack(anchor="w", padx=12, pady=(0, 8))

    def _set_running(self, running: bool):
        if running:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

    def start_typing(self):
        text = self.text_box.get("1.0", "end").rstrip("\n")

        if not text.strip():
            messagebox.showwarning("No text", "Please paste/type some text first.")
            return

        # Validate numeric ranges a bit
        if self.typing_interval.get() < 0:
            messagebox.showerror("Invalid typing interval", "Typing interval must be >= 0.")
            return
        if self.prep_delay.get() < 1:
            messagebox.showerror("Invalid delay", "Preparation delay must be at least 1 second.")
            return
        if self.extra_pause_min.get() < 0 or self.extra_pause_max.get() < 0:
            messagebox.showerror("Invalid pause", "Pause values must be >= 0.")
            return
        if self.extra_pause_max.get() < self.extra_pause_min.get():
            messagebox.showerror("Invalid pause range", "Max pause must be >= min pause.")
            return

        self._stop_flag.clear()
        self._set_running(True)

        # Run typing in a background thread so the GUI stays responsive
        self._worker_thread = threading.Thread(target=self._typing_worker, args=(text,), daemon=True)
        self._worker_thread.start()

    def stop_typing(self):
        self._stop_flag.set()
        self.status_text.set("Stopping...")

    def _typing_worker(self, text: str):
        try:
            delay = self.prep_delay.get()

            # Countdown (update GUI safely via after)
            for remaining in range(delay, 0, -1):
                if self._stop_flag.is_set():
                    self._safe_status("Stopped before typing.")
                    self._safe_done()
                    return
                self._safe_status(f"Starting in {remaining}s... Focus Word (or target app).")
                time.sleep(1)

            self._safe_status("Typing... (Move mouse to top-left to trigger FAILSAFE)")

            interval = self.typing_interval.get()
            variation = self.enable_variation.get()
            every_n = max(2, self.variation_every_n.get())
            pmin = self.extra_pause_min.get()
            pmax = self.extra_pause_max.get()

            for i, ch in enumerate(text, start=1):
                if self._stop_flag.is_set():
                    self._safe_status("Stopped.")
                    self._safe_done()
                    return

                # Type into the currently focused window/cursor
                pyautogui.write(ch, interval=interval)

                if variation and (i % every_n == 0):
                    time.sleep(random.uniform(pmin, pmax))

            self._safe_status("Done.")
            self._safe_done()

        except pyautogui.FailSafeException:
            self._safe_status("FAILSAFE triggered (mouse to top-left). Aborted.")
            self._safe_done()
        except Exception as e:
            self._safe_status(f"Error: {e}")
            self._safe_done()

    def _safe_status(self, msg: str):
        self.after(0, lambda: self.status_text.set(msg))

    def _safe_done(self):
        self.after(0, lambda: self._set_running(False))


if __name__ == "__main__":
    # Optional: slightly reduce pyautogui built-in pause between calls
    # pyautogui.PAUSE = 0
    app = AutoTyperGUI()
    app.mainloop()
