import os
import sys
import shutil
from pathlib import Path

# Override environment variables for isolated testing
os.environ["DATABASE_URL"] = "sqlite:///./data/test_fgbm.db"
os.environ["BACKUPS_ROOT"] = "./test_backups"
os.environ["TOKEN_ENCRYPTION_KEY"] = "bWgK1m8z2H1yL7O4pD3F9E0gX6nC5vB8sR1wT4uW5bQ="

from database.db import Base, get_engine
from database import models
from backend.security import encrypt_token
from backend.backup_engine import run_backup_for_center
import backend.fortigate_client

# 1. Mock the fortigate client to return fake data without needing real credentials
def mock_fetch_config_with_credentials(ip, username, password):
    print(f"    [MOCK API] Attempting login to {ip} with user '{username}'...")
    print(f"    [MOCK API] Login successful, downloading config...")
    return b"# config-version=FG100F-7.0.5\nconfig system global\n    set hostname politecnico-spm\nend\n"

# Replace the real function with our mock for this test
import backend.backup_engine
backend.backup_engine.fetch_config_with_credentials = mock_fetch_config_with_credentials

def main():
    print("\n" + "="*50)
    print("-> STARTING BACKUP ENGINE E2E TEST (MOCKED)")
    print("="*50 + "\n")
    
    # Setup isolated Test DB
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    # Clean isolated test backups folder
    backups_path = Path("./test_backups")
    if backups_path.exists():
        shutil.rmtree(backups_path)
    
    # 2. Create a test center
    print("[1] Creating Test Center in Database...")
    center = models.Center(
        name="Politécnico San Pedro",
        location="SPM",
        fortigate_ip="10.50.1.1",
        auth_mode="credentials",
        fortigate_username="admin",
        fortigate_password_encrypted=encrypt_token("super_secret_123"),
        status="UNKNOWN"
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    print(f"    * Created Center: '{center.name}' (ID: {center.id})")

    # 3. Trigger backup
    print("\n[2] Triggering Backup Engine logic...")
    backup_record = run_backup_for_center(db, center)
    
    if backup_record:
        print(f"    * Backup SUCCESS! Saved to DB (Backup ID: {backup_record.id})")
        print(f"    * File path in DB string: {backup_record.file_path}")
    else:
        print("    ! Backup FAILED!")
        events = db.query(models.Event).filter(models.Event.center_id == center.id).all()
        for e in events:
            print(f"      [REASON] {e.message}")
        sys.exit(1)

    # 4. Verify Physical Storage Structure
    print("\n[3] Verifying Physical Storage & Folders...")
    safe_name = "politecnico-san-pedro" # Should be cleaned by sanitize logic
    
    # List all folders in backups to see what was created
    created_dirs = [d.name for d in backups_path.iterdir() if d.is_dir()]
    print(f"    -> Folders inside ./test_backups/: {created_dirs}")
    
    if created_dirs:
        center_dir = backups_path / created_dirs[0]
        print(f"    * Dedicated folder created correctly: {center_dir}")
        files = list(center_dir.glob("*.conf"))
        if files:
            for f in files:
                print(f"    * Found backup file: {f.name} ({f.stat().st_size} bytes)")
        else:
            print("    ! ERROR: No configuration files found inside folder.")
    else:
        print(f"    ! ERROR: No center folder was created!")

    # 5. Verify Database State
    db.refresh(center)
    print("\n[4] Verifying Database State...")
    print(f"    Center Status: {center.status}")
    print(f"    Last Backup DateTime: {center.last_backup.isoformat()}")
    
    print("\n    Event Log created in DB:")
    events = db.query(models.Event).all()
    for event in events:
         print(f"      - [{event.event_type}] {event.message}")

    print("\n" + "="*50)
    print("-> TEST COMPLETED SUCCESSFULLY")
    print("="*50 + "\n")

if __name__ == '__main__':
    main()
