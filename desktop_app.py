"""FortiGate Backup Manager – Desktop GUI (tkinter)

Single-file entry point that:
 1. Creates local storage (data/ + backups/ next to the exe).
 2. Generates a Fernet key on first run.
 3. Initialises SQLite + tables.
 4. Shows an "Initial Setup" dialog if no admin exists.
 5. Shows a polished login screen.
 6. Launches the main tabbed dashboard with all management functions.
 7. Runs the APScheduler backup job in the background.
"""

import base64
import secrets
import threading
import queue
import traceback
from pathlib import Path
import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox

from apscheduler.schedulers.background import BackgroundScheduler

APP_TITLE = "FortiGate Backup Manager"
VERSION = "1.1.0"

# ── Colour palette ──────────────────────────────────────────────────────
BG          = "#0f172a"
BG_CARD     = "#1e293b"
BG_INPUT    = "#0f172a"
BG_HOVER    = "#334155"
ACCENT      = "#3b82f6"
ACCENT_DARK = "#2563eb"
GREEN       = "#22c55e"
RED         = "#ef4444"
AMBER       = "#f59e0b"
TEXT        = "#f1f5f9"
MUTED       = "#94a3b8"
BORDER      = "#334155"


# ════════════════════════════════════════════════════════════════════════
# Path helpers
# ════════════════════════════════════════════════════════════════════════

def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_storage_dir(app_dir: Path) -> Path:
    try:
        test_file = app_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink(missing_ok=True)
        return app_dir
    except Exception:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(app_dir)))
        return local_app_data / "FGBM"


def ensure_dirs(storage_dir: Path) -> tuple[Path, Path, Path]:
    data_dir = storage_dir / "data"
    backups_dir = storage_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    return data_dir, backups_dir, data_dir / "secret.key"


def load_or_create_secret(secret_file: Path) -> str:
    if secret_file.exists():
        return secret_file.read_text().strip()
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    secret_file.write_text(secret)
    return secret


def init_environment(base_dir: Path) -> None:
    storage_dir = get_storage_dir(base_dir)
    data_dir, backups_dir, secret_file = ensure_dirs(storage_dir)
    secret = load_or_create_secret(secret_file)
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", secret)
    db_path = data_dir / "fgbm.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    os.environ.setdefault("BACKUPS_ROOT", str(backups_dir))


# ════════════════════════════════════════════════════════════════════════
# Themed widgets helpers
# ════════════════════════════════════════════════════════════════════════

def configure_styles():
    """Apply a dark-themed ttk style globally."""
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=BG_CARD)
    style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("MutedCard.TLabel", background=BG_CARD, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 22, "bold"))
    style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
    style.configure("Header.TLabel", background=BG_CARD, foreground=TEXT, font=("Segoe UI", 13, "bold"))
    style.configure("Metric.TLabel", background=BG_CARD, foreground=ACCENT, font=("Segoe UI", 28, "bold"))
    style.configure("MetricLabel.TLabel", background=BG_CARD, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("StatusOK.TLabel", background=BG_CARD, foreground=GREEN, font=("Segoe UI", 10, "bold"))
    style.configure("StatusFail.TLabel", background=BG_CARD, foreground=RED, font=("Segoe UI", 10, "bold"))
    style.configure("StatusUnknown.TLabel", background=BG_CARD, foreground=AMBER, font=("Segoe UI", 10, "bold"))

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=BG_CARD, foreground=MUTED,
                     padding=[16, 8], font=("Segoe UI", 10))
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])

    style.configure("TEntry", fieldbackground=BG_INPUT, foreground=TEXT,
                     bordercolor=BORDER, insertcolor=TEXT, padding=[8, 6])
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=TEXT,
                     bordercolor=BORDER, arrowcolor=MUTED, padding=[8, 6])
    style.map("TCombobox",
              bordercolor=[("focus", ACCENT)],
              fieldbackground=[("readonly", BG_INPUT)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                     font=("Segoe UI", 10, "bold"), padding=[16, 8],
                     borderwidth=0)
    style.map("Accent.TButton",
              background=[("active", ACCENT_DARK), ("disabled", BORDER)])

    style.configure("Danger.TButton", background=RED, foreground="#ffffff",
                     font=("Segoe UI", 10, "bold"), padding=[12, 6],
                     borderwidth=0)
    style.map("Danger.TButton",
              background=[("active", "#dc2626"), ("disabled", BORDER)])

    style.configure("Secondary.TButton", background=BG_CARD, foreground=TEXT,
                     font=("Segoe UI", 10), padding=[12, 6], borderwidth=0)
    style.map("Secondary.TButton", background=[("active", BG_HOVER)])

    style.configure("TLabelframe", background=BG_CARD, foreground=MUTED,
                     bordercolor=BORDER, font=("Segoe UI", 10))
    style.configure("TLabelframe.Label", background=BG_CARD, foreground=ACCENT,
                     font=("Segoe UI", 10, "bold"))

    style.configure("Treeview",
                     background=BG_CARD, foreground=TEXT,
                     fieldbackground=BG_CARD, borderwidth=0,
                     rowheight=32, font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                     background=BG, foreground=MUTED,
                     font=("Segoe UI", 9, "bold"), borderwidth=0)
    style.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])

    style.configure("Vertical.TScrollbar", background=BG_CARD,
                     troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)


