from kubernetes import client, config
import structlog
import os

logger = structlog.get_logger(__name__)

_initialized = False

def init_k8s_client():
    """Initializes the Kubernetes client. Tries in-cluster config first, then kubeconfig."""
    global _initialized
    if _initialized:
        return

    try:
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
            
            # Even in-cluster, honor KUBERNETES_INSECURE for testing or air-gapped setups
            is_insecure = os.getenv("KUBERNETES_INSECURE", "false").lower() == "true"
            if is_insecure:
                c = client.Configuration.get_default_copy()
                c.verify_ssl = False
                client.Configuration.set_default(c)
                logger.warning("SSL verification DISABLED for in-cluster Kubernetes API")
            
            _initialized = True
        else:
            config.load_kube_config()
            
            is_insecure = os.getenv("KUBERNETES_INSECURE", "false").lower() == "true"
            
            if is_insecure:
                c = client.Configuration.get_default_copy()
                c.verify_ssl = False
                client.Configuration.set_default(c)
                logger.warning("SSL verification DISABLED for local Kubernetes API (KUBERNETES_INSECURE=true)")
            else:
                c = client.Configuration.get_default_copy()
                c.verify_ssl = True
                client.Configuration.set_default(c)
                logger.info("Loaded local kubeconfig (SSL VERIFICATION ENABLED)")
            
            _initialized = True
    except config.ConfigException as e:
        logger.error("Failed to load any Kubernetes configuration", error=str(e))
        raise e

def get_core_v1_api() -> client.CoreV1Api:
    """Returns a CoreV1Api client, ensuring configuration is loaded."""
    if not _initialized:
        init_k8s_client()
    api_client = client.ApiClient()
    # Hardened: default 10s timeout for all K8s calls
    api_client.request_timeout = 10.0
    return client.CoreV1Api(api_client)

def get_apps_v1_api() -> client.AppsV1Api:
    """Returns an AppsV1Api client, ensuring configuration is loaded."""
    if not _initialized:
        init_k8s_client()
    api_client = client.ApiClient()
    # Hardened: default 10s timeout for all K8s calls
    api_client.request_timeout = 10.0
    return client.AppsV1Api(api_client)

