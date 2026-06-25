import paramiko
import os
import time

HOST = "72.60.188.94"
USER = "root"
PASSWORD = "Sudoroot100@"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, look_for_keys=False, allow_agent=False)
print("Connected to VPS")

def run(cmd, timeout=120):
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip():
        for line in out.strip().split("\n"):
            print(f"  {line}")
    if err.strip():
        for line in err.strip().split("\n"):
            print(f"  ! {line}")
    return exit_code

local_repo = os.path.dirname(os.path.abspath(__file__))
print(f"Local repo at: {local_repo}")

run("apt-get update -qq && apt-get install -y -qq docker.io docker-compose-v2 2>/dev/null")
time.sleep(2)

run("cd /root && rm -rf JBot-temp")
run("mkdir -p /root/JBot-temp")

sftp = ssh.open_sftp()
for root, dirs, files in os.walk(local_repo):
    rel = os.path.relpath(root, local_repo)
    skip_dirs = [".", "venv", "__pycache__", ".git", "tests", "docs", "node_modules", ".venv"]
    norm = rel.replace("\\", "/")
    if rel == ".":
        remote_dir = "/root/JBot-temp"
    elif any(s in norm.split("/") for s in skip_dirs):
        continue
    else:
        remote_dir = "/root/JBot-temp/" + norm
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parts = remote_dir.split("/")
        for i in range(3, len(parts) + 1):
            sub = "/".join(parts[:i])
            try:
                sftp.stat(sub)
            except FileNotFoundError:
                sftp.mkdir(sub)
    for f in files:
        if f.endswith(".pyc") or f.endswith(".pyo") or f == ".DS_Store":
            continue
        local_path = os.path.join(root, f)
        remote_path = remote_dir + "/" + f
        sftp.put(local_path, remote_path)
sftp.close()
print("Files uploaded")

run("cd /root && rm -rf JBot && mv JBot-temp JBot")

run("cd /root/JBot && mkdir -p data profile")
run("cd /root/JBot && ls -la")

run("docker compose -f /root/JBot/docker-compose.yml down 2>/dev/null")
time.sleep(2)

exit_code = run("docker compose -f /root/JBot/docker-compose.yml up -d --build 2>&1", timeout=300)
if exit_code != 0:
    print("Build failed, checking for errors...")
    run("docker compose -f /root/JBot/docker-compose.yml logs", timeout=30)
else:
    print("Container started, checking status...")
    time.sleep(5)
    run("docker compose -f /root/JBot/docker-compose.yml ps")
    run("docker compose -f /root/JBot/docker-compose.yml logs --tail=30", timeout=15)

ssh.close()
