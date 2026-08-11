import asyncio
import subprocess
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


# =========================
# MODEL
# =========================
class Evidence(BaseModel):
    namespace: str
    pod_name: str
    logs: str
    describe: str
    events: str
    reason: str
    exit_code: Optional[int] = None
    phase: Optional[str] = "Unknown"
    restart_count: Optional[int] = 0
    image: Optional[str] = "unknown"
    owner_ref: Optional[str] = None
    containers_status: Dict[str, Any] = Field(default_factory=dict)


# =========================
# SAFE COMMAND EXECUTOR
# =========================
def run_cmd(cmd: list[str], timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            logger.warning(
                "Command failed",
                cmd=" ".join(cmd),
                error=result.stderr.strip()
            )
            return result.stderr.strip() or "Command failed"

        return result.stdout.strip() or "No output"

    except subprocess.TimeoutExpired:
        logger.error("Command timeout", cmd=" ".join(cmd))
        return "Command timeout"

    except Exception as e:
        logger.error("Command execution error", cmd=" ".join(cmd), error=str(e))
        return f"Command failed: {str(e)}"


# =========================
# EVIDENCE COLLECTION
# =========================
def collect_evidence(namespace: str, pod_name: str) -> dict:

    # logs with fallback to previous
    logs = run_cmd([
        "kubectl", "logs", pod_name,
        "-n", namespace,
        "--all-containers=true",
        "--tail=200"
    ])

    if "error" in logs.lower() or "not found" in logs.lower():
        logs_prev = run_cmd([
            "kubectl", "logs", pod_name,
            "-n", namespace,
            "--previous",
            "--tail=200"
        ])
        if logs_prev:
            logs = logs_prev

    describe = run_cmd([
        "kubectl", "describe", "pod", pod_name,
        "-n", namespace
    ])

    events = run_cmd([
        "kubectl", "get", "events",
        "-n", namespace,
        "--sort-by=.metadata.creationTimestamp"
    ])

    # =========================
    # REASON DETECTION
    # =========================
    describe_lower = describe.lower()

    if "crashloopbackoff" in describe_lower or "back-off restarting" in describe_lower:
        reason = "CrashLoopBackOff"
    elif "oomkilled" in describe_lower:
        reason = "OOMKilled"
    elif "imagepullbackoff" in describe_lower or "errimagepull" in describe_lower:
        reason = "ImagePullBackOff"
    elif "containercannotrun" in describe_lower:
        reason = "ContainerCannotRun"
    elif "error" in describe_lower:
        reason = "Error"
    else:
        reason = "unknown"

    return {
        "logs": logs or "No logs available",
        "describe": describe or "Describe failed",
        "events": events or "Events unavailable",
        "reason": reason
    }


# =========================
# ASYNC COLLECTOR
# =========================
class EvidenceCollector:

    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    async def collect_full_evidence(self, namespace: str, pod_name: str) -> Evidence:
        loop = asyncio.get_running_loop()

        evidence_dict = await loop.run_in_executor(
            None,
            collect_evidence,
            namespace,
            pod_name
        )

        describe = evidence_dict.get("describe", "")

        # =========================
        # PARSING
        # =========================
        phase = self._extract(r"Phase:\s*([^\n]+)", describe, default="Unknown")
        restart_count = int(self._extract(r"Restart Count:\s*(\d+)", describe, default="0"))
        image = self._extract(r"Image:\s*([^\s\n]+)", describe, default="unknown")

        exit_code_raw = self._extract(r"Exit Code:\s*(\d+)", describe)
        exit_code = int(exit_code_raw) if exit_code_raw else None

        owner_ref = self._extract(r"Controlled By:\s*([^\n]+)", describe)

        containers_status = {}
        if exit_code is not None:
            containers_status[pod_name] = {
                "exit_code": exit_code,
                "reason": evidence_dict.get("reason", "unknown")
            }

        evidence = Evidence(
            namespace=namespace,
            pod_name=pod_name,
            logs=evidence_dict["logs"],
            describe=describe,
            events=evidence_dict["events"],
            reason=evidence_dict["reason"],
            phase=phase,
            exit_code=exit_code,
            restart_count=restart_count,
            image=image,
            owner_ref=owner_ref,
            containers_status=containers_status
        )

        self.logger.info(
            "Evidence collected",
            pod=pod_name,
            namespace=namespace,
            reason=evidence.reason,
            restarts=restart_count
        )

        return evidence

    # =========================
    # HELPER
    # =========================
    def _extract(self, pattern: str, text: str, default: Optional[str] = None) -> Optional[str]:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default