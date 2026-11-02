# OpsPilot demo application — incident generator for the S1 laboratory.
#
# IMPORTANT (docs/architecture/ARCHITECTURE.md §5): this is a throwaway probe app
# deployed ONLY inside the Kind lab to produce controlled incidents. It is NOT the
# project backend — the real FastAPI backend (S5) will be a separate service that
# never runs inside this workload. Keeping both clearly distinct was an explicit
# requirement of the project setup.
#
# Behaviors are selected with the SCENARIO env var:
#   healthy    - serve /healthz and /info (use for lab self-tests and reset checks)
#   crashloop  - print a startup log line then exit non-zero => the Pod enters
#                CrashLoopBackOff (SC-01). Each attempt logs its number so that
#                `kubectl logs --previous` differs from current logs (FR-04).
#   oom        - allocate memory beyond the container limit => the container is
#                OOMKilled (SC-04). The exit code is whatever Kubernetes reports;
#                it is never fabricated here (spec §10.6: "exit code 137 ne doit
#                pas être supposé" — it must be OBSERVED from a real run).
# ImagePullBackOff (SC-02) is produced by the manifest, not by this app.
import os
import sys
import time
from typing import Any, Dict

SCENARIO = os.environ.get("SCENARIO", "healthy").strip().lower()
VALID_SCENARIOS = ("healthy", "crashloop", "oom")


def _log_startup() -> None:
    attempt = os.environ.get("HOSTNAME", "unknown-host")
    print(f"demo-app: starting; scenario={SCENARIO}; pod={attempt}", flush=True)


if SCENARIO == "crashloop":
    _log_startup()
    # Small delay so logs accumulate before the process exits; restartPolicy: Always
    # on the manifest makes Kubernetes restart the container -> CrashLoopBackOff.
    time.sleep(3)
    print("demo-app: simulating application error; exiting 1 (SC-01)", flush=True)
    sys.exit(1)

if SCENARIO == "oom":
    _log_startup()
    # Keep allocating past the container limit (limits are set in the SC-04
    # manifest, e.g. 64Mi). The kernel kills the process; we do not pretend to
    # know the exit code here (spec §10.6).
    blocks: list[bytes] = []
    print("demo-app: allocating memory beyond the container limit (SC-04)", flush=True)
    while True:
        blocks.append(bytes(8 * 1024 * 1024))  # 8 MiB per block
        time.sleep(0.05)

if SCENARIO != "healthy":
    print(f"demo-app: unknown SCENARIO={SCENARIO!r}; expected one of {VALID_SCENARIOS}", file=sys.stderr, flush=True)
    sys.exit(2)

# --- healthy mode: minimal FastAPI service for lab self-tests -----------------
from fastapi import FastAPI  # noqa: E402  (import after early exits on purpose)

app = FastAPI(title="OpsPilot demo app", version="s1")


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"status": "ok", "scenario": SCENARIO}


@app.get("/info")
def info() -> Dict[str, Any]:
    return {
        "app": "opspilot-demo",
        "scenario": SCENARIO,
        "purpose": "incident generator for the S1 laboratory (not the project backend)",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
