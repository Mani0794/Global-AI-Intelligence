import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ============================================================
# SETTINGS
# ============================================================

HTML_FILE = "ai_news_email.html"


# ============================================================
# GET GITHUB SECRETS
# ============================================================

gmail_username = os.environ.get("GMAIL_USERNAME")
gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
gmail_to = os.environ.get("GMAIL_TO")


if not gmail_username:
    raise RuntimeError("GMAIL_USERNAME is missing.")

if not gmail_app_password:
    raise RuntimeError("GMAIL_APP_PASSWORD is missing.")

if not gmail_to:
    raise RuntimeError("GMAIL_TO is missing.")


# ============================================================
# READ HTML EMAIL
# ============================================================

if not os.path.exists(HTML_FILE):
    raise FileNotFoundError(
        f"{HTML_FILE} was not found."
    )


with open(
    HTML_FILE,
    "r",
    encoding="utf-8"
) as file:

    html_content = file.read()


# ============================================================
# CREATE EMAIL
# ============================================================

message = MIMEMultipart("alternative")

message["Subject"] = "🌎 Global AI Intelligence Brief"
message["From"] = gmail_username
message["To"] = gmail_to


html_part = MIMEText(
    html_content,
    "html",
    "utf-8"
)

message.attach(html_part)


# ============================================================
# SEND THROUGH GMAIL
# ============================================================

print("Connecting to Gmail...")


with smtplib.SMTP_SSL(
    "smtp.gmail.com",
    465
) as server:

    server.login(
        gmail_username,
        gmail_app_password
    )

    server.sendmail(
        gmail_username,
        [gmail_to],
        message.as_string()
    )


print("✅ AI Intelligence email sent successfully.")
