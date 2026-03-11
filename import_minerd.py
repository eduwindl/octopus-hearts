import pandas as pd
from database.db import SessionLocal, get_engine, Base
from database.models import Center
from pathlib import Path
import os
import sys

def init_env():
    import desktop_app
    base_dir = desktop_app.get_app_dir()
    desktop_app.init_environment(base_dir)

def run():
    init_env()
    
    excel_path = Path("Excel_Centros_Minerd") / "Fortigate Backup Minerd Data.xlsx"
    if not excel_path.exists():
        print(f"Error: {excel_path} does not exist.")
        return

    df = pd.read_excel(excel_path)
    
    db = SessionLocal()
    count_added = 0
    count_skipped = 0
    seen_ips = set()
    
    for idx, row in df.iterrows():
        name = str(row.get('Account Name', '')).strip()
        ip = str(row.get('WAN IP', '')).strip()
        
        if not name or name == 'nan':
            name = f"Minerd_Center_{idx}"
        if not ip or ip == 'nan':
            count_skipped += 1
            continue
            
        location = str(row.get('City', 'Desconocido')).strip()
        if location == 'nan': location = 'Desconocido'
        
        model = str(row.get('Tipo de centro', '')).strip()
        if model == 'nan': model = ''

        # We will use the Distito or other fields if needed, but the basic form is enough.
        
        # Since session isn't flushed between adds, also track in memory
        if ip in seen_ips:
            continue
            
        existing = db.query(Center).filter(
            (Center.fortigate_ip == ip) | (Center.name == name)
        ).first()
        
        if not existing:
            c = Center(
                name=name,
                location=location,
                fortigate_ip=ip,
                model=model,
                tag='minerd',
                auth_mode='credentials', # Prepare for mass credentials update
                status='UNKNOWN'
            )
            db.add(c)
            seen_ips.add(ip)
            count_added += 1
        else:
            seen_ips.add(ip)
            # Maybe it already exists, tag it if it's not tagged
            if not existing.tag:
                existing.tag = 'minerd'
                existing.auth_mode = 'credentials'
                count_added += 1
                
    db.commit()
    db.close()
    
    print(f"Successfully added or updated {count_added} centers. Skipped {count_skipped} without IP.")

if __name__ == '__main__':
    run()
