"""Authentication and account views."""
import resend
from django.conf import settings

def send_otp_email(email: str, username: str, otp: str):
    resend.api_key = getattr(settings, 'RESEND_API_KEY', '')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')

    return resend.Emails.send({
        "from": from_email,
        "to": [email],
        "subject": "Verify Your Email - OTP",
        "html": f"<p>Hello <strong>{username}</strong>,</p>"
                f"<p>Your OTP for registration is: <strong>{otp}</strong></p>"
                f"<p>Do not share this code with anyone.</p>",
    })