from dataclasses import dataclass
from typing import Optional
import asyncio
import structlog
from kubernetes.client.rest import ApiException
import time
from configs.config import settings

from infrastructure.kubernetes_client import get_core_v1_api, get_apps_v1_api

logger = structlog.get_logger(__name__)


@dataclass
class RemediationContext:
    pod_name: str
    namespace: str
    deployment_name: Optional[str] = None
    target_replicas: Optional[int] = None
    new_memory_limit: Optional[str] = None


@dataclass
class RemediationResult:
    action: str
    success: bool
    message: str = ""


class RemediationEngine:

    ACTION_HANDLERS = {
        "restart_pod": "_restart_pod",
        "rollback_deployment": "_rollback_deployment",
        "scale_deployment": "_scale_deployment",
        "increase_limits": "_increase_resource_limits",
        "manual_investigation": "_handle_manual_investigation",
    }

    @property
    def v1(self):
        return get_core_v1_api()

    @property
    def apps_v1(self):
        return get_apps_v1_api()

    def __init__(self):
        from configs.config import settings
        self.settings = settings
        # pod_key -> list of timestamps
        self._action_history: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def execute(self, action: str, context: RemediationContext) -> RemediationResult:
        handler_name = self.ACTION_HANDLERS.get(action)

        if not handler_name:
            return RemediationResult(action=action, success=False, message="Unknown action")

        try:
            # auto-detect deployment if missing
            if not context.deployment_name:
                context.deployment_name = await self._find_deployment_name(
                    context.pod_name, context.namespace
                )

            handler = getattr(self, handler_name)

            logger.info(
                "Executing remediation",
                action=action,
                pod=context.pod_name,
                namespace=context.namespace,
                deployment=context.deployment_name
            )

            return await handler(context)

        except Exception as e:
            logger.error("Remediation failed", action=action, error=str(e))
            return RemediationResult(action=action, success=False, message=str(e))

    # -------------------------
    # DISCOVERY
    # -------------------------
    async def _find_deployment_name(self, pod_name: str, namespace: str) -> Optional[str]:
        try:
            pod = await asyncio.to_thread(
                self.v1.read_namespaced_pod,
                name=pod_name,
                namespace=namespace
            )

            owners = pod.metadata.owner_references or []

            for owner in owners:
                if owner.kind == "ReplicaSet":
                    rs = await asyncio.to_thread(
                        self.apps_v1.read_namespaced_replica_set,
                        name=owner.name,
                        namespace=namespace
                    )

                    if rs.metadata.owner_references:
                        for rs_owner in rs.metadata.owner_references:
                            if rs_owner.kind == "Deployment":
                                return rs_owner.name

                    # Fallback for older K8s or direct RS
                    return owner.name.rsplit("-", 1)[0]

                if owner.kind == "Deployment":
                    return owner.name

            return None

        except Exception as e:
            logger.warning("Deployment discovery failed", error=str(e))
            return None

    # -------------------------
    # ACTIONS
    # -------------------------
    async def _restart_pod(self, ctx: RemediationContext) -> RemediationResult:
        try:
            # 1. Prefer rollout restart if deployment name is known
            if ctx.deployment_name:
                logger.info("Performing rollout restart", deployment=ctx.deployment_name)
                patch_body = {
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "kubectl.kubernetes.io/restartedAt": str(time.time())
                                }
                            }
                        }
                    }
                }
                await asyncio.to_thread(
                    self.apps_v1.patch_namespaced_deployment,
                    name=ctx.deployment_name,
                    namespace=ctx.namespace,
                    body=patch_body
                )
                
                # Verify deployment becomes healthy
                if ctx.deployment_name and await self._verify_deployment_healthy(ctx.namespace, ctx.deployment_name):
                    return RemediationResult(
                        action="restart_pod",
                        success=True,
                        message=f"Deployment {ctx.deployment_name} successfully restarted"
                    )
                else:
                    return RemediationResult(
                        action="restart_pod",
                        success=False,
                        message=f"Deployment {ctx.deployment_name} restart failed validation"
                    )
            
            # 2. Fallback: Pod not managed by Deployment
            logger.info("Pod not controlled by Deployment, fallback to manual_investigation", pod=ctx.pod_name)
            return RemediationResult(
                action="manual_investigation",
                success=True,
                message=f"Pod {ctx.pod_name} is not managed by a Deployment. Action changed to manual_investigation."
            )

        except ApiException as e:
            return RemediationResult("restart_pod", False, str(e))

    async def _verify_deployment_healthy(self, namespace: str, deployment_name: str) -> bool:
        """Poll up to 45s: deployment has all replicas ready."""
        for i in range(15):  # 15 polls x 3s = 45s
            try:
                deploy = await asyncio.to_thread(
                    self.apps_v1.read_namespaced_deployment,
                    name=deployment_name,
                    namespace=namespace
                )
                if deploy.status.ready_replicas and deploy.status.ready_replicas >= (deploy.spec.replicas or 1):
                    logger.info(f"Deployment healthy: {deployment_name}")
                    return True
            except Exception:
                pass
            await asyncio.sleep(3)
        return False

    async def _verify_pod_recreated(self, namespace: str, pod_name: str) -> bool:
        """Poll up to 30s: pod exists, phase!=Pending/Failed."""
        # Note: This is now only used for standalone pods or as a 404 check fallback
        for i in range(10):  # 10 polls x 3s = 30s
            try:
                pod = await asyncio.to_thread(
                    self.v1.read_namespaced_pod,
                    name=pod_name,
                    namespace=namespace
                )
                if pod.status.phase in ['Running', 'Succeeded']:
                    return True
            except ApiException as e:
                # If it's a 404, the pod is gone. For managed pods, it will never reappear with same name.
                if e.status == 404:
                     # Check if ANY pod in namespace is now running (dirty check for fallback)
                     return False
            except Exception:
                pass
            await asyncio.sleep(3)
        return False

    async def _rollback_deployment(self, ctx: RemediationContext) -> RemediationResult:
        """
        Real rollback: finds the previous-revision ReplicaSet and re-applies
        its container images to the deployment.  Falls back to a rolling restart
        only if no previous revision exists (first deploy scenario).
        """
        if not ctx.deployment_name:
            return RemediationResult("rollback_deployment", False, "Deployment not found")

        try:
            # 1. Get current deployment and its revision number
            deployment = await asyncio.to_thread(
                self.apps_v1.read_namespaced_deployment,
                name=ctx.deployment_name,
                namespace=ctx.namespace,
            )
            annotations = deployment.metadata.annotations or {}
            current_rev = int(annotations.get("deployment.kubernetes.io/revision", "1"))
            target_rev = current_rev - 1

            if target_rev < 1:
                logger.warning(
                    "No previous revision to roll back to — triggering rolling restart",
                    deployment=ctx.deployment_name,
                    current_revision=current_rev,
                )
                # Graceful degradation: rolling restart so pods pick up any
                # external fixes (e.g. the image was re-pushed to the same tag)
                patch_body = {
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "kubectl.kubernetes.io/restartedAt": str(time.time())
                                }
                            }
                        }
                    }
                }
                await asyncio.to_thread(
                    self.apps_v1.patch_namespaced_deployment,
                    name=ctx.deployment_name,
                    namespace=ctx.namespace,
                    body=patch_body,
                )
                return RemediationResult(
                    action="rollback_deployment",
                    success=True,
                    message=f"{ctx.deployment_name}: no prior revision — rolling restart triggered",
                )

            # 2. List all ReplicaSets owned by this deployment
            label_selector = ",".join(
                f"{k}={v}"
                for k, v in (deployment.spec.selector.match_labels or {}).items()
            )
            rs_list = await asyncio.to_thread(
                self.apps_v1.list_namespaced_replica_set,
                namespace=ctx.namespace,
                label_selector=label_selector,
            )

            # 3. Find the RS that corresponds to the target revision
            target_rs = None
            for rs in rs_list.items:
                rs_annotations = rs.metadata.annotations or {}
                rs_rev = int(rs_annotations.get("deployment.kubernetes.io/revision", "0"))
                if rs_rev == target_rev:
                    target_rs = rs
                    break

            if target_rs is None:
                return RemediationResult(
                    "rollback_deployment",
                    False,
                    f"Cannot find ReplicaSet for revision {target_rev} of {ctx.deployment_name}",
                )

            # 4. Re-apply the previous revision’s container images (targeted patch)
            prev_containers = target_rs.spec.template.spec.containers or []
            container_patches = [
                {"name": c.name, "image": c.image} for c in prev_containers
            ]

            patch_body = {
                "spec": {
                    "template": {
                        "spec": {"containers": container_patches}
                    }
                }
            }

            await asyncio.to_thread(
                self.apps_v1.patch_namespaced_deployment,
                name=ctx.deployment_name,
                namespace=ctx.namespace,
                body=patch_body,
            )

            logger.info(
                "Deployment rolled back to previous revision",
                deployment=ctx.deployment_name,
                from_rev=current_rev,
                to_rev=target_rev,
                images=[c["image"] for c in container_patches],
            )
            return RemediationResult(
                action="rollback_deployment",
                success=True,
                message=(
                    f"{ctx.deployment_name} rolled back from rev {current_rev} → rev {target_rev}: "
                    + ", ".join(c["image"] for c in container_patches)
                ),
            )

        except ApiException as e:
            return RemediationResult("rollback_deployment", False, str(e))

    async def _scale_deployment(self, ctx: RemediationContext) -> RemediationResult:
        if not ctx.deployment_name:
            return RemediationResult("scale_deployment", False, "Deployment not found")

        replicas = ctx.target_replicas or 2

        try:
            await asyncio.to_thread(
                self.apps_v1.patch_namespaced_deployment_scale,
                name=ctx.deployment_name,
                namespace=ctx.namespace,
                body={"spec": {"replicas": replicas}}
            )

            return RemediationResult(
                action="scale_deployment",
                success=True,
                message=f"Scaled to {replicas}"
            )

        except ApiException as e:
            return RemediationResult("scale_deployment", False, str(e))

    async def _increase_resource_limits(self, ctx: RemediationContext) -> RemediationResult:
        if not ctx.deployment_name:
            return RemediationResult("increase_limits", False, "Deployment not found")

        new_limit = ctx.new_memory_limit or "512Mi"

        try:
            deployment = await asyncio.to_thread(
                self.apps_v1.read_namespaced_deployment,
                name=ctx.deployment_name,
                namespace=ctx.namespace
            )

            container_name = deployment.spec.template.spec.containers[0].name

            patch_body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": container_name,
                                    "resources": {
                                        "limits": {
                                            "memory": new_limit
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }

            await asyncio.to_thread(
                self.apps_v1.patch_namespaced_deployment,
                name=ctx.deployment_name,
                namespace=ctx.namespace,
                body=patch_body
            )

            return RemediationResult(
                action="increase_limits",
                success=True,
                message=f"Memory updated to {new_limit}"
            )

        except ApiException as e:
            return RemediationResult("increase_limits", False, str(e))

    async def _handle_manual_investigation(self, ctx: RemediationContext) -> RemediationResult:
        return RemediationResult(
            action="manual_investigation",
            success=True,
            message="Manual investigation required - no auto-remediation"
        )


# Singleton
remediation_engine = RemediationEngine()
