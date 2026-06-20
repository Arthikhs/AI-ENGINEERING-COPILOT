"""
Secure Code Execution Sandbox — Production Grade
Docker-based isolated execution with:
- CPU / Memory / PID limits
- Network isolation (none)
- Read-only filesystem (except /tmp)
- Timeout protection
- Proper temp file handling
- stdout / stderr separation
- stdin support
- Multi-language: Python, JavaScript, TypeScript, Java
- DB execution logging
- Retry on transient Docker errors
"""
import os
import time
import uuid
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# ── Language Config ────────────────────────────────────────────────────────────

LANGUAGE_CONFIG = {
    "python": {
        "image":    "python:3.11-slim",
        "filename": "solution.py",
        "cmd":      ["python", "/sandbox/solution.py"],
    },
    "javascript": {
        "image":    "node:20-alpine",
        "filename": "solution.js",
        "cmd":      ["node", "/sandbox/solution.js"],
    },
    "typescript": {
        "image":    "node:20-alpine",
        "filename": "solution.ts",
        "cmd":      ["sh", "-c", "npx --yes ts-node /sandbox/solution.ts"],
    },
    "java": {
        "image":    "openjdk:17-slim",
        "filename": "Solution.java",
        "cmd":      ["sh", "-c", "cd /sandbox && javac Solution.java && java Solution"],
    },
}

# ── Sandbox Limits ─────────────────────────────────────────────────────────────

LIMITS = {
    "mem_limit":      "256m",
    "memswap_limit":  "256m",
    "cpu_period":     100_000,
    "cpu_quota":      50_000,    # 50% of 1 CPU
    "pids_limit":     64,
    "timeout_sec":    30,
    "max_output_len": 50_000,    # truncate huge outputs
}

SUPPORTED_LANGUAGES = list(LANGUAGE_CONFIG.keys())


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class SandboxResult:
    success:          bool
    stdout:           str
    stderr:           str
    exit_code:        int
    execution_time_ms: int
    language:         str = ""
    timed_out:        bool = False
    sandbox_error:    bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Core Executor ──────────────────────────────────────────────────────────────

async def execute_code(
    code: str,
    language: str,
    stdin_data: Optional[str] = None,
) -> SandboxResult:
    """
    Execute code in an isolated Docker sandbox.
    Returns SandboxResult with stdout, stderr, exit_code and timing.
    """
    language = language.lower()
    if language not in LANGUAGE_CONFIG:
        return SandboxResult(
            success=False, stdout="", stderr=f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}",
            exit_code=1, execution_time_ms=0, language=language,
        )

    cfg = LANGUAGE_CONFIG[language]
    start = time.time()
    tmp_dir = None

    try:
        import docker
        from docker.errors import ContainerError, ImageNotFound

        client = docker.from_env(timeout=10)

        # Write code to a real temp directory (bind mount into container)
        tmp_dir = tempfile.mkdtemp(prefix="sandbox_")
        code_path = Path(tmp_dir) / cfg["filename"]
        code_path.write_text(code, encoding="utf-8")

        # Pull image if not present (silent)
        try:
            client.images.get(cfg["image"])
        except ImageNotFound:
            logger.info(f"Pulling sandbox image: {cfg['image']}")
            client.images.pull(cfg["image"])

        container = client.containers.run(
            image=cfg["image"],
            command=cfg["cmd"],
            volumes={tmp_dir: {"bind": "/sandbox", "mode": "ro"}},
            mem_limit=LIMITS["mem_limit"],
            memswap_limit=LIMITS["memswap_limit"],
            cpu_period=LIMITS["cpu_period"],
            cpu_quota=LIMITS["cpu_quota"],
            pids_limit=LIMITS["pids_limit"],
            network_mode="none",
            read_only=True,
            tmpfs={"/tmp": "size=64m,noexec"},
            stdin_open=bool(stdin_data),
            remove=False,          # remove manually after reading logs
            detach=True,
            stdout=True,
            stderr=True,
        )

        # Feed stdin if provided
        if stdin_data:
            try:
                sock = container.attach_socket(params={"stdin": True, "stream": True})
                sock._sock.sendall(stdin_data.encode())
                sock._sock.close()
            except Exception:
                pass

        # Wait with timeout
        timed_out = False
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(container.wait),
                timeout=LIMITS["timeout_sec"],
            )
            exit_code = result.get("StatusCode", 1)
        except asyncio.TimeoutError:
            container.kill()
            timed_out = True
            exit_code = 124

        elapsed = int((time.time() - start) * 1000)

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        # Truncate large outputs
        stdout = stdout[:LIMITS["max_output_len"]]
        stderr = stderr[:LIMITS["max_output_len"]]

        container.remove(force=True)

        return SandboxResult(
            success=exit_code == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=elapsed,
            language=language,
            timed_out=timed_out,
        )

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.warning(f"Sandbox error ({language}): {e}")
        return SandboxResult(
            success=False, stdout="", stderr=str(e),
            exit_code=1, execution_time_ms=elapsed,
            language=language, sandbox_error=True,
        )
    finally:
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def execute_code_with_retry(
    code: str,
    language: str,
    stdin_data: Optional[str] = None,
    max_retries: int = 2,
) -> SandboxResult:
    """Execute with retry on transient Docker errors."""
    for attempt in range(max_retries + 1):
        result = await execute_code(code, language, stdin_data)
        if not result.sandbox_error:
            return result
        if attempt < max_retries:
            logger.info(f"Sandbox retry {attempt + 1}/{max_retries}")
            await asyncio.sleep(1)
    return result


