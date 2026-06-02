"""AWS S3 connectivity check via AWS CLI."""

from __future__ import annotations

import logging
import shutil
import subprocess

from engp_cfx_sync_monitor import config

logger = logging.getLogger(__name__)


def check_s3_connectivity() -> tuple[bool, str]:
    if not shutil.which("aws"):
        return False, "AWS CLI not found in PATH"

    identity = _run_aws(["sts", "get-caller-identity", "--output", "text"])
    if identity.returncode != 0:
        err = (identity.stderr or identity.stdout or "STS check failed").strip()
        return False, err[:300]

    account = (identity.stdout or "").strip().split()
    acct_hint = account[0] if account else "unknown"

    if config.S3_BUCKET:
        s3_path = f"s3://{config.S3_BUCKET}/"
        if config.S3_PREFIX:
            s3_path += config.S3_PREFIX.lstrip("/")
        probe = _run_aws(
            ["s3", "ls", s3_path, "--max-items", "1"],
        )
        if probe.returncode != 0:
            err = (probe.stderr or probe.stdout or "S3 ls failed").strip()
            return False, f"STS OK ({acct_hint}); S3: {err[:200]}"
        return True, f"STS + S3 OK — {s3_path} (account {acct_hint})"

    return True, f"AWS STS OK (account {acct_hint})"


def _run_aws(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = ["aws", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.AWS_CLI_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            cmd, returncode=124, stdout="", stderr="AWS CLI timed out"
        )
    except OSError as exc:
        logger.exception("AWS CLI error")
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr=str(exc)
        )