# ════════════════════════════════════════════════════════════════════════
# Initial admin setup
# ════════════════════════════════════════════════════════════════════════

def create_default_admin(db, root) -> None:
    from backend.auth import ensure_admin_user
    from database import models
    if db.query(models.User).first():
        return

    setup = tk.Toplevel(root)
    setup.title("Initial Setup")
    setup.configure(bg=BG)
    setup.geometry("420x300")
    setup.resizable(False, False)
    setup.grab_set()

    # Centre on screen
    setup.update_idletasks()
    x = (setup.winfo_screenwidth() - 420) // 2
    y = (setup.winfo_screenheight() - 300) // 2
    setup.geometry(f"+{x}+{y}")

    frame = ttk.Frame(setup)
    frame.pack(fill="both", expand=True, padx=30, pady=20)

    ttk.Label(frame, text="🔐 Create Admin Account",
              style="Title.TLabel", font=("Segoe UI", 16, "bold")).pack(pady=(0, 4))
    ttk.Label(frame, text="This is required on first launch.",
              style="Muted.TLabel").pack(pady=(0, 16))

    entry_frame = ttk.Frame(frame)
    entry_frame.pack(fill="x")

    ttk.Label(entry_frame, text="Username", style="Muted.TLabel").pack(anchor="w")
    username_entry = ttk.Entry(entry_frame, width=35)
    username_entry.pack(fill="x", pady=(2, 10))
    username_entry.focus_set()

    ttk.Label(entry_frame, text="Password", style="Muted.TLabel").pack(anchor="w")
    password_entry = ttk.Entry(entry_frame, show="●", width=35)
    password_entry.pack(fill="x", pady=(2, 16))

    def save_admin():
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Username and password required", parent=setup)
            return
        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters", parent=setup)
            return
        ensure_admin_user(db, username, password)
        setup.destroy()

    password_entry.bind("<Return>", lambda e: save_admin())
    ttk.Button(frame, text="Create Admin", style="Accent.TButton",
               command=save_admin).pack(fill="x")

    root.wait_window(setup)


