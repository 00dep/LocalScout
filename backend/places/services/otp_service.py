"""OTP generation and verification services for the places app."""
import random

def generate_otp() -> str:
    return str(random.randint(100000, 999999))