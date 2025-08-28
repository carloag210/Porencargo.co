import smtplib
from email.mime.text import MIMEText

# Configuración
smtp_server = "smtp.purelymail.com"
smtp_port = 465
username = "logistica@porencargo.co"
password = "pm-live-c0196312-75cd-4eb2-a8bd-5085bd590a43"

# Crear mensaje
msg = MIMEText("Test desde Python puro")
msg['Subject'] = 'Test SMTP Python'
msg['From'] = 'logistica@porencargo.co'
msg['To'] = 'tu_email@gmail.com'  # Cambia esto

# Enviar
try:
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(username, password)
        server.send_message(msg)
    print("✅ Email enviado via Python puro!")
except Exception as e:
    print(f"❌ Error: {e}")

    