"""SQLite persistence helpers for the Summer Camp Milestone Tracker."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("camp_tracker.db")
VALID_ROLES = {"student", "teacher", "admin"}
VALID_STATUSES = {"Not Started", "In Progress", "Completed"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def init_db() -> None:
    """Create the tracker database if it does not already exist."""
    with closing(get_connection()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users(email)
            );

            CREATE TABLE IF NOT EXISTS student_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_email TEXT NOT NULL,
                milestone_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Not Started',
                notes TEXT NOT NULL DEFAULT '',
                assigned_by TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                completed_at TEXT,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(student_email, milestone_id),
                FOREIGN KEY (student_email) REFERENCES users(email),
                FOREIGN KEY (milestone_id) REFERENCES milestones(id),
                FOREIGN KEY (assigned_by) REFERENCES users(email),
                FOREIGN KEY (updated_by) REFERENCES users(email)
            );
            """
        )
        conn.commit()


def ensure_user(email: str, name: str, admin_emails: Iterable[str] = ()) -> dict[str, Any]:
    """Create or update a user and return the stored record."""
    normalized_email = email.strip().lower()
    clean_name = name.strip() or normalized_email
    if not normalized_email:
        raise ValueError("Email is required")

    now = _utc_now()
    admin_email_set = {item.strip().lower() for item in admin_emails if item.strip()}

    with closing(get_connection()) as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()
        if existing is None:
            role = "admin" if normalized_email in admin_email_set else "student"
            conn.execute(
                """
                INSERT INTO users (email, name, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_email, clean_name, role, now, now),
            )
        else:
            role = existing["role"]
            if normalized_email in admin_email_set and role != "admin":
                role = "admin"
            conn.execute(
                """
                UPDATE users
                SET name = ?, role = ?, updated_at = ?
                WHERE email = ?
                """,
                (clean_name, role, now, normalized_email),
            )
        conn.commit()
        return get_user(normalized_email)


def get_user(email: str) -> dict[str, Any]:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        raise LookupError(f"User not found: {email}")
    return _row_to_dict(row)


def list_users() -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT email, name, role, created_at, updated_at FROM users ORDER BY name, email"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_students() -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT email, name, role, created_at, updated_at
            FROM users
            WHERE role = 'student'
            ORDER BY name, email
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_user_role(email: str, role: str) -> None:
    if role not in VALID_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE email = ?",
            (role, _utc_now(), email),
        )
        conn.commit()


def create_milestone(title: str, description: str, created_by: str) -> None:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Milestone title is required")
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO milestones (title, description, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (clean_title, description.strip(), created_by, _utc_now()),
        )
        conn.commit()


def list_milestones() -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.title, m.description, m.created_by, m.created_at,
                   u.name AS creator_name
            FROM milestones m
            LEFT JOIN users u ON u.email = m.created_by
            ORDER BY m.created_at DESC, m.title
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def assign_milestone(student_email: str, milestone_id: int, assigned_by: str) -> None:
    now = _utc_now()
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO student_milestones (
                student_email, milestone_id, status, notes, assigned_by,
                assigned_at, completed_at, updated_by, updated_at
            )
            VALUES (?, ?, 'Not Started', '', ?, ?, NULL, ?, ?)
            """,
            (student_email, milestone_id, assigned_by, now, assigned_by, now),
        )
        conn.commit()


def list_student_milestones(student_email: str) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT sm.id, sm.student_email, sm.milestone_id, sm.status, sm.notes,
                   sm.assigned_by, sm.assigned_at, sm.completed_at, sm.updated_by,
                   sm.updated_at, m.title, m.description
            FROM student_milestones sm
            JOIN milestones m ON m.id = sm.milestone_id
            WHERE sm.student_email = ?
            ORDER BY CASE sm.status
                WHEN 'Completed' THEN 3
                WHEN 'In Progress' THEN 2
                ELSE 1
            END, m.title
            """,
            (student_email,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_all_student_milestones() -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT sm.id, sm.student_email, u.name AS student_name, sm.status,
                   sm.notes, sm.completed_at, sm.updated_at, m.title
            FROM student_milestones sm
            JOIN users u ON u.email = sm.student_email
            JOIN milestones m ON m.id = sm.milestone_id
            ORDER BY u.name, m.title
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_student_milestone(
    assignment_id: int,
    status: str,
    notes: str,
    updated_by: str,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    completed_at = _utc_now() if status == "Completed" else None
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE student_milestones
            SET status = ?, notes = ?, completed_at = ?, updated_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, notes.strip(), completed_at, updated_by, _utc_now(), assignment_id),
        )
        conn.commit()
