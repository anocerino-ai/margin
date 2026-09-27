# Oracle Always Free deployment

This deployment runs the frontend, API and job worker on one Oracle VM. Cloudflare D1 remains the database. Caddy terminates HTTPS on the VM and forwards traffic to the existing loopback-only web container. Netlify is not needed for this topology.

```text
Browser → HTTPS / Caddy → Nginx / Vue + API proxy → FastAPI
                                                   ↓
                                      Cloudflare D1 bridge
                                                   ↑
                                           Python worker
```

## 1. Create an eligible VM

Register at [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) and choose your home region carefully. In Compute → Instances → Create instance, use:

| Field | Selection |
| --- | --- |
| Name | margin |
| Image | Canonical Ubuntu 24.04 LTS, ARM64, eligible for Always Free |
| Shape | VM.Standard.A1.Flex |
| CPU / memory | 1 OCPU / 6 GB RAM |
| Boot volume | 50 GB, within your account's free storage allocation |
| Networking | Public subnet with internet gateway and public IPv4 |
| SSH | Upload your public SSH key or download the generated private key securely |

Check the eligibility labels and account usage before creating the instance. The documented A1 allowance is currently equivalent to 2 OCPUs and 12 GB across the free tenancy; this guide uses half of it. Do not select a paid shape just because A1 has no capacity. Retry another availability domain in your home region or wait.