# ════════════════════════════════════════════════════════════════════════
# Main application
# ════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)

        # Centre on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 1200) // 2
        y = (self.root.winfo_screenheight() - 780) // 2
        self.root.geometry(f"+{x}+{y}")

        self.queue: queue.Queue = queue.Queue()
        self.current_user = None
        self._center_id_map: dict[str, int] = {}

        configure_styles()
        self._build_login()

    # ── Login screen ────────────────────────────────────────────────
    def _build_login(self):
        self.login_frame = ttk.Frame(self.root)
        self.login_frame.pack(fill="both", expand=True)

        # Centred card
        card = ttk.Frame(self.login_frame, style="Card.TFrame", padding=40)
        card.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(card, text="🛡️ FortiGate Backup Manager",
                  font=("Segoe UI", 20, "bold"), style="Card.TLabel").pack(pady=(0, 4))
        ttk.Label(card, text=f"v{VERSION}  •  Secure Configuration Backups",
                  style="MutedCard.TLabel").pack(pady=(0, 24))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x")

        ttk.Label(form, text="Username", style="MutedCard.TLabel").pack(anchor="w")
        self.username_entry = ttk.Entry(form, width=36)
        self.username_entry.pack(fill="x", pady=(2, 12))
        self.username_entry.focus_set()

        ttk.Label(form, text="Password", style="MutedCard.TLabel").pack(anchor="w")
        self.password_entry = ttk.Entry(form, show="●", width=36)
        self.password_entry.pack(fill="x", pady=(2, 20))
        self.password_entry.bind("<Return>", lambda e: self.login())

        ttk.Button(card, text="Sign In", style="Accent.TButton",
                   command=self.login).pack(fill="x")

        self.login_status = ttk.Label(card, text="", foreground=RED,
                                       style="Card.TLabel", font=("Segoe UI", 9))
        self.login_status.pack(pady=(10, 0))

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            self.login_status.configure(text="Enter username and password.")
            return
        from backend.auth import authenticate_user
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            user = authenticate_user(db, username, password)
            if not user:
                self.login_status.configure(text="Invalid credentials.")
                return
            self.current_user = user
        finally:
            db.close()
        self.login_frame.destroy()
        self._build_main_ui()

    # ── Main UI ─────────────────────────────────────────────────────
    def _build_main_ui(self):
        # Top bar
        topbar = ttk.Frame(self.root, style="Card.TFrame", padding=(16, 10))
        topbar.pack(fill="x")
        ttk.Label(topbar, text=f"🛡️ {APP_TITLE}", style="Card.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(side="left")
        user_label = ttk.Label(topbar, text=f"👤 {self.current_user.username}  ({self.current_user.role})",
                               style="MutedCard.TLabel")
        user_label.pack(side="right")

        # Summary cards
        self._build_summary_bar()

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.centers_tab = ttk.Frame(self.notebook)
        self.backups_tab = ttk.Frame(self.notebook)
        self.events_tab = ttk.Frame(self.notebook)
        self.users_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.centers_tab, text="  🏢 Centers  ")
        self.notebook.add(self.backups_tab, text="  💾 Backups  ")
        self.notebook.add(self.events_tab, text="  📋 Events  ")
        if self.current_user.role == "admin":
            self.notebook.add(self.users_tab, text="  👥 Users  ")

        self._build_centers_tab()
        self._build_backups_tab()
        self._build_events_tab()
        if self.current_user.role == "admin":
            self._build_users_tab()

        self.refresh_all()

        if self.current_user.role == "viewer":
            self.add_center_btn.state(["disabled"])
            self.run_backup_btn.state(["disabled"])
            self.run_all_btn.state(["disabled"])

        # Status bar
        self.statusbar = ttk.Label(self.root, text="Ready", style="Muted.TLabel",
                                    padding=(12, 4))
        self.statusbar.pack(fill="x", side="bottom")

        self.root.after(500, self._process_queue)

    def _build_summary_bar(self):
        bar = ttk.Frame(self.root, padding=(12, 8))
        bar.pack(fill="x")

        cards_data = [
            ("total_card", "Total Centers", "0"),
            ("ok_card", "OK", "0"),
            ("failed_card", "Failed", "0"),
            ("last_card", "Last Backup", "--"),
        ]
        self._summary_labels = {}
        for i, (key, label_text, default) in enumerate(cards_data):
            card = ttk.Frame(bar, style="Card.TFrame", padding=14)
            card.pack(side="left", expand=True, fill="both", padx=(0 if i == 0 else 4, 4))
            ttk.Label(card, text=label_text, style="MetricLabel.TLabel").pack(anchor="w")
            lbl = ttk.Label(card, text=default, style="Metric.TLabel")
            lbl.pack(anchor="w")
            self._summary_labels[key] = lbl

    def _update_summary(self, centers):
        total = len(centers)
        ok = sum(1 for c in centers if c.status == "OK")
        failed = sum(1 for c in centers if c.status == "FAILED")
        last = "--"
        dates = [c.last_backup for c in centers if c.last_backup]
        if dates:
            from datetime import datetime
            latest = max(dates)
            if isinstance(latest, str):
                last = latest[:19]
            else:
                last = latest.strftime("%Y-%m-%d %H:%M")

        self._summary_labels["total_card"].configure(text=str(total))
        self._summary_labels["ok_card"].configure(text=str(ok), foreground=GREEN)
        self._summary_labels["failed_card"].configure(text=str(failed),
                                                       foreground=RED if failed else GREEN)
        self._summary_labels["last_card"].configure(text=last,
                                                     font=("Segoe UI", 14, "bold"))

    # ── Centers tab ─────────────────────────────────────────────────
    def _build_centers_tab(self):
        # Top action bar
        action_bar = ttk.Frame(self.centers_tab, style="Card.TFrame", padding=10)
        action_bar.pack(fill="x", padx=8, pady=(8, 4))

        self.run_all_btn = ttk.Button(action_bar, text="▶ Run All Backups",
                                       style="Accent.TButton",
                                       command=self.run_all_backups)
        self.run_all_btn.pack(side="left", padx=(0, 8))

        self.run_backup_btn = ttk.Button(action_bar, text="▶ Backup Selected",
                                          style="Secondary.TButton",
                                          command=self.run_selected_backup)
        self.run_backup_btn.pack(side="left", padx=(0, 8))

        ttk.Button(action_bar, text="🔄 Refresh", style="Secondary.TButton",
                   command=self.refresh_all).pack(side="left")

        delete_btn = ttk.Button(action_bar, text="🗑 Delete Selected",
                                style="Danger.TButton", command=self.delete_center)
        delete_btn.pack(side="right")

        # Add-center form
        form = ttk.LabelFrame(self.centers_tab, text="  Add New FortiGate  ", padding=12)
        form.pack(fill="x", padx=8, pady=4)

        fields = ttk.Frame(form, style="Card.TFrame")
        fields.pack(fill="x")

        labels = ["Name *", "Location", "FortiGate IP *", "Model", "API Token *"]
        self.center_entries: dict[str, ttk.Entry] = {}
        for i, label in enumerate(labels):
            col_frame = ttk.Frame(fields, style="Card.TFrame")
            col_frame.pack(side="left", expand=True, fill="x", padx=(0, 6))
            ttk.Label(col_frame, text=label, style="MutedCard.TLabel",
                      font=("Segoe UI", 8)).pack(anchor="w")
            key = label.replace(" *", "").lower().replace(" ", "_")
            entry = ttk.Entry(col_frame)
            if key == "api_token":
                entry.configure(show="●")
            entry.pack(fill="x", pady=(2, 0))
            self.center_entries[key] = entry

        self.add_center_btn = ttk.Button(form, text="+ Add Center",
                                          style="Accent.TButton",
                                          command=self.add_center)
        self.add_center_btn.pack(anchor="e", pady=(8, 0))

        # Tree
        tree_frame = ttk.Frame(self.centers_tab)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        cols = ("name", "location", "ip", "model", "status", "last_backup")
        self.centers_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                          selectmode="browse")
        headings = {"name": "Name", "location": "Location", "ip": "IP Address",
                    "model": "Model", "status": "Status", "last_backup": "Last Backup"}
        widths = {"name": 160, "location": 120, "ip": 140, "model": 100,
                  "status": 80, "last_backup": 160}
        for col in cols:
            self.centers_tree.heading(col, text=headings[col])
            self.centers_tree.column(col, width=widths[col], minwidth=60)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical",
                                   command=self.centers_tree.yview)
        self.centers_tree.configure(yscrollcommand=scrollbar.set)
        self.centers_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ── Backups tab ─────────────────────────────────────────────────
    def _build_backups_tab(self):
        top = ttk.Frame(self.backups_tab, style="Card.TFrame", padding=10)
        top.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(top, text="Center:", style="Card.TLabel").pack(side="left")
        self.backup_center = ttk.Combobox(top, state="readonly", width=28)
        self.backup_center.pack(side="left", padx=8)
        self.backup_center.bind("<<ComboboxSelected>>", lambda e: self.refresh_backups())

        ttk.Button(top, text="🔄 Refresh", style="Secondary.TButton",
                   command=self.refresh_backups).pack(side="left", padx=(0, 8))

        self.restore_btn = ttk.Button(top, text="⏪ Restore Selected",
                                       style="Danger.TButton",
                                       command=self.restore_selected)
        self.restore_btn.pack(side="right")

        tree_frame = ttk.Frame(self.backups_tab)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        cols = ("date", "file", "checksum", "size", "status")
        self.backups_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                          selectmode="browse")
        headings = {"date": "Backup Date", "file": "File", "checksum": "Checksum (SHA-256)",
                    "size": "Size", "status": "Status"}
        widths = {"date": 160, "file": 200, "checksum": 220, "size": 90, "status": 80}
        for col in cols:
            self.backups_tree.heading(col, text=headings[col])
            self.backups_tree.column(col, width=widths[col], minwidth=50)

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.backups_tree.yview)
        self.backups_tree.configure(yscrollcommand=sb.set)
        self.backups_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Events tab ──────────────────────────────────────────────────
    def _build_events_tab(self):
        tree_frame = ttk.Frame(self.events_tab)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("time", "center", "type", "message")
        self.events_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                         selectmode="browse")
        headings = {"time": "Timestamp", "center": "Center", "type": "Event Type",
                    "message": "Message"}
        widths = {"time": 160, "center": 140, "type": 130, "message": 400}
        for col in cols:
            self.events_tree.heading(col, text=headings[col])
            self.events_tree.column(col, width=widths[col], minwidth=50)

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=sb.set)
        self.events_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Users tab ───────────────────────────────────────────────────
    def _build_users_tab(self):
        form = ttk.LabelFrame(self.users_tab, text="  Create User  ", padding=12)
        form.pack(fill="x", padx=8, pady=(8, 4))

        fields = ttk.Frame(form, style="Card.TFrame")
        fields.pack(fill="x")

        col1 = ttk.Frame(fields, style="Card.TFrame")
        col1.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Label(col1, text="Username", style="MutedCard.TLabel",
                  font=("Segoe UI", 8)).pack(anchor="w")
        self.user_name = ttk.Entry(col1)
        self.user_name.pack(fill="x", pady=(2, 0))

        col2 = ttk.Frame(fields, style="Card.TFrame")
        col2.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Label(col2, text="Password", style="MutedCard.TLabel",
                  font=("Segoe UI", 8)).pack(anchor="w")
        self.user_password = ttk.Entry(col2, show="●")
        self.user_password.pack(fill="x", pady=(2, 0))

        col3 = ttk.Frame(fields, style="Card.TFrame")
        col3.pack(side="left", fill="x", padx=(0, 6))
        ttk.Label(col3, text="Role", style="MutedCard.TLabel",
                  font=("Segoe UI", 8)).pack(anchor="w")
        self.user_role = ttk.Combobox(col3, values=["admin", "operator", "viewer"],
                                       state="readonly", width=12)
        self.user_role.set("operator")
        self.user_role.pack(fill="x", pady=(2, 0))

        ttk.Button(form, text="+ Create User", style="Accent.TButton",
                   command=self.create_user).pack(anchor="e", pady=(8, 0))

        # Actions bar
        action_bar = ttk.Frame(self.users_tab, style="Card.TFrame", padding=10)
        action_bar.pack(fill="x", padx=8, pady=4)

        ttk.Label(action_bar, text="New Password:", style="Card.TLabel").pack(side="left")
        self.reset_password_entry = ttk.Entry(action_bar, show="●", width=20)
        self.reset_password_entry.pack(side="left", padx=6)
        ttk.Button(action_bar, text="🔑 Reset Password",
                   style="Secondary.TButton",
                   command=self.reset_user_password).pack(side="left", padx=(0, 8))
        ttk.Button(action_bar, text="⛔ Disable User",
                   style="Danger.TButton",
                   command=self.disable_user).pack(side="left")
        ttk.Button(action_bar, text="✅ Enable User",
                   style="Secondary.TButton",
                   command=self.enable_user).pack(side="left", padx=6)

        tree_frame = ttk.Frame(self.users_tab)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        cols = ("username", "role", "active", "created")
        self.users_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                        selectmode="browse")
        headings = {"username": "Username", "role": "Role", "active": "Status",
                    "created": "Created"}
        widths = {"username": 180, "role": 100, "active": 100, "created": 180}
        for col in cols:
            self.users_tree.heading(col, text=headings[col])
            self.users_tree.column(col, width=widths[col], minwidth=50)

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=sb.set)
        self.users_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Data refresh ────────────────────────────────────────────────
    def refresh_all(self):
        self.refresh_centers()
        self.refresh_backups()
        self.refresh_events()
        if self.current_user.role == "admin":
            self.refresh_users()

    def refresh_centers(self):
        for row in self.centers_tree.get_children():
            self.centers_tree.delete(row)
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            centers = db.query(models.Center).order_by(models.Center.name).all()
            self._center_id_map.clear()
            for c in centers:
                last = "--"
                if c.last_backup:
                    if isinstance(c.last_backup, str):
                        last = c.last_backup[:19]
                    else:
                        last = c.last_backup.strftime("%Y-%m-%d %H:%M")
                self.centers_tree.insert(
                    "", "end", iid=str(c.id),
                    values=(c.name, c.location or "--", c.fortigate_ip,
                            c.model or "--", c.status, last),
                    tags=(c.status,))
                self._center_id_map[c.name] = c.id

            # Tag colours
            self.centers_tree.tag_configure("OK", foreground=GREEN)
            self.centers_tree.tag_configure("FAILED", foreground=RED)
            self.centers_tree.tag_configure("UNKNOWN", foreground=AMBER)

            self.backup_center["values"] = [c.name for c in centers]
            self._update_summary(centers)
        finally:
            db.close()

    def refresh_backups(self):
        for row in self.backups_tree.get_children():
            self.backups_tree.delete(row)
        selected = self.backup_center.get().strip()
        if not selected:
            return
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            center = db.query(models.Center).filter(
                models.Center.name == selected).first()
            if not center:
                return
            backups = (db.query(models.Backup)
                       .filter(models.Backup.center_id == center.id)
                       .order_by(models.Backup.backup_date.desc()).all())
            for b in backups:
                date_str = "--"
                if b.backup_date:
                    if isinstance(b.backup_date, str):
                        date_str = b.backup_date[:19]
                    else:
                        date_str = b.backup_date.strftime("%Y-%m-%d %H:%M:%S")
                size_str = self._format_size(b.size)
                short_hash = b.checksum[:16] + "…" if len(b.checksum) > 16 else b.checksum
                self.backups_tree.insert(
                    "", "end", iid=str(b.id),
                    values=(date_str, b.file_path, short_hash, size_str, b.status))
        finally:
            db.close()

    def refresh_events(self):
        for row in self.events_tree.get_children():
            self.events_tree.delete(row)
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            events = (db.query(models.Event)
                      .order_by(models.Event.timestamp.desc())
                      .limit(100).all())
            for e in events:
                ts = "--"
                if e.timestamp:
                    if isinstance(e.timestamp, str):
                        ts = e.timestamp[:19]
                    else:
                        ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                # Get center name
                center = db.query(models.Center).filter(
                    models.Center.id == e.center_id).first()
                cname = center.name if center else f"ID:{e.center_id}"
                self.events_tree.insert("", "end",
                                         values=(ts, cname, e.event_type, e.message))
        finally:
            db.close()

    def refresh_users(self):
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            users = db.query(models.User).order_by(models.User.username).all()
            for u in users:
                active = "✅ Active" if u.is_active else "⛔ Disabled"
                created = "--"
                if u.created_at:
                    if isinstance(u.created_at, str):
                        created = u.created_at[:19]
                    else:
                        created = u.created_at.strftime("%Y-%m-%d %H:%M")
                self.users_tree.insert("", "end", iid=str(u.id),
                                        values=(u.username, u.role, active, created))
        finally:
            db.close()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    # ── Actions ─────────────────────────────────────────────────────
    def _set_status(self, msg: str):
        self.statusbar.configure(text=msg)

    def add_center(self):
        name = self.center_entries["name"].get().strip()
        ip = self.center_entries["fortigate_ip"].get().strip()
        token = self.center_entries["api_token"].get().strip()
        location = self.center_entries["location"].get().strip() or None
        model = self.center_entries["model"].get().strip() or None

        if not name or not ip or not token:
            messagebox.showerror("Error", "Name, IP, and API Token are required.")
            return
        if len(token) < 10:
            messagebox.showerror("Error", "API Token must be at least 10 characters.")
            return

        from backend.security import encrypt_token
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            if db.query(models.Center).filter(models.Center.name == name).first():
                messagebox.showerror("Error", f"Center '{name}' already exists.")
                return
            if db.query(models.Center).filter(models.Center.fortigate_ip == ip).first():
                messagebox.showerror("Error", f"IP '{ip}' is already registered.")
                return
            center = models.Center(
                name=name, location=location, fortigate_ip=ip,
                api_token_encrypted=encrypt_token(token),
                model=model, status="UNKNOWN",
            )
            db.add(center)
            db.commit()
            # Clear form
            for entry in self.center_entries.values():
                entry.delete(0, "end")
            self._set_status(f"✅ Center '{name}' added successfully.")
        finally:
            db.close()
        self.refresh_centers()

    def delete_center(self):
        selected = self.centers_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a center first.")
            return
        name = self.centers_tree.item(selected, "values")[0]
        if not messagebox.askyesno("Confirm Delete",
                                    f"Are you sure you want to delete '{name}'?\n"
                                    f"This will remove all associated backups and events."):
            return
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            center = db.query(models.Center).filter(
                models.Center.id == int(selected)).first()
            if center:
                db.query(models.Backup).filter(
                    models.Backup.center_id == center.id).delete()
                db.query(models.Event).filter(
                    models.Event.center_id == center.id).delete()
                db.delete(center)
                db.commit()
                self._set_status(f"🗑 Center '{name}' deleted.")
        finally:
            db.close()
        self.refresh_all()

    def run_all_backups(self):
        self._set_status("⏳ Running backups for all centers…")
        self.run_all_btn.state(["disabled"])
        threading.Thread(target=self._run_all_thread, daemon=True).start()

    def _run_all_thread(self):
        from backend.backup_engine import run_backup_for_all
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            result = run_backup_for_all(db)
            self.queue.put(("info", f"Backups complete: {result['ok']} OK, {result['failed']} failed"))
        except Exception as exc:
            self.queue.put(("error", f"Backup run failed: {exc}"))
        finally:
            db.close()
        self.queue.put(("refresh", None))
        self.queue.put(("enable_run_all", None))

    def run_selected_backup(self):
        selected = self.centers_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a center first.")
            return
        name = self.centers_tree.item(selected, "values")[0]
        self._set_status(f"⏳ Running backup for '{name}'…")
        threading.Thread(target=self._run_backup_thread,
                         args=(int(selected), name), daemon=True).start()

    def _run_backup_thread(self, center_id: int, center_name: str):
        from backend.backup_engine import run_backup_for_center
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            center = db.query(models.Center).filter(
                models.Center.id == center_id).first()
            if not center:
                self.queue.put(("error", "Center not found"))
                return
            result = run_backup_for_center(db, center)
            if result:
                self.queue.put(("info", f"✅ Backup OK for '{center_name}'"))
            else:
                self.queue.put(("error", f"❌ Backup failed for '{center_name}'"))
        except Exception as exc:
            self.queue.put(("error", f"Backup error: {exc}"))
        finally:
            db.close()
        self.queue.put(("refresh", None))

    def restore_selected(self):
        backup_id = self.backups_tree.focus()
        if not backup_id:
            messagebox.showerror("Error", "Select a backup first.")
            return
        if not messagebox.askyesno("Confirm Restore",
                                    "Are you sure you want to restore this configuration?\n"
                                    "This will overwrite the FortiGate's current configuration."):
            return
        self._set_status("⏳ Restoring configuration…")
        threading.Thread(target=self._restore_thread,
                         args=(int(backup_id),), daemon=True).start()

    def _restore_thread(self, backup_id: int):
        from backend.fortigate_client import restore_config
        from backend.security import decrypt_token
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            backup = db.query(models.Backup).filter(
                models.Backup.id == backup_id).first()
            if not backup:
                self.queue.put(("error", "Backup not found"))
                return
            center = db.query(models.Center).filter(
                models.Center.id == backup.center_id).first()
            if not center:
                self.queue.put(("error", "Center not found"))
                return
            path = Path(backup.file_path)
            if not path.exists():
                self.queue.put(("error", "Backup file missing on disk"))
                return
            token = decrypt_token(center.api_token_encrypted)
            restore_config(center.fortigate_ip, token, path.read_bytes())
            self.queue.put(("info", f"✅ Restore completed for '{center.name}'"))
        except Exception as exc:
            self.queue.put(("error", f"Restore failed: {exc}"))
        finally:
            db.close()

    def create_user(self):
        username = self.user_name.get().strip()
        password = self.user_password.get().strip()
        role = self.user_role.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Username and password are required.")
            return
        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters.")
            return
        from backend.auth import hash_password
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            if db.query(models.User).filter(
                    models.User.username == username).first():
                messagebox.showerror("Error", f"User '{username}' already exists.")
                return
            user = models.User(username=username,
                               password_hash=hash_password(password),
                               role=role, is_active=True)
            db.add(user)
            db.commit()
            self.user_name.delete(0, "end")
            self.user_password.delete(0, "end")
            self._set_status(f"✅ User '{username}' created.")
        finally:
            db.close()
        self.refresh_users()

    def disable_user(self):
        selected = self.users_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a user first.")
            return
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(
                models.User.id == int(selected)).first()
            if not user:
                return
            if user.username == self.current_user.username:
                messagebox.showerror("Error", "Cannot disable your own account.")
                return
            user.is_active = False
            db.add(user)
            db.commit()
            self._set_status(f"⛔ User '{user.username}' disabled.")
        finally:
            db.close()
        self.refresh_users()

    def enable_user(self):
        selected = self.users_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a user first.")
            return
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(
                models.User.id == int(selected)).first()
            if not user:
                return
            user.is_active = True
            db.add(user)
            db.commit()
            self._set_status(f"✅ User '{user.username}' enabled.")
        finally:
            db.close()
        self.refresh_users()

    def reset_user_password(self):
        selected = self.users_tree.focus()
        new_password = self.reset_password_entry.get().strip()
        if not selected or not new_password:
            messagebox.showerror("Error",
                                  "Select a user and enter a new password.")
            return
        if len(new_password) < 6:
            messagebox.showerror("Error",
                                  "Password must be at least 6 characters.")
            return
        from backend.auth import hash_password
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(
                models.User.id == int(selected)).first()
            if not user:
                return
            user.password_hash = hash_password(new_password)
            db.add(user)
            db.commit()
            self.reset_password_entry.delete(0, "end")
            self._set_status(f"🔑 Password reset for '{user.username}'.")
        finally:
            db.close()
        self.refresh_users()

    # ── Queue processor ─────────────────────────────────────────────
    def _process_queue(self):
        while not self.queue.empty():
            kind, message = self.queue.get()
            if kind == "error":
                messagebox.showerror("Error", message)
                self._set_status(f"❌ {message}")
            elif kind == "info":
                self._set_status(message)
            elif kind == "refresh":
                self.refresh_all()
            elif kind == "enable_run_all":
                self.run_all_btn.state(["!disabled"])
        self.root.after(500, self._process_queue)


