import smtplib

# Configuración SMTP de Purelymail
smtp_server = "smtp.purelymail.com"
port = 587  # Para TLS
sender_email = "logistica@porencargo.co"      # Reemplaza con tu correo
password = "Carlos161809Aguado*2025*"  # Tu contraseña de Purelymail
recipient_email = "carloag210@hotmail.com"  # Reemplaza con el correo de destino

# Mensaje simple
message = """\
Subject: Prueba SMTP desde Python

Hola, este es un correo de prueba enviado desde Python usando Purelymail.
"""

server = None  # Inicializamos server antes del try

try:
    # Conexión al servidor
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()  # Inicia TLS
    server.login(sender_email, password)  # Inicia sesión
    server.sendmail(sender_email, recipient_email, message)  # Envía el correo
    print("✅ Correo enviado correctamente")
except Exception as e:
    print("❌ Error al enviar correo:", e)
finally:
    if server:
        server.quit()  # Cierra la conexión solo si se creó

