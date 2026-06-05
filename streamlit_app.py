from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from database import (
    assign_milestone,
    bootstrap_admin,
    create_milestone,
    get_or_create_user,
    init_db,
    list_all_assignments,
    list_milestones,
    list_student_milestones,
    list_users,
    update_student_milestone,
    update_user_role,
)

APP_TITLE = "Summer Camp Milestone Tracker"
AUTH_REQUIRED_KEYS = (
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
)
PLACEHOLDER_MARKERS = ("replace-with", "your-", "xxx")
ROLES = ("student", "teacher", "admin")
STATUSES = ("Not started", "In progress", "Completed")

st.set_page_config(page_title=APP_TITLE, page_icon="🏕️", layout="wide")


def get_secret_value(
    *keys: str, default: str | None = None, use_env: bool = False
) -> str | None:
    """Safely read nested Streamlit secrets.

    Streamlit's built-in ``st.login`` only reads OIDC settings from
    ``st.secrets``. Environment fallback is therefore opt-in and used only for
    non-auth app settings such as the bootstrap admin email.
    """
    env_key = "_".join(keys).upper()

    value: object = st.secrets
    for key in keys:
        try:
            has_key = isinstance(value, Mapping) and key in value
        except StreamlitSecretNotFoundError:
            return os.environ.get(env_key, default) if use_env else default

        if has_key:
            value = value[key]
        else:
            return os.environ.get(env_key, default) if use_env else default
    return str(value) if value is not None else default


def is_placeholder_secret(value: str | None) -> bool:
    """Return whether an auth secret is empty or still an example value."""
    if value is None or not value.strip():
        return True
    normalized = value.strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def auth_config_errors() -> list[str]:
    """Return setup problems that would prevent ``st.login`` from working."""
    errors: list[str] = []
    for key in AUTH_REQUIRED_KEYS:
        if is_placeholder_secret(get_secret_value("auth", key)):
            errors.append(f"Missing or placeholder [auth].{key}")

    redirect_uri = get_secret_value("auth", "redirect_uri")
    if redirect_uri and not redirect_uri.startswith(("http://", "https://")):
        errors.append("[auth].redirect_uri must be an absolute http(s) URL")

    metadata_url = get_secret_value("auth", "server_metadata_url")
    if metadata_url and not metadata_url.startswith(("http://", "https://")):
        errors.append("[auth].server_metadata_url must be an absolute http(s) URL")

    if importlib.util.find_spec("authlib") is None:
        errors.append("Authlib is not installed; run `pip install -r requirements.txt`")

    return errors


def oidc_configured() -> bool:
    """Return whether the app has enough valid OIDC settings for st.login."""
    return not auth_config_errors()


def get_demo_user() -> dict[str, str] | None:
    """Return the current local demo user stored in session state."""
    demo_user = st.session_state.get("demo_user")
    if isinstance(demo_user, dict) and demo_user.get("email"):
        return {
            "email": demo_user["email"],
            "name": demo_user.get("name", demo_user["email"]),
        }
    return None


def login_screen() -> None:
    """Render authentication controls for OIDC or local demo mode."""
    st.title(f"🏕️ {APP_TITLE}")
    st.subheader("Track student progress through camp milestones.")
    st.write(
        "Students can sign in with Google/Gmail, while teachers and admins can "
        "assign milestones and update progress."
    )

    auth_errors = auth_config_errors()
    if not auth_errors:
        st.info("Google login is configured for this deployment.")
        st.button("Log in with Google", type="primary", on_click=st.login)
        st.stop()

    st.warning(
        "Google login is not ready, so the app is running in local demo mode. "
        "Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, "
        "fill in real Google OAuth values, and install the requirements to enable Gmail login."
    )
    with st.expander("Google login setup checks"):
        for error in auth_errors:
            st.write(f"- {error}")

    with st.form("demo_login"):
        email = st.text_input("Demo email", value="teacher@example.com")
        name = st.text_input("Display name", value="Camp Teacher")
        st.caption(
            "Tip: use teacher@example.com for teacher tools or "
            "admin@example.com for admin tools."
        )
        submitted = st.form_submit_button("Continue in demo mode", type="primary")

    if submitted:
        if not email or "@" not in email:
            st.error("Enter a valid email address.")
            st.stop()
        st.session_state.demo_user = {
            "email": email.strip().lower(),
            "name": name.strip() or email,
        }
        st.rerun()

    st.stop()


