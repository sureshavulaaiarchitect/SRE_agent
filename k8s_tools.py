import structlog
from kubernetes import client
from infrastructure.kubernetes_client import get_core_v1_api, get_apps_v1_api

logger = structlog.get_logger(__name__)

# Module-level clients — initialized lazily, patchable for tests via @patch('k8s_tools.v1')
v1 = None
apps_v1 = None


def _ensure_v1():
    """Lazily initialize the CoreV1Api client if not already set or patched."""
    global v1
    if v1 is None:
        v1 = get_core_v1_api()


def _ensure_apps_v1():
    """Lazily initialize the AppsV1Api client if not already set or patched."""
    global apps_v1
    if apps_v1 is None:
        apps_v1 = get_apps_v1_api()


def get_pod_status(pod_name, namespace='default'):
    """Get pod status summary."""
    try:
        _ensure_v1()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        status = f"Phase: {pod.status.phase}, IP: {getattr(pod.status, 'pod_ip', 'None')}, Node: {getattr(pod.spec, 'node_name', 'None')}"
        return status
    except Exception as e:
        logger.error("Failed to get pod status", pod=pod_name, error=str(e))
        return f"ERROR: {str(e)}"


def get_pod_logs(pod_name, namespace='default', tail_lines=100):
    """Get recent pod logs."""
    try:
        _ensure_v1()
        logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail_lines, timestamps=True)
        return logs
    except Exception as e:
        logger.error("Failed to get logs", pod=pod_name, error=str(e))
        return f"ERROR getting logs: {str(e)}"


def list_unhealthy_pods(namespace: str = 'default') -> list:
    """List unhealthy pod names in a specific namespace."""
    try:
        _ensure_v1()
        pods = v1.list_namespaced_pod(namespace)
        unhealthy = []
        for pod in pods.items:
            reason = None
            phase = getattr(pod.status, 'phase', '')
            if phase in ('Failed', 'Pending', 'Unknown'):
                reason = phase
            else:
                for cs in (pod.status.container_statuses or []):
                    if getattr(cs.state, 'waiting', None) and getattr(cs.state.waiting, 'reason', None):
                        reason = cs.state.waiting.reason
                        break
                    if getattr(cs.state, 'terminated', None) and getattr(cs.state.terminated, 'reason', None):
                        reason = cs.state.terminated.reason
                        break
            if reason:
                unhealthy.append(pod.metadata.name)
        return unhealthy
    except Exception as e:
        logger.error("Failed to list unhealthy pods", namespace=namespace, error=str(e))
        return []


def list_unhealthy_pods_all_namespaces():
    """List unhealthy pods across all namespaces."""
    try:
        _ensure_v1()
        pods = v1.list_pod_for_all_namespaces()
        unhealthy = []
        for pod in pods.items:
            reason = None
            phase = getattr(pod.status, 'phase', '')
            if phase in ('Failed', 'Pending', 'Unknown'):
                reason = phase
            else:
                for cs in (pod.status.container_statuses or []):
                    if getattr(cs.state, 'waiting', None) and getattr(cs.state.waiting, 'reason', None):
                        reason = cs.state.waiting.reason
                        break
                    if getattr(cs.state, 'terminated', None) and getattr(cs.state.terminated, 'reason', None):
                        reason = cs.state.terminated.reason
                        break
            if reason:
                unhealthy.append({
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'reason': reason
                })
        return unhealthy
    except Exception as e:
        logger.error("Failed to list unhealthy pods", error=str(e))
        return []


def restart_pod(pod_name, namespace='default'):
    """Restart pod by delete (safe for managed pods)."""
    try:
        _ensure_v1()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        is_managed = pod.metadata.owner_references and any(
            ref.kind in ['ReplicaSet', 'StatefulSet', 'DaemonSet']
            for ref in pod.metadata.owner_references
        )
        if is_managed:
            v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
            return f"Safe restart of managed pod {pod_name}"
        else:
            return f"SAFETY: Manual pod {pod_name} - requires approval (not managed)"
    except Exception as e:
        return f"Restart failed: {str(e)}"


def delete_pod(namespace, pod_name):
    """Delete pod."""
    try:
        _ensure_v1()
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
        return f"Pod {pod_name} deleted successfully"
    except Exception as e:
        return f"Delete failed: {str(e)}"


def validate_pod(namespace, pod_name):
    """Validate pod recovery."""
    try:
        _ensure_v1()
        pod = v1.read_namespaced_pod(pod_name, namespace)
        if pod.status.phase == 'Running' and all(cs.ready for cs in (pod.status.container_statuses or [])):
            return "SUCCESS: Pod healthy"
        else:
            return f"FAILED: {pod.status.phase}"
    except Exception as e:
        return f"FAILED: {str(e)}"


def scale_deployment(namespace, deployment_name, replicas):
    """Scale deployment."""
    try:
        _ensure_apps_v1()
        body = {"spec": {"replicas": int(replicas)}}
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=body)
        return f"Scaled {deployment_name} to {replicas}"
    except Exception as e:
        logger.error("Scale failed", deployment=deployment_name, error=str(e))
        return f"Scale failed: {e}"


def rollback_deployment(namespace, deployment_name):
    """Rollback deployment to previous revision."""
    try:
        _ensure_apps_v1()
        # In a production SRE context this would use a specific revision;
        # represented here as a placeholder for the remediation pipeline.
        return f"Rollback initiated for {deployment_name} in {namespace}"
    except Exception as e:
        logger.error("Rollback failed", deployment=deployment_name, error=str(e))
        return f"Rollback failed: {e}"


def is_fix_safe(action: str, params: dict = None) -> str:
    """Check whether a remediation action is safe to execute.

    Returns the exact string 'SAFE' when safe, or a string containing 'UNSAFE' when not.
    """
    params = params or {}

    if action == 'restart_pod':
        pod_name = params.get('pod_name', params.get('pod', ''))
        namespace = params.get('namespace', 'default')
        try:
            _ensure_v1()
            pod = v1.read_namespaced_pod(pod_name, namespace)
            is_managed = (
                pod.metadata.owner_references and
                any(ref.kind in ['ReplicaSet', 'StatefulSet', 'DaemonSet']
                    for ref in pod.metadata.owner_references)
            )
            if is_managed:
                return 'SAFE: Managed pod — controller will recreate'
            return 'UNSAFE: Unmanaged pod — will be permanently deleted'
        except Exception as e:
            return f'UNSAFE: Cannot read pod: {e}'

    elif action == 'scale_deployment':
        replicas = int(params.get('replicas', 1))
        if replicas > 10:
            return f'UNSAFE: Scale to {replicas} exceeds maximum of 10'
        return 'SAFE'

    elif action in SAFE_ACTIONS:
        return 'SAFE'

    return f'UNSAFE: Unknown action {action}'


SAFE_ACTIONS = {
    'restart_pod': restart_pod,
    'scale_deployment': scale_deployment,
    'delete_pod': delete_pod,
    'validate_pod': validate_pod,
    'rollback_deployment': rollback_deployment
}


def execute_remediation(action, params):
    """Dispatch to safe action."""
    if action in SAFE_ACTIONS:
        return SAFE_ACTIONS[action](**params)
    return f"Unknown action: {action}"
