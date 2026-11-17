# Deploying LocalScout on Render

The Render Blueprint is in `render.yaml`. The repository pins Python 3.13 because the dependency set is not compatible with Render's newer default Python yet. Before deploying, create these free-tier accounts/services:

- A PostgreSQL database (for example, Neon). Copy its connection URL to Render's `DATABASE_URL`.
- A Cloudinary account. Set `CLOUDINARY_URL` to its credential URL so uploaded images survive Render restarts and deploys.
- A Resend account with a verified sending domain. Set `RESEND_API_KEY` and `DEFAULT_FROM_EMAIL` to the verified sender.

Connect the repository to Render and create a Blueprint from `render.yaml`. Set the remaining environment variables in the Render dashboard:

- `DJANGO_SECRET`: a newly generated Django secret key.
- `DJANGO_ALLOWED_HOSTS`: comma-separated Render hostname and custom domain, for example `localscout.onrender.com,example.com,www.example.com`.
- `CSRF_TRUSTED_ORIGINS`: comma-separated HTTPS origins, for example `https://localscout.onrender.com,https://example.com,https://www.example.com`.
- `GOOGLE_CLIENT_ID` is optional; set it only when configuring Google sign-in.

The build command installs dependencies and collects static files. The start command applies migrations before starting Gunicorn. Add the custom domain in Render, then configure the DNS records Render provides at your domain registrar. Do not remove unrelated DNS or email records.

Render's free web service can sleep when idle, and its filesystem is temporary. The app uses external PostgreSQL and Cloudinary storage to avoid losing database records and uploaded images. Free-tier services have usage limits and are best suited to demos and hobby projects.

The deployed database starts empty. Existing records in the local SQLite database and files in local `backend/media` are not copied automatically.

### Create the first admin on the Free plan

The Render Shell is not available on the Free plan. To create a Django superuser without the Shell, add these temporary environment variables to the web service in the Render dashboard:

- `DJANGO_BOOTSTRAP_ADMIN_USERNAME`
- `DJANGO_BOOTSTRAP_ADMIN_EMAIL`
- `DJANGO_BOOTSTRAP_ADMIN_PASSWORD`

Set all three, using a unique username and a strong password that passes the configured Django password validators. Saving the variables restarts the service; its startup command creates the superuser if that username does not already belong to a superuser. It never promotes an existing regular account or changes an existing superuser's password. After the deploy succeeds, delete all three temporary variables from Render and log in at `/admin/` with the username and password you chose. Never put these credentials in source code or share them in chat.