def current_identity() -> dict[str, str]:
    """Resolve the authenticated user from OIDC or local demo mode."""
    if oidc_configured():
        if not st.user.is_logged_in:
            login_screen()
        return {
            "email": str(st.user.email).lower(),
            "name": str(getattr(st.user, "name", st.user.email)),
        }

    demo_user = get_demo_user()
    if demo_user is None:
        login_screen()
    return demo_user


def logout_button() -> None:
    """Render the correct logout button for the active auth mode."""
    if oidc_configured():
        st.sidebar.button("Log out", on_click=st.logout)
    elif st.sidebar.button("Log out of demo mode"):
        st.session_state.pop("demo_user", None)
        st.rerun()


def status_badge(status: str) -> str:
    """Return a human-friendly status label."""
    icons = {
        "Not started": "⚪ Not started",
        "In progress": "🟡 In progress",
        "Completed": "🟢 Completed",
    }
    return icons.get(status, status)


def render_student_dashboard(user: dict[str, str]) -> None:
    """Show milestone progress for the current student."""
    st.header("🎒 My Milestones")
    assignments = list_student_milestones(user["email"])

    if not assignments:
        st.info("No milestones have been assigned yet. Check back after your teacher adds them.")
        return

    completed = sum(1 for assignment in assignments if assignment["status"] == "Completed")
    progress = completed / len(assignments)
    st.progress(progress, text=f"{completed} of {len(assignments)} milestones completed")

    for assignment in assignments:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.subheader(assignment["title"])
                if assignment["description"]:
                    st.write(assignment["description"])
                if assignment["notes"]:
                    st.caption(f"Teacher notes: {assignment['notes']}")
            with cols[1]:
                st.metric("Status", status_badge(assignment["status"]))
                if assignment["completed_at"]:
                    st.caption(f"Completed: {assignment['completed_at']}")


