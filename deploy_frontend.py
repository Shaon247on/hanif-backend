import paramiko
import os

HOST = '187.7.27.77'
USER = 'root'
PASSWORD = 'Jazzcouk@#123'
DOMAIN = 'jazzbarberseastbourne.com'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    print("Connected successfully.")

    # Execute setup commands
    commands = [
        "apt-get update",
        "apt-get install -y nginx",
        f"mkdir -p /var/www/{DOMAIN}/html",
        f"chown -R www-data:www-data /var/www/{DOMAIN}/html",
        f"chmod -R 755 /var/www/{DOMAIN}"
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

    # Upload HTML
    print("Uploading index.html...")
    sftp = ssh.open_sftp()
    local_path = '/home/backend/siam/barberbay/frontend/index.html'
    remote_path = f'/var/www/{DOMAIN}/html/index.html'
    sftp.put(local_path, remote_path)
    
    # Nginx Config
    nginx_config = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {DOMAIN} www.{DOMAIN};

    root /var/www/{DOMAIN}/html;
    index index.html;

    location / {{
        try_files $uri $uri/ =404;
    }}
}}
"""
    print("Configuring Nginx...")
    with sftp.file(f'/etc/nginx/sites-available/{DOMAIN}', 'w') as f:
        f.write(nginx_config)
    sftp.close()

    # Enable and restart Nginx
    commands_final = [
        f"ln -sf /etc/nginx/sites-available/{DOMAIN} /etc/nginx/sites-enabled/",
        "systemctl restart nginx"
    ]
    
    for cmd in commands_final:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

    print("Deployment successful! Nginx is serving the Coming Soon page.")

except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
