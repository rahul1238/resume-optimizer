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