Oracle can reclaim idle Always Free instances, so keep off-host backups. The published free allocation is not a guarantee of available capacity or uninterrupted hosting. See [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

## 2. Configure network access

On the instance's VNIC/subnet, add stateful ingress rules in the associated security list or network security group:

| Protocol / destination port | Source |
| --- | --- |
| TCP 22 | Your current public IP followed by `/32` |
| TCP 80 | `0.0.0.0/0` |
| TCP 443 | `0.0.0.0/0` |

Retain outbound internet access for image downloads, D1 and provider APIs. Do not expose ports 8000, 8080 or 5173 publicly. Confirm the subnet has a route to an internet gateway. SSH access must be updated if your home IP changes.

The Ubuntu image may also have an operating-system firewall. Inspect `sudo ufw status` and `sudo iptables -S`. If UFW is active, allow TCP 80/443 and your SSH source there. If an existing iptables INPUT chain ends in a REJECT rule, add equivalent scoped rules before that rejection and persist them using the image's firewall management mechanism. Do not flush Oracle's rules or disable the firewall wholesale.

## 3. Connect from your Mac

Replace the key path and IP with the values from your instance:

```sh
chmod 600 ~/.ssh/oracle-margin.key
ssh -i ~/.ssh/oracle-margin.key ubuntu@YOUR_VM_IP
```

Confirm the SSH host identity using Oracle's instance/console information before accepting it. Never upload the private SSH key to GitHub or paste it into chat.

On the VM:

```sh
sudo apt update
sudo apt install -y ca-certificates curl git python3 python3-venv
```

## 4. Install Docker on Ubuntu

Use Docker's official apt repository:

```sh
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF_DOCKER
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

This guide uses `sudo docker`, avoiding changes to Docker group membership. Reference: [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

## 5. Clone the repository

For a public repository:

```sh
git clone https://github.com/anocerino-ai/margin.git
cd margin
```

For a private repository, create a separate read-only deploy key on the VM:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/margin_deploy -C margin-vm
cat ~/.ssh/margin_deploy.pub
```

Add only the public key in GitHub → repository Settings → Deploy keys. Leave write access disabled. Clone using that key:

```sh
GIT_SSH_COMMAND='ssh -i ~/.ssh/margin_deploy -o IdentitiesOnly=yes' git clone git@github.com:anocerino-ai/margin.git
cd margin
git config core.sshCommand 'ssh -i ~/.ssh/margin_deploy -o IdentitiesOnly=yes'
```

Check GitHub's SSH host fingerprint before accepting it. Do not place an access token in the clone URL.

## 6. Configure admin, D1 and provider keys

```sh
cp .env.example .env
chmod 600 .env
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
.venv/bin/pip install --no-deps -e apps/api
.venv/bin/python scripts/admin.py
```

Choose your admin email and password. Use a local editor such as `nano .env` to set:

```dotenv
MARGIN_ENV=production
MARGIN_COOKIE_SECURE=true
MARGIN_STORAGE=d1_worker
MARGIN_D1_WORKER_URL=https://YOUR_BRIDGE.YOUR_SUBDOMAIN.workers.dev
MARGIN_D1_WORKER_TOKEN=YOUR_EXISTING_BRIDGE_TOKEN
```

Reuse the bridge URL and token from your private Mac `.env`; do not create another database. Existing D1 records and model settings are shared. The VM does not inherit provider overrides saved in your Mac's Docker volume: set provider keys in the VM environment or enter them through Settings after HTTPS is ready.

The current production settings validator also requires a legacy server token of at least 32 characters. Generate and save it without printing it:

```sh
.venv/bin/python - <<'PY'
import secrets
from dotenv import set_key
set_key('.env', 'MARGIN_API_TOKEN', secrets.token_urlsafe(32))
PY
chmod 600 .env
.venv/bin/python scripts/validate_bridge.py
```

This token is not your login password and does not bypass the admin session. The probe creates and removes a temporary table to test D1 transaction behavior.

## 7. Start the application

```sh
sudo docker compose -f compose.yaml -f compose.d1.yaml up --build -d
sudo docker compose -f compose.yaml -f compose.d1.yaml ps -a
curl -fsS http://127.0.0.1:8080/api/auth/session
```

Expect `init` to exit with code 0, API to be healthy, and web/worker to remain running. The auth response should report `configured: true`. Do not test login over public plain HTTP: secure cookies are enabled.

## 8. Point your subdomain to the VM

At the authoritative DNS provider for your domain, create an A record for your chosen application subdomain pointing to the VM's public IPv4. For example, `margin.example.com`. Do not alter your root website records.

If DNS is managed by Cloudflare, start with **DNS only** for this record so certificate issuance is straightforward. Do not add an AAAA record unless IPv6 routing and firewall access are configured too. Wait until DNS resolves to the VM.

## 9. Enable HTTPS with Caddy

On the VM in the repository directory, create `Caddyfile` using your real hostname:

```sh
cat > Caddyfile <<'CADDY'
margin.example.com {
    reverse_proxy 127.0.0.1:8080
}
CADDY
sudo docker volume create margin_caddy_data
sudo docker volume create margin_caddy_config
sudo docker run -d --name margin-caddy --restart unless-stopped \
  --network host \
  -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v margin_caddy_data:/data \
  -v margin_caddy_config:/config \
  caddy:2
sudo docker logs --tail=50 margin-caddy
```

Host networking here is for the Linux VM. Caddy obtains and renews certificates when DNS and ports 80/443 are reachable. Keep its volumes for certificate state. Reference: [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

Open `https://YOUR_SUBDOMAIN`, sign in and check worker status. Save provider connections, run a small discovery, inspect the result and generate one draft. Hosting setup alone does not validate provider quotas or generated content quality.

Once the VM is confirmed working, stop the local Mac stack if you do not want two workers consuming the same D1 queue:

```sh
docker compose -f compose.yaml -f compose.d1.yaml down
```

Run that last command on the Mac, not the VM. Do not add `-v`.

## 10. Maintain the deployment

For code updates, on the VM:

```sh
git pull --ff-only
sudo docker compose -f compose.yaml -f compose.d1.yaml up --build -d
```

For `.env` changes use `up -d --force-recreate` with both Compose files. Back up the private `.env`, the provider-credentials volume and Caddy's certificate state; protect backups as secrets. D1 application data needs a separate D1 export/Time Travel recovery plan. VM snapshots alone do not back up remote D1.

Keep the same checkout directory/Compose project name so the credentials volume remains attached. Do not run `down -v`. Check Oracle usage and keep resources within the free allocation. Provider APIs and domain registration have independent costs. No VM is provisioned merely by following or building these docs.
