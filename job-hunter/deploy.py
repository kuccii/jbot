"""Deploy job-hunter standalone to VPS."""
import paramiko
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "72.60.188.94"
USER = "root"
PASSWORD = "Sudoroot100@"
REMOTE_DIR = "/root/job-hunter"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

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
    for line in out.strip().split("\n")[-5:]:
        print(f"  {line}")
    for line in err.strip().split("\n")[-5:]:
        print(f"  ! {line}")
    return exit_code

# Stop old containers
run("docker stop job-hunter 2>/dev/null; docker rm job-hunter 2>/dev/null")

# Clean and create directory
run(f"rm -rf {REMOTE_DIR}")
run(f"mkdir -p {REMOTE_DIR}/data")
# Ensure config.yaml is always a file, not a directory
run(f"rm -rf {REMOTE_DIR}/config.yaml && cp {REMOTE_DIR}/../config.example.yaml {REMOTE_DIR}/config.yaml 2>/dev/null || true")

# Upload files
skip_dirs = {".git", "__pycache__", ".pytest_cache", ".freebuff", ".openclaude",
             "job-hunter-improved", "data", ".venv", "venv", "tests"}
skip_files = {".pyc", ".pyo", ".DS_Store", ".zip"}

sftp = ssh.open_sftp()
uploaded = 0
for root, dirs, files in os.walk(LOCAL_DIR):
    rel = os.path.relpath(root, LOCAL_DIR)
    parts = rel.replace("\\", "/").split("/") if rel != "." else []

    if any(s in skip_dirs for s in parts):
        continue

    remote_dir = REMOTE_DIR if rel == "." else REMOTE_DIR + "/" + rel.replace("\\", "/")

    # Create remote directory
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        base_parts = remote_dir.split("/")
        for i in range(3, len(base_parts) + 1):
            sub = "/".join(base_parts[:i])
            try:
                sftp.stat(sub)
            except FileNotFoundError:
                sftp.mkdir(sub)

    for f in files:
        if any(f.endswith(ext) for ext in skip_files):
            continue
        if f == "config.yaml":  # Don't overwrite config on VPS
            continue
        local_path = os.path.join(root, f)
        remote_path = remote_dir + "/" + f
        try:
            sftp.put(local_path, remote_path)
            uploaded += 1
        except Exception as e:
            print(f"  Skip {f}: {e}")

sftp.close()
print(f"\nUploaded {uploaded} files")

# Verify
run(f"ls -la {REMOTE_DIR}/")
run(f"ls {REMOTE_DIR}/job_hunter/ | head -15")

# Build and start
run(f"cd {REMOTE_DIR} && docker compose down 2>/dev/null")
time.sleep(2)
run(f"cd {REMOTE_DIR} && docker compose up -d --build 2>&1", timeout=300)
time.sleep(8)

# Check status
run(f"docker compose -f {REMOTE_DIR}/docker-compose.yml ps")
run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8001/")
run(f"curl -s http://localhost:8001/api/stats | head -1")

ssh.close()
print("\nDone!")