# ════════════════════════════════════════════════════════════════════════
# Scheduler
# ════════════════════════════════════════════════════════════════════════

def start_scheduler():
    from backend.config import settings
    from backend.backup_engine import run_backup_for_all
    from database.db import SessionLocal
    if not settings.scheduler_enabled:
        return None
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    def job():
        db = SessionLocal()
        try:
            run_backup_for_all(db)
        finally:
            db.close()

    scheduler.add_job(job, "cron", hour=18, minute=0)
    scheduler.start()
    return scheduler


# ════════════════════════════════════════════════════════════════════════
# Entry points
# ════════════════════════════════════════════════════════════════════════

def main():
    base_dir = get_app_dir()
    init_environment(base_dir)

    from database import models  # noqa: F401
    from database.db import SessionLocal, get_engine, Base
    Base.metadata.create_all(bind=get_engine())

    root = tk.Tk()
    root.withdraw()
    db = SessionLocal()
    try:
        create_default_admin(db, root)
    finally:
        db.close()
    root.deiconify()

    scheduler = start_scheduler()
    app = App(root)  # noqa: F841
    try:
        root.mainloop()
    finally:
        if scheduler:
            scheduler.shutdown()


def run():
    try:
        main()
    except Exception as exc:
        storage_dir = get_storage_dir(get_app_dir())
        storage_dir.mkdir(parents=True, exist_ok=True)
        log_path = storage_dir / "fgbm-error.txt"
        try:
            log_path.write_text(traceback.format_exc())
        except Exception:
            pass
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Fatal error",
                f"Application failed to start.\n\n{exc}\n\nLog: {log_path}")
        except Exception:
            pass


if __name__ == "__main__":
    run()
