import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser from temporary environment variables, if absent."

    variable_names = (
        "DJANGO_BOOTSTRAP_ADMIN_USERNAME",
        "DJANGO_BOOTSTRAP_ADMIN_EMAIL",
        "DJANGO_BOOTSTRAP_ADMIN_PASSWORD",
    )

    def handle(self, *args, **options):
        username, email, password = (
            os.environ.get(name, "") for name in self.variable_names
        )

        if not any((username, email, password)):
            self.stdout.write("Admin bootstrap is not configured; skipping.")
            return

        username = username.strip()
        email = email.strip()
        if not all((username, email, password)):
            raise CommandError(
                "DJANGO_BOOTSTRAP_ADMIN_USERNAME, "
                "DJANGO_BOOTSTRAP_ADMIN_EMAIL, and "
                "DJANGO_BOOTSTRAP_ADMIN_PASSWORD must all be set together."
            )

        user_model = get_user_model()
        existing_user = user_model._default_manager.filter(
            **{user_model.USERNAME_FIELD: username}
        ).first()
        if existing_user:
            if existing_user.is_staff and existing_user.is_superuser:
                self.stdout.write("Bootstrap admin already exists; skipping.")
                return
            raise CommandError(
                "A non-admin user with the bootstrap username already exists. "
                "Choose a different username."
            )

        candidate = user_model(**{
            user_model.USERNAME_FIELD: username,
            "email": email,
        })
        try:
            validate_password(password, user=candidate)
        except ValidationError:
            raise CommandError(
                "The bootstrap password does not meet the configured "
                "password requirements."
            ) from None

        user_model._default_manager.create_superuser(
            **{
                user_model.USERNAME_FIELD: username,
                "email": email,
                "password": password,
            }
        )
        self.stdout.write("Bootstrap admin created successfully.")