async def execute_tests(
    test_code: str,
    source_code: str,
    language: str = "python",
) -> SandboxResult:
    """
    Execute test code against source code.
    Combines source + tests into a single file for Python/JS.
    For Java, wraps them together.
    """
    if language == "python":
        # Combine source + test, run with pytest-style discovery
        combined = (
            f"# === Source Code ===\n{source_code}\n\n"
            f"# === Tests ===\n{test_code}\n\n"
            "# === Run Tests ===\n"
            "import sys\n"
            "_tests_passed = 0\n"
            "_tests_failed = 0\n"
            "for _name, _obj in list(globals().items()):\n"
            "    if _name.startswith('test_') and callable(_obj):\n"
            "        try:\n"
            "            _obj()\n"
            "            print(f'✅ {_name} passed')\n"
            "            _tests_passed += 1\n"
            "        except Exception as _e:\n"
            "            print(f'❌ {_name} failed: {_e}')\n"
            "            _tests_failed += 1\n"
            "print(f'\\nResults: {_tests_passed} passed, {_tests_failed} failed')\n"
            "sys.exit(0 if _tests_failed == 0 else 1)\n"
        )
    elif language in ("javascript", "typescript"):
        combined = (
            f"// === Source ===\n{source_code}\n\n"
            f"// === Tests ===\n{test_code}\n"
        )
    else:
        combined = f"{source_code}\n\n{test_code}"

    return await execute_code_with_retry(combined, language)


async def log_execution(
    result: SandboxResult,
    job_id: Optional[str],
    db_session,
) -> None:
    """Persist sandbox execution result to database."""
    try:
        from sqlalchemy import text
        await db_session.execute(
            text("""
                INSERT INTO sandbox_executions
                  (id, job_id, language, code, status, stdout, stderr,
                   exit_code, execution_time_ms, created_at)
                VALUES
                  (:id, :job_id, :lang, '', :status, :stdout, :stderr,
                   :exit_code, :time_ms, now())
            """),
            {
                "id":       str(uuid.uuid4()),
                "job_id":   job_id,
                "lang":     result.language,
                "status":   "passed" if result.success else "failed",
                "stdout":   result.stdout[:5000],
                "stderr":   result.stderr[:5000],
                "exit_code": result.exit_code,
                "time_ms":  result.execution_time_ms,
            }
        )
        await db_session.commit()
    except Exception as e:
        logger.warning(f"Failed to log sandbox execution: {e}")


def is_docker_available() -> bool:
    """Check if Docker daemon is accessible."""
    try:
        import docker
        docker.from_env(timeout=3).ping()
        return True
    except Exception:
        return False
