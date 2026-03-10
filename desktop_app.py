import base64
import secrets
import threading
import queue
from pathlib import Path
import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox

from apscheduler.schedulers.background import BackgroundScheduler


APP_TITLE = "FortiGate Backup Manager"


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
        local_app_data = Path(os.environ.get("LOCALAPPDATA", app_dir))
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
    import os
    storage_dir = get_storage_dir(base_dir)
    data_dir, backups_dir, secret_file = ensure_dirs(storage_dir)
    secret = load_or_create_secret(secret_file)
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", secret)
    db_path = data_dir / "fgbm.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    os.environ.setdefault("BACKUPS_ROOT", str(backups_dir))


def create_default_admin(db, root) -> None:
    from backend.auth import ensure_admin_user
    from database import models
    if db.query(models.User).first():
        return

    setup = tk.Toplevel(root)
    setup.title("Initial Setup")
    setup.geometry("360x220")
    setup.resizable(False, False)

    ttk.Label(setup, text="Create admin account", font=("Segoe UI", 12, "bold")).pack(pady=10)

    frame = ttk.Frame(setup, padding=10)
    frame.pack(fill="x")

    ttk.Label(frame, text="Username").grid(row=0, column=0, sticky="w")
    username_entry = ttk.Entry(frame)
    username_entry.grid(row=0, column=1, sticky="ew")

    ttk.Label(frame, text="Password").grid(row=1, column=0, sticky="w")
    password_entry = ttk.Entry(frame, show="*")
    password_entry.grid(row=1, column=1, sticky="ew")

    frame.columnconfigure(1, weight=1)

    def save_admin():
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Username and password required")
            return
        ensure_admin_user(db, username, password)
        setup.destroy()

    ttk.Button(setup, text="Create Admin", command=save_admin).pack(pady=10)
    setup.grab_set()
    root.wait_window(setup)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x700")

        self.queue = queue.Queue()
        self.current_user = None

        self._build_login()

    def _build_login(self):
        self.login_frame = ttk.Frame(self.root, padding=20)
        self.login_frame.pack(fill="both", expand=True)

        ttk.Label(self.login_frame, text="FortiGate Backup Manager", font=("Segoe UI", 16, "bold")).pack(pady=10)

        form = ttk.Frame(self.login_frame)
        form.pack(pady=10)

        ttk.Label(form, text="Username").grid(row=0, column=0, sticky="w")
        self.username_entry = ttk.Entry(form, width=30)
        self.username_entry.grid(row=0, column=1, padx=10, pady=6)

        ttk.Label(form, text="Password").grid(row=1, column=0, sticky="w")
        self.password_entry = ttk.Entry(form, width=30, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=6)

        ttk.Button(self.login_frame, text="Login", command=self.login).pack(pady=10)

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        from backend.auth import authenticate_user
        from database.db import SessionLocal
        with SessionLocal() as db:
            user = authenticate_user(db, username, password)
            if not user:
                messagebox.showerror("Login failed", "Invalid credentials")
                return
            self.current_user = user
        self.login_frame.destroy()
        self._build_main_ui()

    def _build_main_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.centers_tab = ttk.Frame(self.notebook)
        self.backups_tab = ttk.Frame(self.notebook)
        self.events_tab = ttk.Frame(self.notebook)
        self.users_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.centers_tab, text="Centers")
        self.notebook.add(self.backups_tab, text="Backups")
        self.notebook.add(self.events_tab, text="Events")
        if self.current_user.role == "admin":
            self.notebook.add(self.users_tab, text="Users")

        self._build_centers_tab()
        self._build_backups_tab()
        self._build_events_tab()
        if self.current_user.role == "admin":
            self._build_users_tab()

        self.refresh_all()

        if self.current_user.role == "viewer":
            self.add_center_btn.state(["disabled"])
            self.run_backup_btn.state(["disabled"])
            self.restore_btn.state(["disabled"])

        self.root.after(500, self._process_queue)

    def _build_centers_tab(self):
        form = ttk.LabelFrame(self.centers_tab, text="Add FortiGate", padding=10)
        form.pack(fill="x", padx=10, pady=10)

        self.center_name = ttk.Entry(form)
        self.center_location = ttk.Entry(form)
        self.center_ip = ttk.Entry(form)
        self.center_model = ttk.Entry(form)
        self.center_token = ttk.Entry(form)

        labels = ["Name", "Location", "FortiGate IP", "Model", "API Token"]
        entries = [self.center_name, self.center_location, self.center_ip, self.center_model, self.center_token]
        for i, (label, entry) in enumerate(zip(labels, entries)):
            ttk.Label(form, text=label).grid(row=0, column=i)
            entry.grid(row=1, column=i, padx=5, pady=5)

        self.add_center_btn = ttk.Button(form, text="Add Center", command=self.add_center)
        self.add_center_btn.grid(row=1, column=5, padx=5)

        self.centers_tree = ttk.Treeview(self.centers_tab, columns=("name", "ip", "model", "status", "last"), show="headings")
        self.centers_tree.heading("name", text="Name")
        self.centers_tree.heading("ip", text="IP")
        self.centers_tree.heading("model", text="Model")
        self.centers_tree.heading("status", text="Status")
        self.centers_tree.heading("last", text="Last Backup")
        self.centers_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.run_backup_btn = ttk.Button(self.centers_tab, text="Run Backup (Selected)", command=self.run_selected_backup)
        self.run_backup_btn.pack(pady=6)

    def _build_backups_tab(self):
        top = ttk.Frame(self.backups_tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Center").pack(side="left")
        self.backup_center = ttk.Combobox(top, state="readonly")
        self.backup_center.pack(side="left", padx=10)
        ttk.Button(top, text="Refresh", command=self.refresh_backups).pack(side="left")

        self.backups_tree = ttk.Treeview(self.backups_tab, columns=("date", "size", "status"), show="headings")
        self.backups_tree.heading("date", text="Date")
        self.backups_tree.heading("size", text="Size")
        self.backups_tree.heading("status", text="Status")
        self.backups_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.restore_btn = ttk.Button(self.backups_tab, text="Restore Selected Backup", command=self.restore_selected)
        self.restore_btn.pack(pady=6)

    def _build_events_tab(self):
        self.events_tree = ttk.Treeview(self.events_tab, columns=("time", "type", "message"), show="headings")
        self.events_tree.heading("time", text="Time")
        self.events_tree.heading("type", text="Type")
        self.events_tree.heading("message", text="Message")
        self.events_tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _build_users_tab(self):
        form = ttk.LabelFrame(self.users_tab, text="Create User", padding=10)
        form.pack(fill="x", padx=10, pady=10)

        self.user_name = ttk.Entry(form)
        self.user_password = ttk.Entry(form, show="*")
        self.user_role = ttk.Combobox(form, values=["admin", "operator", "viewer"], state="readonly")
        self.user_role.set("operator")

        ttk.Label(form, text="Username").grid(row=0, column=0)
        self.user_name.grid(row=1, column=0, padx=5, pady=5)
        ttk.Label(form, text="Password").grid(row=0, column=1)
        self.user_password.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(form, text="Role").grid(row=0, column=2)
        self.user_role.grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(form, text="Create", command=self.create_user).grid(row=1, column=3, padx=5)

        self.users_tree = ttk.Treeview(self.users_tab, columns=("username", "role", "active"), show="headings")
        self.users_tree.heading("username", text="Username")
        self.users_tree.heading("role", text="Role")
        self.users_tree.heading("active", text="Active")
        self.users_tree.pack(fill="both", expand=True, padx=10, pady=10)

        actions = ttk.Frame(self.users_tab)
        actions.pack(pady=6)
        self.reset_password_entry = ttk.Entry(actions, show="*")
        self.reset_password_entry.pack(side="left", padx=5)
        ttk.Button(actions, text="Reset Password", command=self.reset_user_password).pack(side="left", padx=5)
        ttk.Button(actions, text="Disable Selected User", command=self.disable_user).pack(side="left", padx=5)

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
        centers = []
        with SessionLocal() as db:
            centers = db.query(models.Center).order_by(models.Center.name).all()
            for center in centers:
                self.centers_tree.insert("", "end", iid=str(center.id), values=(center.name, center.fortigate_ip, center.model or "--", center.status, center.last_backup))
        self.backup_center["values"] = [center.name for center in centers]

    def refresh_backups(self):
        for row in self.backups_tree.get_children():
            self.backups_tree.delete(row)
        selected = self.backup_center.get().strip()
        if not selected:
            return
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            center = db.query(models.Center).filter(models.Center.name == selected).first()
            if not center:
                return
            backups = db.query(models.Backup).filter(models.Backup.center_id == center.id).order_by(models.Backup.backup_date.desc()).all()
            for backup in backups:
                self.backups_tree.insert("", "end", iid=str(backup.id), values=(backup.backup_date, backup.size, backup.status))

    def refresh_events(self):
        for row in self.events_tree.get_children():
            self.events_tree.delete(row)
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            events = db.query(models.Event).order_by(models.Event.timestamp.desc()).limit(50).all()
            for event in events:
                self.events_tree.insert("", "end", values=(event.timestamp, event.event_type, event.message))

    def refresh_users(self):
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            users = db.query(models.User).order_by(models.User.username).all()
            for user in users:
                active = "Yes" if user.is_active else "No"
                self.users_tree.insert("", "end", iid=str(user.id), values=(user.username, user.role, active))

    def add_center(self):
        name = self.center_name.get().strip()
        ip = self.center_ip.get().strip()
        token = self.center_token.get().strip()
        if not name or not ip or not token:
            messagebox.showerror("Error", "Name, IP and API token are required")
            return
        from backend.security import encrypt_token
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            if db.query(models.Center).filter(models.Center.name == name).first():
                messagebox.showerror("Error", "Center already exists")
                return
            center = models.Center(
                name=name,
                location=self.center_location.get().strip() or None,
                fortigate_ip=ip,
                api_token_encrypted=encrypt_token(token),
                model=self.center_model.get().strip() or None,
                status="UNKNOWN",
            )
            db.add(center)
            db.commit()
        self.refresh_centers()

    def run_selected_backup(self):
        selected = self.centers_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a center")
            return
        threading.Thread(target=self._run_backup_thread, args=(int(selected),), daemon=True).start()

    def _run_backup_thread(self, center_id: int):
        from backend.backup_engine import run_backup_for_center
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            center = db.query(models.Center).filter(models.Center.id == center_id).first()
            if not center:
                self.queue.put(("error", "Center not found"))
                return
            run_backup_for_center(db, center)
        self.queue.put(("refresh", None))

    def restore_selected(self):
        backup_id = self.backups_tree.focus()
        if not backup_id:
            messagebox.showerror("Error", "Select a backup")
            return
        threading.Thread(target=self._restore_thread, args=(int(backup_id),), daemon=True).start()

    def _restore_thread(self, backup_id: int):
        from backend.fortigate_client import restore_config
        from backend.security import decrypt_token
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
            if not backup:
                self.queue.put(("error", "Backup not found"))
                return
            center = db.query(models.Center).filter(models.Center.id == backup.center_id).first()
            if not center:
                self.queue.put(("error", "Center not found"))
                return
            path = Path(backup.file_path)
            if not path.exists():
                self.queue.put(("error", "Backup file missing"))
                return
            token = decrypt_token(center.api_token_encrypted)
            restore_config(center.fortigate_ip, token, path.read_bytes())
        self.queue.put(("info", "Restore completed"))

    def create_user(self):
        username = self.user_name.get().strip()
        password = self.user_password.get().strip()
        role = self.user_role.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Username and password required")
            return
        from backend.auth import hash_password
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            if db.query(models.User).filter(models.User.username == username).first():
                messagebox.showerror("Error", "User already exists")
                return
            user = models.User(username=username, password_hash=hash_password(password), role=role, is_active=True)
            db.add(user)
            db.commit()
        self.refresh_users()

    def disable_user(self):
        selected = self.users_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a user")
            return
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            user = db.query(models.User).filter(models.User.id == int(selected)).first()
            if not user:
                return
            if user.username == self.current_user.username:
                messagebox.showerror("Error", "Cannot disable your own account")
                return
            user.is_active = False
            db.add(user)
            db.commit()
        self.refresh_users()

    def reset_user_password(self):
        selected = self.users_tree.focus()
        new_password = self.reset_password_entry.get().strip()
        if not selected or not new_password:
            messagebox.showerror("Error", "Select a user and enter a password")
            return
        from backend.auth import hash_password
        from database.db import SessionLocal
        from database import models
        with SessionLocal() as db:
            user = db.query(models.User).filter(models.User.id == int(selected)).first()
            if not user:
                return
            user.password_hash = hash_password(new_password)
            db.add(user)
            db.commit()
        self.refresh_users()

    def _process_queue(self):
        while not self.queue.empty():
            kind, message = self.queue.get()
            if kind == "error":
                messagebox.showerror("Error", message)
            elif kind == "info":
                messagebox.showinfo("Info", message)
            elif kind == "refresh":
                self.refresh_all()
        self.root.after(500, self._process_queue)


def start_scheduler():
    from backend.config import settings
    from backend.backup_engine import run_backup_for_all
    from database.db import SessionLocal
    if not settings.scheduler_enabled:
        return None
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    def job():
        with SessionLocal() as db:
            run_backup_for_all(db)

    scheduler.add_job(job, "cron", hour=18, minute=0)
    scheduler.start()
    return scheduler


def main():
    base_dir = get_app_dir()
    init_environment(base_dir)

    from database import models
    from database.db import SessionLocal, get_engine, Base
    Base.metadata.create_all(bind=get_engine())
    root = tk.Tk()
    root.withdraw()
    with SessionLocal() as db:
        create_default_admin(db, root)
    root.deiconify()
    scheduler = start_scheduler()

    app = App(root)
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
        log_path = storage_dir / "fgbm.log"
        try:
            log_path.write_text(str(exc))
        except Exception:
            pass
        messagebox.showerror("Fatal error", f"Application failed to start.\n\n{exc}")


if __name__ == "__main__":
    run()
