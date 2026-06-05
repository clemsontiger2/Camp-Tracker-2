# 🏕️ Summer Camp Milestone Tracker

A Streamlit app for tracking student milestones during summer camp. Students can sign in, view their assigned milestones, and see progress. Teachers and admins can create milestones, assign them to students, and update completion status.

## Features

- Google/OIDC-ready sign-in through Streamlit authentication
- Local development login fallback when Google auth is not configured
- SQLite persistence for users, roles, milestones, and student progress
- Student dashboard with progress tracking
- Teacher tools to create, assign, and update milestones
- Admin tools to promote users to student, teacher, or admin roles

## How to run locally

1. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:

   ```bash
   streamlit run streamlit_app.py
   ```

3. If you have not configured Google login yet, use the development login form. The default development email is `admin@example.com`.

## Configure Google login

The app uses Streamlit's built-in OpenID Connect support with Google as the identity provider.

1. Create a Google OAuth client in Google Cloud Console.
2. Add this authorized redirect URI for local development:

   ```text
   http://localhost:8501/oauth2callback
   ```

3. Copy the example secrets file:

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

4. Fill in your real Google OAuth client values in `.streamlit/secrets.toml`:

   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "replace-with-a-long-random-string"
   client_id = "replace-with-google-oauth-client-id"
   client_secret = "replace-with-google-oauth-client-secret"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

5. Add initial admin accounts:

   ```toml
   [app]
   admin_emails = ["your-admin@gmail.com"]
   ```

Do not commit `.streamlit/secrets.toml` with real credentials.

## Roles

| Role | Permissions |
| --- | --- |
| Student | View assigned milestones and progress |
| Teacher | Create milestones, assign milestones, and update student progress |
| Admin | All teacher permissions plus user role management |

New users default to `student` unless their email appears in `app.admin_emails` in Streamlit secrets.

## Data storage

The app stores data in a local SQLite database named `camp_tracker.db`. This is convenient for local development and small deployments. For a larger production deployment, consider migrating the storage layer to a managed database such as Supabase/PostgreSQL.

## Deployment notes

When deploying, update both your Google OAuth client and `.streamlit/secrets.toml` so the redirect URI matches your deployed app URL:

```text
https://your-app-url/oauth2callback
```
