import sqlite3
import os
import csv
from datetime import datetime
from typing import Optional, List, Dict

class ApplicationTracker:
    def __init__(self, db_path: str = "data/applications.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE,
                    job_title TEXT,
                    company TEXT,
                    location TEXT,
                    job_url TEXT,
                    query_keyword TEXT,
                    applied_date TIMESTAMP,
                    status TEXT, -- 'APPLIED', 'FAILED', 'SKIPPED_MANUAL_QUESTIONS'
                    notes TEXT
                )
            """)
            conn.commit()

    def is_already_applied(self, job_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def record_application(
        self,
        job_id: str,
        job_title: str,
        company: str,
        location: str,
        job_url: str,
        query_keyword: str,
        status: str = "APPLIED",
        notes: str = ""
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO applications 
                (job_id, job_title, company, location, job_url, query_keyword, applied_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                job_title,
                company,
                location,
                job_url,
                query_keyword,
                datetime.now().isoformat(),
                status,
                notes
            ))
            conn.commit()

    def get_stats(self) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
            rows = cursor.fetchall()
            stats = {status: count for status, count in rows}
            cursor.execute("SELECT COUNT(*) FROM applications")
            stats["TOTAL"] = cursor.fetchone()[0]
            return stats

    def export_to_csv(self, output_csv_path: str = "data/applied_jobs_report.csv"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_title, company, location, applied_date, status, job_url, query_keyword FROM applications ORDER BY applied_date DESC")
            rows = cursor.fetchall()

        with open(output_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Puesto", "Empresa", "Ubicación", "Fecha de Postulación", "Estado", "Enlace de Empleo", "Palabra Clave"])
            writer.writerows(rows)
        return output_csv_path
