"""
Secure Code Execution Sandbox
Docker-based isolated execution with CPU/memory/network limits.
"""
import asyncio
import uuid
import json
import logging
from typing import Optional
import docker
from docker.errors import ContainerError, ImageNotFound, APIError

logger = logging.getLogger(__name__)

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "run_cmd": "python /code/solution.py",
        "filename": "solution.py",
    },
    "javascript": {
        "image": "node:20-alpine",
        "run_cmd": "node /code/solution.js",
        "filename": "solution.js",
    },
    "typescript": {
        "image": "node:20-alpine",
        "run_cmd": "npx ts-node /code/solution.ts",
        "filename": "solution.ts",
    },
    "java": {
        "image": "openjdk:17-slim",
        "run_cmd": "bash -c 'cd /code && javac Solution.java && java Solution'",
        "filename": "Solution.java",
    },
}

SANDBOX_LIMITS = {
    "mem_limit": "256m",
    "memswap_limit": "256m",
    "cpu_period": 100000,
    "cpu_quota": 50000,       # 50% of 1 CPU
    "pids_limit": 64,
    "timeout": 30,            # seconds
}


class SandboxResult:
    def __init__(self, success: bool, stdout: str, stderr: str,
                 exit_code: int, execution_time_ms: int):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms

    def to_dict(self):
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
        }


async def execute_code(code: str, language: str, test_input: Optional[str] = None) -> SandboxResult:
    """Execute code in an isolated Docker sandbox."""
    if language not in LANGUAGE_CONFIG:
        return SandboxResult(False, "", f"Unsupported language: {language}", 1, 0)

    config = LANGUAGE_CONFIG[language]
    execution_id = str(uuid.uuid4())[:8]
    import time
    start = time.time()

    try:
        client = docker.from_env()

        # Write code to temp container via volume
        container = client.containers.run(
            image=config["image"],
            command=f'sh -c "mkdir -p /code && cat > /code/{config["filename"]} << \'HEREDOC\'\n{code}\nHEREDOC\n{config["run_cmd"]}"',
            mem_limit=SANDBOX_LIMITS["mem_limit"],
            memswap_limit=SANDBOX_LIMITS["memswap_limit"],
            cpu_period=SANDBOX_LIMITS["cpu_period"],
            cpu_quota=SANDBOX_LIMITS["cpu_quota"],
            pids_limit=SANDBOX_LIMITS["pids_limit"],
            network_mode="none",           # no network access
            read_only=False,
            remove=True,
            detach=False,
            stdout=True,
            stderr=True,
            timeout=SANDBOX_LIMITS["timeout"],
        )

        elapsed = int((time.time() - start) * 1000)
        output = container.decode("utf-8") if isinstance(container, bytes) else str(container)
        return SandboxResult(True, output, "", 0, elapsed)

    except ContainerError as e:
        elapsed = int((time.time() - start) * 1000)
        stderr = e.stderr.decode("utf-8") if e.stderr else str(e)
        return SandboxResult(False, "", stderr, e.exit_status, elapsed)

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.error(f"Sandbox execution error: {e}")
        return SandboxResult(False, "", str(e), 1, elapsed)


async def execute_tests(test_code: str, source_code: str, language: str = "python") -> SandboxResult:
    """Execute generated tests against source code in sandbox."""
    combined = f"{source_code}\n\n{test_code}"
    return await execute_code(combined, language)
