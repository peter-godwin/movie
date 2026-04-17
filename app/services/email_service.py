from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from app.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

fastmail = FastMail(conf)


async def send_verification_email(email: EmailStr, token: str) -> None:
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 40px;">
        <div style="max-width: 480px; margin: auto; background: #fff;
                    border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
          <h2 style="color: #1a1a1a;">Verify your email</h2>
          <p style="color: #555;">Use the code below to verify your account. It expires in <strong>30 minutes</strong>.</p>
          <div style="font-size: 36px; font-weight: bold; letter-spacing: 8px;
                      color: #4F46E5; margin: 24px 0; text-align: center;">{token}</div>
          <p style="color: #999; font-size: 13px;">
            If you didn't create an account, you can safely ignore this email.
          </p>
        </div>
      </body>
    </html>
    """
    message = MessageSchema(
        subject="Verify your email — Moviz",
        recipients=[email],
        body=html,
        subtype=MessageType.html,
    )
    await fastmail.send_message(message)


async def send_otp_email(email: EmailStr, otp_code: str) -> None:
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 40px;">
        <div style="max-width: 480px; margin: auto; background: #fff;
                    border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
          <h2 style="color: #1a1a1a;">Reset your password</h2>
          <p style="color: #555;">Use the OTP below to reset your password. It expires in <strong>10 minutes</strong>.</p>
          <div style="font-size: 36px; font-weight: bold; letter-spacing: 8px;
                      color: #4F46E5; margin: 24px 0; text-align: center;">{otp_code}</div>
          <p style="color: #999; font-size: 13px;">
            If you didn't request a password reset, please ignore this email or contact support
            if you have concerns.
          </p>
        </div>
      </body>
    </html>
    """
    message = MessageSchema(
        subject="Your password reset OTP — Moviz",
        recipients=[email],
        body=html,
        subtype=MessageType.html,
    )
    await fastmail.send_message(message)


async def send_welcome_email(email: EmailStr, name: str | None = None) -> None:
    display_name = name or "there"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 40px;">
        <div style="max-width: 480px; margin: auto; background: #fff;
                    border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
          <h2 style="color: #1a1a1a;">Welcome to Moviz, {display_name}! 🎬</h2>
          <p style="color: #555;">Your email has been verified and your account is ready to go.</p>
          <p style="color: #555;">Enjoy discovering and tracking your favourite movies.</p>
          <p style="color: #999; font-size: 13px; margin-top: 32px;">— The Moviz Team</p>
        </div>
      </body>
    </html>
    """
    message = MessageSchema(
        subject="Welcome to Moviz!",
        recipients=[email],
        body=html,
        subtype=MessageType.html,
    )
    await fastmail.send_message(message)