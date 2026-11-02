import paramiko
import os

HOST = '187.7.27.77'
USER = 'root'
PASSWORD = 'Jazzcouk@#123'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    print("Connected successfully.")

    # Fix .env in possible directories
    commands = [
        "cd ~/backend/barberbay && sed -i 's/PROJECT_NAME=\"BarberBay API\"/PROJECT_NAME=\"barberbay\"/g' .env || true",
        "cd ~/barberbay && sed -i 's/PROJECT_NAME=\"BarberBay API\"/PROJECT_NAME=\"barberbay\"/g' .env || true"
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        if out: print(out)

    print("Fixed .env on the server successfully!")

except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