def render_teacher_dashboard(user: dict[str, str]) -> None:
    """Show teacher/admin tools for managing student milestones."""
    st.header("🧑‍🏫 Teacher Dashboard")
    students = list_users("student")
    milestones = list_milestones()

    create_tab, assign_tab, update_tab, overview_tab = st.tabs(
        ["Create milestone", "Assign milestone", "Update progress", "Overview"]
    )

    with create_tab:
        st.subheader("Create a new camp milestone")
        with st.form("create_milestone", clear_on_submit=True):
            title = st.text_input("Milestone title", placeholder="Example: Swim safety check")
            description = st.text_area("Description", placeholder="What should the student complete?")
            submitted = st.form_submit_button("Create milestone", type="primary")
        if submitted:
            if not title.strip():
                st.error("Milestone title is required.")
            else:
                create_milestone(title, description, user["email"])
                st.success("Milestone created.")
                st.rerun()

        if milestones:
            st.dataframe(
                pd.DataFrame(milestones)[["title", "description", "created_by_name", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )

    with assign_tab:
        st.subheader("Assign a milestone to a student")
        if not students:
            st.info("No student accounts exist yet. Students appear here after their first login.")
        elif not milestones:
            st.info("Create at least one milestone before assigning work to students.")
        else:
            student_options = {f"{student['name']} ({student['email']})": student for student in students}
            milestone_options = {milestone["title"]: milestone for milestone in milestones}
            with st.form("assign_milestone"):
                selected_student = st.selectbox("Student", list(student_options))
                selected_milestone = st.selectbox("Milestone", list(milestone_options))
                submitted = st.form_submit_button("Assign milestone", type="primary")
            if submitted:
                assign_milestone(
                    student_options[selected_student]["email"],
                    int(milestone_options[selected_milestone]["id"]),
                    user["email"],
                )
                st.success("Milestone assigned.")
                st.rerun()

    with update_tab:
        st.subheader("Update a student's milestone progress")
        if not students:
            st.info("No students are available yet.")
        else:
            student_options = {f"{student['name']} ({student['email']})": student for student in students}
            selected_student = st.selectbox("Choose a student", list(student_options), key="update_student")
            selected_email = student_options[selected_student]["email"]
            assignments = list_student_milestones(selected_email)

            if not assignments:
                st.info("This student does not have assigned milestones yet.")
            else:
                for assignment in assignments:
                    with st.form(f"assignment_{assignment['id']}"):
                        st.markdown(f"**{assignment['title']}**")
                        status = st.selectbox(
                            "Status",
                            STATUSES,
                            index=STATUSES.index(assignment["status"]),
                            key=f"status_{assignment['id']}",
                        )
                        notes = st.text_area(
                            "Notes",
                            value=assignment["notes"] or "",
                            key=f"notes_{assignment['id']}",
                        )
                        submitted = st.form_submit_button("Save progress")
                    if submitted:
                        update_student_milestone(
                            int(assignment["id"]), status, notes, user["email"]
                        )
                        st.success("Progress updated.")
                        st.rerun()

    with overview_tab:
        st.subheader("All assigned milestones")
        assignments = list_all_assignments()
        if assignments:
            display = pd.DataFrame(assignments)
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("No milestones have been assigned yet.")


def render_admin_dashboard(current_user: dict[str, str]) -> None:
    """Show account role management for admins."""
    st.header("🛠️ Admin Dashboard")
    st.write("Promote trusted staff to teacher/admin or return accounts to student access.")
    users = list_users()

    if not users:
        st.info("No user accounts exist yet.")
        return

    for account in users:
        with st.form(f"role_{account['email']}"):
            cols = st.columns([2, 2, 1])
            cols[0].markdown(f"**{account['name']}**")
            cols[0].caption(account["email"])
            role = cols[1].selectbox(
                "Role",
                ROLES,
                index=ROLES.index(account["role"]),
                key=f"role_select_{account['email']}",
                label_visibility="collapsed",
            )
            disabled = account["email"] == current_user["email"] and role != "admin"
            submitted = cols[2].form_submit_button("Save", disabled=disabled)
        if submitted:
            update_user_role(account["email"], role)
            st.success(f"Updated {account['email']} to {role}.")
            st.rerun()


def render_sidebar(user: dict[str, str], role: str) -> str:
    """Render sidebar profile and navigation."""
    st.sidebar.title("🏕️ Camp Tracker")
    st.sidebar.write(f"**{user['name']}**")
    st.sidebar.caption(user["email"])
    st.sidebar.caption(f"Role: {role.title()}")
    logout_button()

    pages = ["My milestones"]
    if role in {"teacher", "admin"}:
        pages.append("Teacher dashboard")
    if role == "admin":
        pages.append("Admin dashboard")
    return st.sidebar.radio("Go to", pages, key="navigation")


def main() -> None:
    """Run the Streamlit app."""
    init_db()
    bootstrap_admin(get_secret_value("app", "bootstrap_admin_email", use_env=True))

    identity = current_identity()
    user = get_or_create_user(identity["email"], identity["name"])
    if not oidc_configured() and user["email"] in {"teacher@example.com", "admin@example.com"}:
        demo_role = "admin" if user["email"] == "admin@example.com" else "teacher"
        if user["role"] != demo_role:
            update_user_role(user["email"], demo_role)
            user["role"] = demo_role

    st.title(f"🏕️ {APP_TITLE}")
    page = render_sidebar({"email": user["email"], "name": user["name"]}, user["role"])

    if page == "My milestones":
        render_student_dashboard({"email": user["email"], "name": user["name"]})
    elif page == "Teacher dashboard" and user["role"] in {"teacher", "admin"}:
        render_teacher_dashboard({"email": user["email"], "name": user["name"]})
    elif page == "Admin dashboard" and user["role"] == "admin":
        render_admin_dashboard({"email": user["email"], "name": user["name"]})
    else:
        st.error("You do not have access to that page.")


if __name__ == "__main__":
    main()
