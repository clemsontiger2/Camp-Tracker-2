"""SQLite persistence helpers for the Summer Camp Milestone Tracker."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("camp_tracker.db")


def utc_now() -> str:
    """Return an ISO-formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row dictionaries and foreign keys enabled."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create application tables when they do not already exist."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student'
                    CHECK (role IN ('student', 'teacher', 'admin')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users(email)
            );

            CREATE TABLE IF NOT EXISTS student_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_email TEXT NOT NULL,
                milestone_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Not started'
                    CHECK (status IN ('Not started', 'In progress', 'Completed')),
                notes TEXT,
                completed_at TEXT,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (student_email, milestone_id),
                FOREIGN KEY (student_email) REFERENCES users(email),
                FOREIGN KEY (milestone_id) REFERENCES milestones(id),
                FOREIGN KEY (updated_by) REFERENCES users(email)
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a SQLite row into a plain dictionary."""
    if row is None:
        return None
    return dict(row)


def bootstrap_admin(admin_email: str | None) -> None:
    """Create or promote the configured bootstrap admin email."""
    if not admin_email:
        return

    email = admin_email.strip().lower()
    if not email:
        return

    now = utc_now()
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT email FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE users SET role = 'admin', updated_at = ? WHERE email = ?",
                (now, email),
            )
        else:
            connection.execute(
                """
                INSERT INTO users (email, name, role, created_at, updated_at)
                VALUES (?, ?, 'admin', ?, ?)
                """,
                (email, email.split("@")[0], now, now),
            )


def get_or_create_user(email: str, name: str) -> dict[str, Any]:
    """Fetch a user by email, creating a student record when needed."""
    normalized_email = email.strip().lower()
    display_name = name.strip() or normalized_email.split("@")[0]
    now = utc_now()

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()
        if row is None:
            connection.execute(
                """
                INSERT INTO users (email, name, role, created_at, updated_at)
                VALUES (?, ?, 'student', ?, ?)
                """,
                (normalized_email, display_name, now, now),
            )
        else:
            connection.execute(
                "UPDATE users SET name = ?, updated_at = ? WHERE email = ?",
                (display_name, now, normalized_email),
            )

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()

    result = row_to_dict(user)
    if result is None:
        raise RuntimeError("Unable to create or fetch user")
    return result


def list_users(role: str | None = None) -> list[dict[str, Any]]:
    """List users, optionally filtered by role."""
    with get_connection() as connection:
        if role:
            rows = connection.execute(
                "SELECT * FROM users WHERE role = ? ORDER BY name COLLATE NOCASE",
                (role,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY role, name COLLATE NOCASE"
            ).fetchall()
    return [dict(row) for row in rows]


def update_user_role(email: str, role: str) -> None:
    """Change a user's role."""
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE email = ?",
            (role, now, email),
        )


def create_milestone(title: str, description: str, created_by: str) -> int:
    """Create a reusable milestone and return its id."""
    now = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO milestones (title, description, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), description.strip(), created_by, now),
        )
    return int(cursor.lastrowid)


def list_milestones() -> list[dict[str, Any]]:
    """List all reusable milestones."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT m.*, u.name AS created_by_name
            FROM milestones m
            JOIN users u ON u.email = m.created_by
            ORDER BY m.created_at DESC, m.title COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def assign_milestone(student_email: str, milestone_id: int, updated_by: str) -> None:
    """Assign a milestone to a student if not already assigned."""
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO student_milestones (
                student_email, milestone_id, updated_by, updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (student_email, milestone_id, updated_by, now),
        )


def update_student_milestone(
    assignment_id: int,
    status: str,
    notes: str,
    updated_by: str,
) -> None:
    """Update status and notes for an assigned student milestone."""
    now = utc_now()
    completed_at = now if status == "Completed" else None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE student_milestones
            SET status = ?, notes = ?, completed_at = ?, updated_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, notes.strip(), completed_at, updated_by, now, assignment_id),
        )


def list_student_milestones(student_email: str) -> list[dict[str, Any]]:
    """List all milestone assignments for one student."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                sm.id,
                sm.student_email,
                sm.milestone_id,
                sm.status,
                sm.notes,
                sm.completed_at,
                sm.updated_at,
                sm.updated_by,
                m.title,
                m.description,
                u.name AS updated_by_name
            FROM student_milestones sm
            JOIN milestones m ON m.id = sm.milestone_id
            JOIN users u ON u.email = sm.updated_by
            WHERE sm.student_email = ?
            ORDER BY
                CASE sm.status
                    WHEN 'Completed' THEN 3
                    WHEN 'In progress' THEN 2
                    ELSE 1
                END,
                m.title COLLATE NOCASE
            """,
            (student_email,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_all_assignments() -> list[dict[str, Any]]:
    """List every assigned milestone with student names for admin views."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                sm.id,
                s.name AS student_name,
                sm.student_email,
                m.title,
                sm.status,
                sm.completed_at,
                sm.updated_at,
                sm.notes
            FROM student_milestones sm
            JOIN users s ON s.email = sm.student_email
            JOIN milestones m ON m.id = sm.milestone_id
            ORDER BY s.name COLLATE NOCASE, m.title COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]
