## Resume Optimizer API

### LaTeX PDF dependency

ATS PDF exports are compiled with Tectonic. Install it before starting the API:

```bash
brew install tectonic
```

The compiler runs with `--untrusted` and a timeout. Production deployments should
pre-warm the Tectonic resource bundle during the container build and set:

```env
TECTONIC_BINARY="tectonic"
TECTONIC_ONLY_CACHED=true
LATEX_COMPILE_TIMEOUT_SECONDS=30
```

For a new local installation that has not downloaded its bundle yet, temporarily
set `TECTONIC_ONLY_CACHED=false`, generate one PDF, and then restore it to `true`.

### Production container

The API image pins and verifies Tectonic, warms its LaTeX resource cache during
the build, and runs the application as a non-root user. Build it from this
directory so the Docker context remains limited to the API:

```bash
docker build -t resume-optimizer-api .
docker run --rm -p 8000:8000 --env-file .env resume-optimizer-api
```

The container listens on `PORT` when a hosting platform provides it and otherwise
uses port `8000`. Its health check calls `/api/v1/health/`.
