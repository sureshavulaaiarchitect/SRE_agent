import asyncio
import time
from dataclasses import dataclass
from kubernetes import client
import structlog

from infrastructure.kubernetes_client import get_core_v1_api, get_apps_v1_api

logger = structlog.get_logger(__name__)

@dataclass
class ValidationResult:
    success: bool
    message: str
    elapsed_seconds: float = 0.0

class ValidationEngine:
    @property
    def v1(self):
        return get_core_v1_api()

    async def validate_pod_recovery(
        self, namespace: str, pod_name: str, timeout: int = 120
    ) -> ValidationResult:
        """Poll pod status. For managed pods, searches for new pods if name changes."""
        start   = time.time()
        backoff = 2.0
        logger.info("Validating pod recovery", pod=pod_name, ns=namespace, timeout=timeout)

        # Try to get labels/owner of the original pod first to track it if it gets deleted
        labels = {}
        owner_name = ""
        try:
            old_pod = await asyncio.to_thread(self.v1.read_namespaced_pod, name=pod_name, namespace=namespace)
            labels = old_pod.metadata.labels or {}
            if old_pod.metadata.owner_references:
                owner_name = old_pod.metadata.owner_references[0].name
        except Exception:
            logger.debug("Could not get metadata for original pod", pod=pod_name)

        while time.time() - start < timeout:
            try:
                # 1. Try direct name match first
                pod = None
                try:
                    pod = await asyncio.to_thread(self.v1.read_namespaced_pod, name=pod_name, namespace=namespace)
                except Exception:
                    # 2. If name match fails (common for restarts), search by label/owner
                    if labels or owner_name:
                        label_selector = ",".join([f"{k}={v}" for k, v in labels.items() if k != "pod-template-hash"])
                        pods = await asyncio.to_thread(self.v1.list_namespaced_pod, namespace=namespace, label_selector=label_selector)
                        if pods.items:
                            # Pick the most recent pod
                            pod = sorted(pods.items, key=lambda x: x.metadata.creation_timestamp, reverse=True)[0]
                
                if pod and pod.status.phase == "Running":
                    container_statuses = pod.status.container_statuses or []
                    all_ready = all(c.ready for c in container_statuses)
                    if all_ready:
                        elapsed = round(time.time() - start, 1)
                        logger.info("Pod/Replica recovered successfully", pod=pod.metadata.name, elapsed=elapsed)
                        return ValidationResult(
                            success=True,
                            message=f"Pod {pod.metadata.name} is Running and all containers are ready.",
                            elapsed_seconds=elapsed
                        )
            except Exception as e:
                logger.debug("Validation loop error", error=str(e))

            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 15.0)

        elapsed = round(time.time() - start, 1)
        logger.warning("Pod validation timed out", pod=pod_name, elapsed=elapsed)
        return ValidationResult(
            success=False,
            message=f"Validation timeout after {timeout}s — manual check required for pod {pod_name}.",
            elapsed_seconds=elapsed
        )

    async def validate_deployment_health(
        self, namespace: str, deployment_name: str, timeout: int = 120
    ) -> ValidationResult:
        """Poll deployment until all replicas are available or timeout."""
        start   = time.time()
        backoff = 2.0
        apps_v1 = get_apps_v1_api()

        while time.time() - start < timeout:
            try:
                dep = await asyncio.to_thread(
                    apps_v1.read_namespaced_deployment,
                    name=deployment_name, namespace=namespace
                )
                status    = dep.status
                desired   = status.replicas or 0
                available = status.available_replicas or 0
                if desired > 0 and desired == available:
                    elapsed = round(time.time() - start, 1)
                    return ValidationResult(
                        success=True,
                        message=f"Deployment {deployment_name}: {available}/{desired} replicas available.",
                        elapsed_seconds=elapsed
                    )
            except Exception as e:
                logger.debug("Deployment status check failed", deployment=deployment_name, error=str(e))

            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 15.0)

        elapsed = round(time.time() - start, 1)
        return ValidationResult(
            success=False,
            message=f"Deployment {deployment_name} not fully healthy after {timeout}s.",
            elapsed_seconds=elapsed
        )

# Singleton instance
validation_engine = ValidationEngine()
