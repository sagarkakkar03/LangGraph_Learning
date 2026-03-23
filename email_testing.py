import smtplib
from email.mime.text import MIMEText

# Sender and receiver
sender_email = "hrcompanyexample@gmail.com"
receiver_email = "kakkarsagar03@gmail.com"

# Use your Gmail App Password here (NOT your normal password)
app_password = "cgpb eiax vunz kkkb"

# Email content
subject = "Test Email from HR System"
body = "Hello Sagar,\n\nThis is a test email from your HR automation system.\n\nRegards,\nHR Team"

# Create message
msg = MIMEText(body)
msg["Subject"] = subject
msg["From"] = sender_email
msg["To"] = receiver_email

try:
    # Connect to Gmail SMTP
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, app_password)

    # Send email
    server.sendmail(sender_email, receiver_email, msg.as_string())

    print("✅ Email sent successfully!")

    server.quit()

except Exception as e:
    print("❌ Error:", e)