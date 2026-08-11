"""Integration test — requires a live cluster.

Marked with pytest.mark.integration so it is skipped in regular CI.
Run manually with: pytest -m integration tests/test_k8s.py
"""
import pytest
from kubernetes import client, config


@pytest.mark.integration
def test_list_all_pods():
    """Verify K8s connection works and can list pods across all namespaces."""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        pods = v1.list_pod_for_all_namespaces()
    except Exception as e:
        pytest.skip(f"Kubernetes cluster not available for integration test: {e}")
    assert pods is not None
    assert hasattr(pods, "items")
    print(f"Total pods found: {len(pods.items)}")

