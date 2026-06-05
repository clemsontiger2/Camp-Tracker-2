from __future__ import annotations

import streamlit as st

from storage import (
    VALID_ROLES,
    VALID_STATUSES,
    assign_milestone,
    create_milestone,
    ensure_user,
    init_db,
    list_all_student_milestones,
    list_milestones,
    list_student_milestones,
    list_students,
    list_users,
    update_student_milestone,
    update_user_role,
)

st.set_page_config(page_title="Summer Camp Milestone Tracker", page_icon="🏕️", layout="wide")


def get_secret_list(section: str, key: str) -> list[str]:
    try:
        value = st.secrets.get(section, {}).get(key, [])
    except Exception:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def auth_is_configured() -> bool:
    try:
        auth_config = st.secrets.get("auth", {})
    except Exception:
        return False
    return bool(auth_config.get("client_id") and auth_config.get("client_secret"))


def get_streamlit_user() -> dict[str, str] | None:
    user = getattr(st, "user", None)
    if user is None or not getattr(user, "is_logged_in", False):
        return None
    email = getattr(user, "email", "") or user.get("email", "")
    name = getattr(user, "name", "") or user.get("name", "") or email
    return {"email": email, "name": name}


def render_login() -> dict[str, str] | None:
    st.title("🏕️ Summer Camp Milestone Tracker")
    st.write("Track student camp milestones with student, teacher, and admin views.")

    if auth_is_configured():
        st.info("Use your Google account to continue.")
        st.button("Log in with Google", on_click=st.login, type="primary")
        return get_streamlit_user()

    st.warning(
        "Google login is not configured yet. Use development login locally, then add "
        "`.streamlit/secrets.toml` for Google/OIDC before sharing the app."
    )
    with st.form("dev_login"):
        email = st.text_input("Email", value="admin@example.com")
        name = st.text_input("Name", value="Camp Admin")
        submitted = st.form_submit_button("Continue in development mode", type="primary")
    if submitted:
        st.session_state["dev_user"] = {"email": email.strip().lower(), "name": name.strip() or email}
        st.rerun()
    return st.session_state.get("dev_user")


def render_sidebar(user: dict[str, str]) -> None:
    st.sidebar.header("Signed in")
    st.sidebar.write(user["name"])
    st.sidebar.caption(user["email"])
    if auth_is_configured():
        st.sidebar.button("Log out", on_click=st.logout)
    elif st.sidebar.button("Log out"):
        st.session_state.pop("dev_user", None)
        st.rerun()


def render_student_dashboard(current_user: dict[str, str], selected_student_email: str | None = None) -> None:
    student_email = selected_student_email or current_user["email"]
    assignments = list_student_milestones(student_email)

    st.subheader("Student Milestones")
    if not assignments:
        st.info("No milestones have been assigned yet.")
        return

    completed = sum(1 for item in assignments if item["status"] == "Completed")
    st.progress(completed / len(assignments), text=f"{completed} of {len(assignments)} milestones completed")

    for assignment in assignments:
        with st.container(border=True):
            cols = st.columns([2, 1])
            cols[0].markdown(f"### {assignment['title']}")
            cols[1].metric("Status", assignment["status"])
            if assignment["description"]:
                st.write(assignment["description"])
            if assignment["notes"]:
                st.caption(f"Teacher notes: {assignment['notes']}")
            if assignment["completed_at"]:
                st.success(f"Completed at {assignment['completed_at']}")


