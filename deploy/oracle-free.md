# GIAE — deploy to a free, always-on server (Oracle Cloud Always Free)

Turns "demo on my laptop" into "a link I can share," at **$0/month, forever**.
Oracle's Always Free tier gives an ARM VM (up to 4 cores / 24 GB RAM / 200 GB
disk) that runs the full compose stack — and we already validated the image on
ARM64, so it just works.

The split: **you** do the account/VM/DNS (I can't — no access to your cloud);
**a script** does everything on the box.

---

## Part A — provision (you, ~15 min, one-time)

1. **Oracle Cloud account** — https://cloud.oracle.com → sign up. Needs a card
   for identity verification; **Always Free resources are never charged**.
2. **Create the VM**: Compute → Instances → Create.
   - Image: **Ubuntu 22.04**. Shape: **VM.Standard.A1.Flex** (Ampere/ARM);
     set **4 OCPU / 24 GB** (all within Always Free).
   - Add your **SSH public key**.
   - Boot volume: 100–200 GB.
3. **Open the ports**: the instance's subnet → Security List → add Ingress rules
   for **TCP 80 and 443** (source `0.0.0.0/0`). (Leave 8000/3000 closed — only
   Caddy on 80/443 is public.)
4. **DNS**: point a domain/subdomain (e.g. `app.your-domain.com`) A-record at the
   VM's public IP. (Optional for a first test — you can use the IP over http.)

## Part B — deploy (the script, ~10 min)

SSH in, get the code, run one script:

```bash
ssh ubuntu@<VM_PUBLIC_IP>
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Ayo-Cyber/GIAE.git && cd GIAE

# set your public URL so auth/cookies work, then run setup
export GIAE_DOMAIN=https://app.your-domain.com     # or http://<VM_IP>:3000 for a quick test
sudo -E bash deploy/setup.sh
```

`setup.sh` installs Docker, generates `.env` with strong secrets, builds and
starts the 5-service stack (postgres, redis, api, worker, frontend), then
downloads Swiss-Prot and builds the Diamond DB **into the volume at the correct
path (`/app/.giae`) and chowns it to the app user** — the two things that broke
the first dress rehearsal. Skip the 90 MB DB step with `--no-db` if you just
want the offline config up first.

## Part C — HTTPS + domain (you, ~5 min)

```bash
sudo apt-get install -y caddy
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/app.your-domain.com/app.your-actual-domain.com/' /etc/caddy/Caddyfile
sudo systemctl restart caddy      # auto-provisions Let's Encrypt TLS
```

Then make sure `.env` has `NEXTAUTH_URL=https://app.your-actual-domain.com` and
`docker compose up -d frontend`.

## Part D — verify (proves the strong config is live)

```bash
curl -fsS https://app.your-domain.com/api/v1/health          # {"status":"ok"}
```

Open the site, `/signup` the first account, upload `case_studies/lambda_phage.gb`,
and confirm on a gene: a **diamond** hit in the Evidence Ladder, a **Calibrated
Reliability** panel, **GO/EC chips**, and the **phage-safety** banner. If those
show, the production box is running the same strong config as the benchmark.

---

## Operating notes

- **Update to latest code**: `git pull && docker compose up -d --build`
- **Backups**: snapshot the Oracle boot volume on a schedule; the Postgres data
  lives in the `postgres_data` docker volume.
- **Scale**: the worker is the bottleneck — `docker compose up -d --scale worker=2`.
- **Security**: `.env` secrets are generated strong; keep Postgres/Redis
  unpublished (they already are); only Caddy is public. Full checklist in
  `../DEPLOYMENT.md` §8.
- **Cost guard**: everything here fits Always Free. Set a $0 budget alert in
  Oracle so you're never surprised.

## What this is / isn't

This is a real, always-on **pilot** deployment — good for design partners and a
shareable demo. It is **not** a hardened public-paid launch: no billing, no
formal load testing, and the phage-safety screen remains "flags for expert
review, not a validated assay." See the readiness tiers we discussed before
opening public signups.
