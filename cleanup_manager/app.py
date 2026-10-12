from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import IMAGE_SUFFIXES, ScanItem, format_size, modified_text, recycle_paths, scan_folder

BG, PANEL, PANEL_2 = "#0b1120", "#111a2e", "#18233b"
TEXT, MUTED, ACCENT = "#f4f7ff", "#9aa8c2", "#55d6be"
DANGER, BORDER = "#ff647c", "#2a3854"

class CleanupApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Cleanup Manager")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.configure(bg=BG)
        self.items: dict[str, ScanItem] = {}
        self.checked: set[Path] = set()
        self.cancel_event = threading.Event()
        self.preview_image = None
        self._style()
        self._build()
        self._show_blank()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED,
                        relief="flat", font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#214c5a")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TProgressbar", background=ACCENT, troughcolor=PANEL_2, borderwidth=0)

    def _button(self, parent, text, command, danger=False, secondary=False):
        color = DANGER if danger else (PANEL_2 if secondary else ACCENT)
        fg = TEXT if danger or secondary else "#061613"
        btn = tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                        activebackground="#ff8295" if danger else "#78ead6",
                        activeforeground=fg, relief="flat", bd=0, padx=16, pady=9,
                        cursor="hand2", font=("Segoe UI Semibold", 10))
        btn.bind("<Enter>", lambda _e: btn.configure(bg="#ff8295" if danger else ("#263653" if secondary else "#78ead6")))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=color))
        return btn

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="Cleanup Manager", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 22)).pack(side="left")
        tk.Label(header, text="Review first. Recycle safely.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left", padx=14, pady=(9, 0))
        controls = tk.Frame(self, bg=BG, padx=24)
        controls.pack(fill="x")
        self.path_var = tk.StringVar(value=str(Path.home()))
        entry = tk.Entry(controls, textvariable=self.path_var, bg=PANEL, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        entry.pack(side="left", fill="x", expand=True, ipady=9)
        self._button(controls, "Browse", self.choose_folder, secondary=True).pack(side="left", padx=8)
        self.scan_btn = self._button(controls, "Scan folder", self.start_scan)
        self.scan_btn.pack(side="left")
        filters = tk.Frame(self, bg=BG, padx=24, pady=12)
        filters.pack(fill="x")
        self.nested_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="Show every nested file and folder",
                        variable=self.nested_var).pack(side="left")
        tk.Label(filters, text="Minimum size:", bg=BG, fg=MUTED).pack(side="left", padx=(24, 6))
        self.size_var = tk.StringVar(value="0")
        tk.Spinbox(filters, from_=0, to=100000, textvariable=self.size_var, width=8,
                   bg=PANEL, fg=TEXT, buttonbackground=PANEL_2, relief="flat").pack(side="left")
        tk.Label(filters, text="MB", bg=BG, fg=MUTED).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.body = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, bd=0)
        self.body.pack(fill="both", expand=True, padx=24, pady=(4, 12))
        left = tk.Frame(self.body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        right = tk.Frame(self.body, bg=PANEL, highlightbackground=BORDER,
                         highlightthickness=1, padx=20, pady=18)
        self.body.add(left, minsize=560, stretch="always")
        self.body.add(right, minsize=280)
        self.tree = ttk.Treeview(left, columns=("size", "modified", "path"),
                                 show="tree headings", selectmode="extended")
        for column, label in (("#0", "Keep / delete"), ("size", "Size"),
                              ("modified", "Modified"), ("path", "Location")):
            self.tree.heading(column, text=label)
        self.tree.column("#0", width=250)
        self.tree.column("size", width=90, anchor="e")
        self.tree.column("modified", width=135)
        self.tree.column("path", width=330)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self.show_preview)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        self.preview_title = tk.Label(right, text="Preview", bg=PANEL, fg=TEXT,
                                      anchor="w", wraplength=330,
                                      font=("Segoe UI Semibold", 16))
        self.preview_title.pack(fill="x")
        self.preview = tk.Label(right, text="Select an item to inspect it.",
                                bg=PANEL, fg=MUTED, justify="left",
                                anchor="nw", wraplength=330)
        self.preview.pack(fill="both", expand=True, pady=16)
        self._button(right, "Open in Explorer", self.open_selected,
                     secondary=True).pack(fill="x")
        footer = tk.Frame(self, bg=BG, padx=24)
        footer.pack(fill="x", pady=(0, 18))
        self.status_var = tk.StringVar()
        tk.Label(footer, textvariable=self.status_var, bg=BG,
                 fg=MUTED, anchor="w").pack(side="left", fill="x", expand=True)
        self._button(footer, "Keep selected", self.keep_selected,
                     secondary=True).pack(side="right", padx=8)
        self.delete_btn = self._button(footer, "Move checked to Recycle Bin",
                                       self.delete_checked, danger=True)
        self.delete_btn.pack(side="right")

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.path_var.get() or str(Path.home()))
        if chosen:
            self.path_var.set(chosen)

    def _show_blank(self) -> None:
        self.status_var.set("Blank - choose a folder, then scan. Nothing is selected for deletion.")
        self.delete_btn.configure(state="disabled")

    def start_scan(self) -> None:
        try:
            root = Path(self.path_var.get()).expanduser()
            min_bytes = max(0, float(self.size_var.get())) * 1024 * 1024
            if not root.is_dir():
                raise ValueError("Please choose an existing folder.")
        except ValueError as exc:
            self.status_var.set(f"Failure: {exc}")
            messagebox.showerror("Cannot scan", str(exc), parent=self)
            return
        include_nested = self.nested_var.get()
        self.cancel_event.clear()
        self.items.clear()
        self.checked.clear()
        self.delete_btn.configure(state="disabled")
        self.tree.delete(*self.tree.get_children())
        self.scan_btn.configure(text="Scanning...", state="disabled")
        self.progress.pack(fill="x", padx=24, before=self.body)
        self.progress.start(12)
        self.status_var.set("Scanning. Protected and unreadable items are skipped.")

        def worker():
            try:
                found = scan_folder(root, include_nested, int(min_bytes),
                                    self.cancel_event.is_set)
                self.after(0, lambda: self.finish_scan(found))
            except Exception as exc:
                self.after(0, lambda error=str(exc): self.fail_scan(error))
        threading.Thread(target=worker, daemon=True).start()

    def finish_scan(self, found: list[ScanItem]) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.scan_btn.configure(text="Scan folder", state="normal")
        for index, item in enumerate(found):
            iid = f"item-{index}"
            self.items[iid] = item
            icon = "📁" if item.is_dir else "📄"
            self.tree.insert("", "end", iid=iid, text=f"☐  {icon} {item.name}",
                             values=(format_size(item.size), modified_text(item.modified),
                                     str(item.path.parent)))
        if found:
            total = sum(item.size for item in found)
            self.status_var.set(f"{len(found):,} items found ({format_size(total)} reviewed).")
        else:
            self.status_var.set("Scan finished; no matching items were found.")

    def fail_scan(self, error: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.scan_btn.configure(text="Scan folder", state="normal")
        self.status_var.set(f"Failure: {error}")
        messagebox.showerror("Scan failed", error, parent=self)

    def on_tree_click(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify_column(event.x) != "#0":
            return
        item = self.items[iid]
        if item.path in self.checked:
            self.checked.remove(item.path)
        else:
            self.checked.add(item.path)
        icon = "📁" if item.is_dir else "📄"
        self.tree.item(iid, text=f"{'☑' if item.path in self.checked else '☐'}  {icon} {item.name}")
        self.delete_btn.configure(state="normal" if self.checked else "disabled")
        self.status_var.set(f"{len(self.checked)} item(s) checked for the Recycle Bin.")

    def show_preview(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        item = self.items[selected[0]]
        self.preview_title.configure(text=item.name)
        self.preview_image = None
        details = f"{'Folder' if item.is_dir else 'File'}\n{format_size(item.size)}\nModified {modified_text(item.modified)}\n\n{item.path}"
        if item.is_dir:
            try:
                names = [p.name for p in list(item.path.iterdir())[:12]]
                details += "\n\nContains:\n" + "\n".join(names) + ("\n..." if len(names) == 12 else "")
            except OSError:
                details += "\n\nContents cannot be read."
        elif item.path.suffix.lower() in IMAGE_SUFFIXES:
            try:
                from PIL import Image, ImageTk
                image = Image.open(item.path)
                image.thumbnail((330, 280))
                self.preview_image = ImageTk.PhotoImage(image)
                self.preview.configure(image=self.preview_image, compound="top", text="\n" + details)
                return
            except Exception:
                details += "\n\nInstall Pillow for an image thumbnail."
        elif item.path.suffix.lower() in {".txt", ".md", ".py", ".js", ".json", ".css", ".html", ".csv"} and item.size < 1_000_000:
            try:
                details += "\n\nPreview:\n" + item.path.read_text(encoding="utf-8", errors="replace")[:1400]
            except OSError:
                pass
        self.preview.configure(image="", text=details)

    def open_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        path = self.items[selected[0]].path
        subprocess.Popen(["explorer", "/select,", str(path)] if path.is_file()
                         else ["explorer", str(path)])

    def keep_selected(self) -> None:
        for iid in self.tree.selection():
            item = self.items[iid]
            self.checked.discard(item.path)
            icon = "📁" if item.is_dir else "📄"
            self.tree.item(iid, text=f"☐  {icon} {item.name}")
        self.delete_btn.configure(state="normal" if self.checked else "disabled")
        self.status_var.set("Selected rows are marked to keep.")

    def delete_checked(self) -> None:
        existing = [path for path in self.checked if path.exists()]
        if not existing:
            self.checked.clear()
            self.delete_btn.configure(state="disabled")
            self.status_var.set("The selected files no longer exist. Scan again.")
            return
        preview = "\n".join(f"• {path.name}" for path in existing[:8])
        if len(existing) > 8:
            preview += f"\n• ...and {len(existing) - 8} more"
        if not messagebox.askyesno("Move to Recycle Bin",
                                   f"Move {len(existing)} checked item(s) to the Recycle Bin?\n\n{preview}",
                                   icon="warning", parent=self):
            return
        self.delete_btn.configure(state="disabled")
        self.status_var.set("Moving checked items to the Recycle Bin...")

        def worker():
            try:
                recycle_paths(existing)
                self.after(0, lambda: self.deleted(existing))
            except Exception as exc:
                self.after(0, lambda error=str(exc): self.delete_failed(error))
        threading.Thread(target=worker, daemon=True).start()

    def deleted(self, paths: list[Path]) -> None:
        removed = set(paths)
        for iid, item in list(self.items.items()):
            if item.path in removed:
                self.tree.delete(iid)
                self.items.pop(iid)
        self.checked.clear()
        self.delete_btn.configure(state="disabled")
        self.status_var.set(f"{len(paths)} item(s) moved to the Recycle Bin.")

    def delete_failed(self, error: str) -> None:
        self.delete_btn.configure(state="normal" if self.checked else "disabled")
        self.status_var.set(f"Failure: {error}")
        messagebox.showerror("Could not recycle items", error, parent=self)

def main() -> None:
    CleanupApp().mainloop()