def render_teacher_dashboard(current_user: dict[str, str]) -> None:
    st.subheader("Teacher/Admin Dashboard")
    students = list_students()
    milestones = list_milestones()

    create_tab, assign_tab, update_tab, overview_tab = st.tabs(
        ["Create milestone", "Assign milestone", "Update progress", "Overview"]
    )

    with create_tab:
        with st.form("create_milestone"):
            title = st.text_input("Milestone title", placeholder="Swim 25 yards")
            description = st.text_area("Description", placeholder="Optional details for students and teachers")
            submitted = st.form_submit_button("Create milestone", type="primary")
        if submitted:
            try:
                create_milestone(title, description, current_user["email"])
                st.success("Milestone created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with assign_tab:
        if not students:
            st.info("Students will appear here after they log in for the first time.")
        elif not milestones:
            st.info("Create at least one milestone before assigning it.")
        else:
            student_options = {f"{student['name']} ({student['email']})": student["email"] for student in students}
            milestone_options = {f"{milestone['title']} #{milestone['id']}": milestone["id"] for milestone in milestones}
            with st.form("assign_milestone"):
                student_label = st.selectbox("Student", list(student_options))
                milestone_label = st.selectbox("Milestone", list(milestone_options))
                submitted = st.form_submit_button("Assign milestone", type="primary")
            if submitted:
                assign_milestone(
                    student_options[student_label],
                    milestone_options[milestone_label],
                    current_user["email"],
                )
                st.success("Milestone assigned.")
                st.rerun()

    with update_tab:
        if not students:
            st.info("No student accounts yet.")
        else:
            student_options = {f"{student['name']} ({student['email']})": student["email"] for student in students}
            selected_label = st.selectbox("Choose a student to update", list(student_options), key="update_student")
            selected_email = student_options[selected_label]
            assignments = list_student_milestones(selected_email)
            if not assignments:
                st.info("This student has no assigned milestones.")
            for assignment in assignments:
                with st.form(f"assignment_{assignment['id']}"):
                    st.markdown(f"#### {assignment['title']}")
                    status = st.selectbox(
                        "Status",
                        sorted(VALID_STATUSES),
                        index=sorted(VALID_STATUSES).index(assignment["status"]),
                        key=f"status_{assignment['id']}",
                    )
                    notes = st.text_area("Notes", value=assignment["notes"], key=f"notes_{assignment['id']}")
                    submitted = st.form_submit_button("Save progress")
                if submitted:
                    update_student_milestone(assignment["id"], status, notes, current_user["email"])
                    st.success("Progress updated.")
                    st.rerun()

    with overview_tab:
        rows = list_all_student_milestones()
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No milestones have been assigned yet.")


def render_admin_dashboard(current_user: dict[str, str]) -> None:
    st.subheader("Admin: User Roles")
    users = list_users()
    if not users:
        st.info("No users found.")
        return

    st.dataframe(users, use_container_width=True, hide_index=True)
    user_options = {f"{user['name']} ({user['email']}) - {user['role']}": user["email"] for user in users}
    with st.form("update_role"):
        selected_user = st.selectbox("User", list(user_options))
        role = st.selectbox("Role", sorted(VALID_ROLES))
        submitted = st.form_submit_button("Update role", type="primary")
    if submitted:
        update_user_role(user_options[selected_user], role)
        st.success("Role updated.")
        st.rerun()


def main() -> None:
    init_db()
    authenticated_user = get_streamlit_user() or render_login()
    if not authenticated_user:
        return

    admin_emails = get_secret_list("app", "admin_emails")
    if not auth_is_configured():
        admin_emails.append("admin@example.com")
    current_user = ensure_user(authenticated_user["email"], authenticated_user["name"], admin_emails)
    render_sidebar(current_user)

    st.title("🏕️ Summer Camp Milestone Tracker")
    st.caption(f"Role: {current_user['role'].title()}")

    if current_user["role"] in {"teacher", "admin"}:
        student_tab, teacher_tab, admin_tab = st.tabs(["My milestones", "Teacher tools", "Admin"])
        with student_tab:
            render_student_dashboard(current_user)
        with teacher_tab:
            render_teacher_dashboard(current_user)
        with admin_tab:
            if current_user["role"] == "admin":
                render_admin_dashboard(current_user)
            else:
                st.info("Admin tools are only available to admins.")
    else:
        render_student_dashboard(current_user)


if __name__ == "__main__":
    main()
