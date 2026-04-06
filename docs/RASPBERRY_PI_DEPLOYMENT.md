# ArchiMind Raspberry Pi Deployment

This runbook assumes the Docker Hub repository is public and that the Raspberry Pi only needs to pull and run the published image.

## 1. Prepare `.env` on the build machine

Start from `.env.example`, then set at least:

```bash
SECRET_KEY=replace_with_a_long_random_secret
GEMINI_API_KEY=replace_with_gemini_api_key
ARCHIMIND_IMAGE=krishnah27/archimind:latest
DOCKERHUB_REPO=krishnah27/archimind
DOCKER_IMAGE_TAG=latest
PI_USER=pi
PI_HOST=192.168.0.65
PI_DIR=/home/pi/archimind
```

Notes:

- `SECRET_KEY` must be a long random value.
- `GEMINI_API_KEY` is required for actual Gemini generation.
- `ARCHIMIND_IMAGE` is what the Pi compose file will pull.

## 2. Build and push the multi-arch image

From the project root on the development machine:

Make sure Docker is actually running first:

```bash
docker info
sudo systemctl start docker
```

Then run:

```bash
bash scripts/00_build_and_push_image.sh krishnah27/archimind latest
```

What this does:

- builds `linux/amd64` and `linux/arm64` images,
- tags `latest` and a timestamp tag,
- pushes both tags to Docker Hub.

Important: this only works if the local Docker daemon is running and the local Docker CLI is already logged in to the target Docker Hub account.

## 3. Smoke-test the container locally

Before deploying to the Pi, verify the container starts cleanly:

If `docker info` fails, start Docker on the build machine before running the smoke test.

```bash
bash scripts/01_smoke_test_container.sh
```

This builds the image locally, starts it on port `5050`, and waits for `/api/status` to return successfully.

## 4. Deploy to the Pi over SSH

Run:

```bash
bash scripts/deploy_pi.sh
```

The script does the following:

1. loads deployment defaults from `.env`,
2. copies `docker-compose.pi.yml` to the Pi as `docker-compose.yml`,
3. copies `.env` to the Pi,
4. installs Docker if it is missing,
5. pulls `ARCHIMIND_IMAGE`,
6. starts the service with `docker compose up -d`.

## 5. Manual pull/run commands on the Pi

If you want to operate the Pi manually instead of using the helper script:

```bash
ssh pi@192.168.0.65
mkdir -p ~/archimind
cd ~/archimind
```

Copy `docker-compose.pi.yml` from this repository as `docker-compose.yml`, copy the prepared `.env`, then run:

```bash
docker pull krishnah27/archimind:latest
ARCHIMIND_IMAGE=krishnah27/archimind:latest docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1/api/status
```

Because the compose file publishes `80:5000`, the service is also reachable on the Pi LAN IP at:

```text
http://<pi-ip>/api/status
```

## 6. Verify Gemini-backed generation

Once the container is up:

1. submit an analysis through the UI or `POST /api/analyze`,
2. poll `GET /api/status?analysis_id=<id>`,
3. check the `generation_backend` field in the response.

Expected values:

- `gemini:gemini-3.1-flash-lite-preview` when Gemini is active,
- `local` if the app had to fall back because `GEMINI_API_KEY` or Gemini access was unavailable.

## 7. Updating the Pi to a newer image

After pushing a new image:

```bash
ssh pi@192.168.0.65 'cd ~/archimind && docker compose pull && docker compose up -d && docker compose ps'
```

If you changed tags, update `ARCHIMIND_IMAGE` in `.env` on the Pi first.

## 8. Troubleshooting

### Container does not become healthy

Run:

```bash
docker compose logs --tail=100 web
docker inspect --format='{{json .State.Health}}' archimind_web
```

### Pi pulled the wrong image

Confirm the active image reference:

```bash
grep '^ARCHIMIND_IMAGE=' .env
docker image ls | grep archimind
```

### Gemini generation fell back to local mode

Check inside the running container:

```bash
docker exec -it archimind_web sh -lc 'printenv | grep -E "GEMINI_API_KEY|DOCUMENTATION_MODEL|GEMINI_THINKING_LEVEL"'
```

Then confirm the key is valid and the preview model is accessible from the account.

### Worker cannot write status or SQLite files

Inspect the app data volume:

```bash
docker exec -it archimind_web sh -lc 'ls -lah /app/data'
```

### Need to roll back quickly

If you know the previous timestamp tag, set it explicitly and restart:

```bash
ARCHIMIND_IMAGE=krishnah27/archimind:20260331-120000 docker compose up -d
```