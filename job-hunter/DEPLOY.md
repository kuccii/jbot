# Deploy Job Hunter to VPS

## Prerequisites

- VPS with Docker installed (Ubuntu 22.04+ recommended)
- SSH access to the VPS
- Domain name (optional, for HTTPS)

## Quick Deploy

### 1. Clone the repo on your VPS

```bash
ssh user@YOUR_VPS_IP
git clone https://github.com/kuccii/jhunt.git /opt/job-hunter
cd /opt/job-hunter/job-hunter
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Edit `config.yaml`:
- Set your `profile.name`, `email`, `skills`
- Set `keywords` for job filtering
- Optionally enable `notifications` (Telegram, webhook, email)

### 3. Build and run

```bash
docker compose up -d --build
```

The dashboard will be available at `http://YOUR_VPS_IP`

### 4. Run initial discovery

```bash
docker compose exec app job-hunter discover
```

### 5. (Optional) Set up HTTPS with Let's Encrypt

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Stop nginx temporarily
docker compose stop nginx

# Get certificate
certbot certonly --standalone -d yourdomain.com

# Update nginx.conf for HTTPS, then restart
docker compose up -d nginx
```

## Commands

```bash
# View logs
docker compose logs -f app

# Run discovery
docker compose exec app job-hunter discover

# Watch mode (continuous discovery)
docker compose exec app job-hunter watch --interval 3600

# Analyze jobs (check links, quality)
docker compose exec app job-hunter analyze

# Clean database
docker compose exec app job-hunter cleanup

# Restart
docker compose restart
```

## Updating

```bash
cd /opt/job-hunter/job-hunter
git pull
docker compose up -d --build
```

## Troubleshooting

- **Port 80 in use**: Change `ports: "80:80"` to `"8080:80"` in docker-compose.yml
- **Disk full**: Run `docker system prune -a` to clean Docker cache
- **Board errors**: Some boards may be temporarily blocked. Check logs with `docker compose logs app`
