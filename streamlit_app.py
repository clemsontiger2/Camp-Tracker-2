from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

APP_TITLE = "Summer Camp Milestone Tracker"
DEFAULT_DB_PATH = Path("camp_tracker.db")
ROLE_ORDER = {"student": 0, "teacher": 1, "admin": 2}
STATUSES = ["Not started", "In progress", "Complete"]


st.set_page_config(page_title=APP_TITLE, page_icon="🏕️", layout="wide")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def get_secret_list(name: str) -> list[str]:
    value = get_secret(name, [])
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    return [str(item).strip().lower() for item in value]


@st.cache_resource
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def execute(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    conn = get_connection(str(get_secret("database_path", DEFAULT_DB_PATH)))
    cursor = conn.execute(query, params)
    conn.commit()
    return cursor


def query_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = get_connection(str(get_secret("database_path", DEFAULT_DB_PATH)))
    return conn.execute(query, params).fetchall()


def query_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = get_connection(str(get_secret("database_path", DEFAULT_DB_PATH)))
    return conn.execute(query, params).fetchone()


def init_db() -> None:
    execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            camp_group TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(created_by) REFERENCES users(email)
        )
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS student_milestones (
            student_email TEXT NOT NULL,
            milestone_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Not started',
            notes TEXT DEFAULT '',
            completed_at TEXT,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(student_email, milestone_id),
            FOREIGN KEY(student_email) REFERENCES users(email),
            FOREIGN KEY(milestone_id) REFERENCES milestones(id),
            FOREIGN KEY(updated_by) REFERENCES users(email)
        )
        """
    )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def default_role_for(email: str) -> str:
    admin_emails = set(get_secret_list("admin_emails"))
    teacher_emails = set(get_secret_list("teacher_emails"))
    if email in admin_emails:
        return "admin"
    if email in teacher_emails:
        return "teacher"
    if not query_one("SELECT email FROM users LIMIT 1"):
        return "admin"
    return "student"


def get_or_create_user(email: str, name: str) -> sqlite3.Row:
    email = normalize_email(email)
    existing = query_one("SELECT * FROM users WHERE email = ?", (email,))
    if existing:
        execute(
            "UPDATE users SET name = ?, updated_at = ? WHERE email = ?",
            (name or existing["name"], utc_now(), email),
        )
    else:
        now = utc_now()
        execute(
            "INSERT INTO users (email, name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (email, name or email, default_role_for(email), now, now),
        )
    return query_one("SELECT * FROM users WHERE email = ?", (email,))


def require_role(user: sqlite3.Row, minimum_role: str) -> bool:
    return ROLE_ORDER[user["role"]] >= ROLE_ORDER[minimum_role]


def get_auth_user() -> dict[str, str] | None:
    if "demo_user" in st.session_state:
        return st.session_state.demo_user

    streamlit_user = getattr(st, "user", None)
    if streamlit_user is not None and getattr(streamlit_user, "is_logged_in", False):
        return {
            "email": normalize_email(streamlit_user.get("email", "")),
            "name": streamlit_user.get("name", streamlit_user.get("email", "Camper")),
        }
    return None


def render_login() -> None:
    st.title(f"🏕️ {APP_TITLE}")
    st.write("Track each camper's summer milestones with student, teacher, and admin dashboards.")

    login_col, demo_col = st.columns(2)
    with login_col:
        st.subheader("Google sign-in")
        st.write(
            "Configure Streamlit OIDC secrets with Google as the provider, then students can sign in "
            "with their Gmail or Google Workspace accounts."
        )
        if hasattr(st, "login"):
            if st.button("Sign in with Google", type="primary"):
                try:
                    st.login()
                except Exception as exc:
                    st.error(f"Google login is not configured yet: {exc}")
        else:
            st.warning("Upgrade Streamlit to use built-in Google/OIDC login.")

    with demo_col:
        st.subheader("Local demo mode")
        st.write("Use this while developing locally before Google OAuth is configured.")
        with st.form("demo_login"):
            email = st.text_input("Email", placeholder="teacher@example.com")
            name = st.text_input("Name", placeholder="Camp Teacher")
            submitted = st.form_submit_button("Continue in demo mode")
            if submitted:
                if not email or "@" not in email:
                    st.error("Enter a valid email address.")
                else:
                    st.session_state.demo_user = {
                        "email": normalize_email(email),
                        "name": name.strip() or email,
                    }
                    st.rerun()


def render_sidebar(current_user: sqlite3.Row) -> None:
    st.sidebar.title("🏕️ Camp Tracker")
    st.sidebar.write(f"**{current_user['name']}**")
    st.sidebar.caption(current_user["email"])
    st.sidebar.markdown(f"**Role:** `{current_user['role'].title()}`")

    if st.sidebar.button("Log out"):
        st.session_state.pop("demo_user", None)
        if hasattr(st, "logout") and getattr(getattr(st, "user", None), "is_logged_in", False):
            st.logout()
        st.rerun()


def metrics_for_student(email: str) -> tuple[int, int, int]:
    rows = query_all(
        """
        SELECT status, COUNT(*) AS count
        FROM student_milestones
        WHERE student_email = ?
        GROUP BY status
        """,
        (email,),
    )
    counts = {row["status"]: row["count"] for row in rows}
    total = sum(counts.values())
    complete = counts.get("Complete", 0)
    in_progress = counts.get("In progress", 0)
    return total, complete, in_progress


def milestone_rows_for_student(email: str) -> list[sqlite3.Row]:
    return query_all(
        """
        SELECT m.id, m.title, m.description, sm.status, sm.notes, sm.completed_at, sm.updated_at, sm.updated_by
        FROM student_milestones sm
        JOIN milestones m ON sm.milestone_id = m.id
        WHERE sm.student_email = ? AND m.archived = 0
        ORDER BY sm.status = 'Complete', m.title
        """,
        (email,),
    )


def render_student_dashboard(current_user: sqlite3.Row) -> None:
    st.header("My milestones")
    total, complete, in_progress = metrics_for_student(current_user["email"])
    remaining = max(total - complete, 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Assigned", total)
    col2.metric("Complete", complete)
    col3.metric("In progress", in_progress)
    col4.metric("Remaining", remaining)

    if total:
        st.progress(complete / total, text=f"{complete} of {total} milestones complete")
    else:
        st.info("No milestones assigned yet. Check back after a teacher adds milestones for you.")

    rows = milestone_rows_for_student(current_user["email"])
    if rows:
        st.dataframe(
            pd.DataFrame([dict(row) for row in rows]).drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )


def list_students() -> list[sqlite3.Row]:
    return query_all("SELECT * FROM users WHERE role = 'student' ORDER BY name, email")


def list_milestones(include_archived: bool = False) -> list[sqlite3.Row]:
    if include_archived:
        return query_all("SELECT * FROM milestones ORDER BY archived, title")
    return query_all("SELECT * FROM milestones WHERE archived = 0 ORDER BY title")


def assign_milestone(student_email: str, milestone_id: int, updated_by: str) -> None:
    now = utc_now()
    execute(
        """
        INSERT OR IGNORE INTO student_milestones
            (student_email, milestone_id, status, updated_by, updated_at)
        VALUES (?, ?, 'Not started', ?, ?)
        """,
        (student_email, milestone_id, updated_by, now),
    )


def render_teacher_dashboard(current_user: sqlite3.Row) -> None:
    st.header("Teacher tools")
    students = list_students()
    milestones = list_milestones()

    create_tab, assign_tab, progress_tab = st.tabs(
        ["Create milestones", "Assign milestones", "Update progress"]
    )

    with create_tab:
        st.subheader("Create a new milestone")
        with st.form("create_milestone"):
            title = st.text_input("Milestone title", placeholder="Swim 25 yards")
            description = st.text_area("Description", placeholder="What should the student do to earn this milestone?")
            submitted = st.form_submit_button("Add milestone", type="primary")
            if submitted:
                if not title.strip():
                    st.error("Milestone title is required.")
                else:
                    execute(
                        "INSERT INTO milestones (title, description, created_by, created_at) VALUES (?, ?, ?, ?)",
                        (title.strip(), description.strip(), current_user["email"], utc_now()),
                    )
                    st.success(f"Added milestone: {title.strip()}")
                    st.rerun()

        st.subheader("Current milestones")
        if milestones:
            st.dataframe(pd.DataFrame([dict(row) for row in milestones]), use_container_width=True, hide_index=True)
        else:
            st.info("No milestones have been created yet.")

    with assign_tab:
        st.subheader("Assign milestones to students")
        if not students:
            st.info("No student accounts exist yet. Students are created the first time they sign in.")
        elif not milestones:
            st.info("Create at least one milestone before assigning it.")
        else:
            student_options = {f"{row['name']} ({row['email']})": row["email"] for row in students}
            milestone_options = {row["title"]: row["id"] for row in milestones}
            with st.form("assign_milestone"):
                selected_students = st.multiselect("Students", list(student_options.keys()))
                selected_milestones = st.multiselect("Milestones", list(milestone_options.keys()))
                submitted = st.form_submit_button("Assign selected milestones", type="primary")
                if submitted:
                    if not selected_students or not selected_milestones:
                        st.error("Choose at least one student and one milestone.")
                    else:
                        for student_label in selected_students:
                            for milestone_label in selected_milestones:
                                assign_milestone(
                                    student_options[student_label],
                                    milestone_options[milestone_label],
                                    current_user["email"],
                                )
                        st.success("Milestones assigned.")
                        st.rerun()

    with progress_tab:
        st.subheader("Update student progress")
        if not students:
            st.info("No students found.")
            return
        student_options = {f"{row['name']} ({row['email']})": row["email"] for row in students}
        selected_student = st.selectbox("Student", list(student_options.keys()))
        student_email = student_options[selected_student]
        assigned = milestone_rows_for_student(student_email)
        if not assigned:
            st.info("This student does not have assigned milestones yet.")
            return

        for row in assigned:
            with st.expander(row["title"], expanded=row["status"] != "Complete"):
                st.write(row["description"] or "No description provided.")
                with st.form(f"progress_{student_email}_{row['id']}"):
                    status = st.selectbox(
                        "Status",
                        STATUSES,
                        index=STATUSES.index(row["status"]),
                        key=f"status_{student_email}_{row['id']}",
                    )
                    notes = st.text_area("Teacher notes", value=row["notes"] or "")
                    submitted = st.form_submit_button("Save progress")
                    if submitted:
                        completed_at = utc_now() if status == "Complete" else None
                        if status == "Complete" and row["completed_at"]:
                            completed_at = row["completed_at"]
                        execute(
                            """
                            UPDATE student_milestones
                            SET status = ?, notes = ?, completed_at = ?, updated_by = ?, updated_at = ?
                            WHERE student_email = ? AND milestone_id = ?
                            """,
                            (
                                status,
                                notes.strip(),
                                completed_at,
                                current_user["email"],
                                utc_now(),
                                student_email,
                                row["id"],
                            ),
                        )
                        st.success("Progress saved.")
                        st.rerun()


def render_admin_dashboard(current_user: sqlite3.Row) -> None:
    st.header("Admin")
    user_tab, milestone_tab = st.tabs(["Manage users", "Archive milestones"])

    with user_tab:
        users = query_all("SELECT * FROM users ORDER BY role DESC, name, email")
        if not users:
            st.info("No users found.")
            return
        st.dataframe(pd.DataFrame([dict(row) for row in users]), use_container_width=True, hide_index=True)
        selected = st.selectbox("User", [f"{row['name']} ({row['email']})" for row in users])
        selected_email = selected.rsplit("(", 1)[1].rstrip(")")
        selected_user = query_one("SELECT * FROM users WHERE email = ?", (selected_email,))
        with st.form("update_user"):
            role = st.selectbox("Role", list(ROLE_ORDER.keys()), index=list(ROLE_ORDER.keys()).index(selected_user["role"]))
            camp_group = st.text_input("Camp group", value=selected_user["camp_group"] or "")
            submitted = st.form_submit_button("Update user")
            if submitted:
                execute(
                    "UPDATE users SET role = ?, camp_group = ?, updated_at = ? WHERE email = ?",
                    (role, camp_group.strip(), utc_now(), selected_email),
                )
                st.success("User updated.")
                st.rerun()

    with milestone_tab:
        milestones = list_milestones(include_archived=True)
        if not milestones:
            st.info("No milestones found.")
            return
        for row in milestones:
            col1, col2, col3 = st.columns([4, 2, 1])
            col1.write(f"**{row['title']}**")
            col2.write("Archived" if row["archived"] else "Active")
            if col3.button("Restore" if row["archived"] else "Archive", key=f"archive_{row['id']}"):
                execute("UPDATE milestones SET archived = ? WHERE id = ?", (0 if row["archived"] else 1, row["id"]))
                st.rerun()


def main() -> None:
    init_db()
    auth_user = get_auth_user()
    if not auth_user:
        render_login()
        return

    current_user = get_or_create_user(auth_user["email"], auth_user["name"])
    render_sidebar(current_user)

    st.title(f"🏕️ {APP_TITLE}")
    st.caption("A simple camp portal for milestone assignments, progress, and completion tracking.")

    tabs = ["Student dashboard"]
    if require_role(current_user, "teacher"):
        tabs.append("Teacher dashboard")
    if require_role(current_user, "admin"):
        tabs.append("Admin dashboard")

    selected_tabs = st.tabs(tabs)
    with selected_tabs[0]:
        render_student_dashboard(current_user)
    if "Teacher dashboard" in tabs:
        with selected_tabs[tabs.index("Teacher dashboard")]:
            render_teacher_dashboard(current_user)
    if "Admin dashboard" in tabs:
        with selected_tabs[tabs.index("Admin dashboard")]:
            render_admin_dashboard(current_user)


if __name__ == "__main__":
    main()
