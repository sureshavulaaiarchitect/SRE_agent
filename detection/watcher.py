import asyncio
from kubernetes import watch
from dataclasses import dataclass
from datetime import datetime
import structlog
from observability.metrics_collector import errors_total

logger = structlog.get_logger(__name__)

_DEDUPE_TTL = 300  # seconds — how long to suppress the same pod UID
_PRUNE_EVERY = 50  # prune stale entries every N pods processed


# Incident event model
@dataclass
class IncidentEvent:
    event_type: str
    reason: str
    message: str
    pod_name: str
    namespace: str
    node_name: str
    cluster_id: str
    timestamp: datetime
    raw_event: dict


# Watcher service
class IncidentDetectionService:

    IGNORED_NAMESPACES = {
        "kube-system",
        "kube-public",
        "kube-node-lease"
    }

    def __init__(self, queue: asyncio.Queue, cluster_id: str):
        self.queue = queue
        self.cluster_id = cluster_id
        self._running = False
        # {pod_uid: last_seen_timestamp} — pruned periodically to prevent unbounded growth
        self._processed_pods: dict[str, float] = {}
        self._pods_seen_since_prune = 0

        # Use the centralised client (respects KUBERNETES_INSECURE env var, no hardcoded SSL disable)
        from infrastructure.kubernetes_client import init_k8s_client, get_core_v1_api
        init_k8s_client()
        self.v1 = get_core_v1_api()
        logger.info("Kubernetes watcher initialised", cluster_id=cluster_id)

    async def start(self):
        self._running = True
        backoff = 1
        main_loop = asyncio.get_running_loop()

        while self._running:
            try:
                logger.info(
                    "Starting Kubernetes pod watch stream",
                    cluster_id=self.cluster_id
                )
                await asyncio.to_thread(self._watch_loop, main_loop)
                backoff = 1  # reset on clean exit
            except Exception as exc:
                logger.error(
                    "Kubernetes event stream disconnected",
                    cluster_id=self.cluster_id,
                    error=str(exc),
                    retry_in=backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _watch_loop(self, main_loop):
        """Blocking watch loop — runs in a thread via asyncio.to_thread."""
        w = watch.Watch()
        try:
            for raw in w.stream(self.v1.list_pod_for_all_namespaces):
                if not self._running:
                    break

                pod = raw["object"]
                uid = pod.metadata.uid
                now = datetime.utcnow().timestamp()

                # Periodic pruning of stale entries to prevent memory leak
                self._pods_seen_since_prune += 1
                if self._pods_seen_since_prune >= _PRUNE_EVERY:
                    self._prune_dedup_cache(now)
                    self._pods_seen_since_prune = 0

                # Deduplication: skip if same UID seen within TTL
                last_seen = self._processed_pods.get(uid)
                if last_seen is not None and (now - last_seen) < _DEDUPE_TTL:
                    continue

                if self._is_pod_incident(pod):
                    event = self._create_incident_event(pod)
                    logger.info(
                        "Kubernetes incident detected",
                        cluster_id=self.cluster_id,
                        pod_name=event.pod_name,
                        namespace=event.namespace,
                        reason=event.reason,
                    )
                    self._processed_pods[uid] = now

                    # Thread-safe enqueue with overflow protection
                    def _safe_enqueue(e=event):
                        try:
                            self.queue.put_nowait(e)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Incident queue full — event dropped",
                                pod=e.pod_name,
                                namespace=e.namespace,
                                cluster_id=self.cluster_id,
                            )
                            errors_total.labels(
                                module="watcher", error_type="QueueFull"
                            ).inc()

                    main_loop.call_soon_threadsafe(_safe_enqueue)

        except Exception as e:
            logger.error("Watch loop crashed", error=str(e))
            raise

    def _prune_dedup_cache(self, now: float) -> None:
        """Remove entries older than _DEDUPE_TTL to prevent unbounded growth."""
        cutoff = now - _DEDUPE_TTL
        stale = [uid for uid, ts in self._processed_pods.items() if ts < cutoff]
        for uid in stale:
            del self._processed_pods[uid]
        if stale:
            logger.debug("Pruned dedup cache", removed=len(stale), remaining=len(self._processed_pods))

    def stop(self):
        self._running = False

    def _is_pod_incident(self, pod) -> bool:
        """
        Detect real failure states only
        """

        if pod.metadata.namespace in self.IGNORED_NAMESPACES:
            return False

        FAILURE_REASONS = {
            'CrashLoopBackOff',
            'ImagePullBackOff',
            'ErrImagePull',
            'OOMKilled',
            'Error',
            'ContainerCannotRun',
            'RunContainerError',
            'CreateContainerError',
            'BackOff'
        }

        if not pod.status or not pod.status.container_statuses:
            return False

        for container in pod.status.container_statuses:

            if container.state and container.state.waiting:
                reason = getattr(container.state.waiting, 'reason', '')
                if reason in FAILURE_REASONS:
                    return True

            if container.state and container.state.terminated:
                reason = getattr(container.state.terminated, 'reason', '')

                if reason == 'OOMKilled':
                    return True

                exit_code = getattr(container.state.terminated, 'exit_code', 0)
                if exit_code and exit_code != 0:
                    return True

        return pod.status.phase == 'Failed'

    def _create_incident_event(self, pod) -> IncidentEvent:
        """
        Convert pod → IncidentEvent
        """

        reason = 'Unknown'

        for container in (pod.status.container_statuses or []):
            if container.state and container.state.waiting:
                reason = getattr(container.state.waiting, 'reason', 'Unknown')
                break
            if container.state and container.state.terminated:
                reason = getattr(container.state.terminated, 'reason', 'Unknown')
                break

        return IncidentEvent(
            event_type='Warning',
            reason=reason,
            message=f'Pod {pod.metadata.name} in failure state',
            pod_name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            node_name=getattr(pod.status, 'node_name', 'Unknown'),
            cluster_id=self.cluster_id,
            timestamp=datetime.utcnow(),
            raw_event={'object': pod}
        )