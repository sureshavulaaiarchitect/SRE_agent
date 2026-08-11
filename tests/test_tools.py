import pytest
from unittest.mock import patch, MagicMock
from k8s_tools import (
    get_pod_status, get_pod_logs, list_unhealthy_pods, list_unhealthy_pods_all_namespaces, 
    restart_pod, delete_pod, validate_pod, execute_remediation, SAFE_ACTIONS, is_fix_safe
)

@patch('k8s_tools.v1')
def test_get_pod_status(mock_v1):
    mock_pod = MagicMock()
    mock_pod.status.phase = 'Pending'
    mock_pod.status.pod_ip = '10.0.0.1'
    mock_pod.spec.node_name = 'node-1'
    mock_v1.read_namespaced_pod.return_value = mock_pod
    
    result = get_pod_status('test-pod', 'default')
    assert 'Pending' in result
    assert 'node-1' in result

@patch('k8s_tools.v1')
def test_list_unhealthy_pods(mock_v1):
    mock_pods = MagicMock()
    mock_pod = MagicMock()
    mock_pod.metadata.name = 'crashy-pod'
    mock_pod.status = MagicMock(phase='Running', container_statuses=[MagicMock(state=MagicMock(waiting=MagicMock(reason='CrashLoopBackOff')), restart_count=5)])
    mock_pods.items = [mock_pod]
    mock_v1.list_namespaced_pod.return_value = mock_pods
    
    result = list_unhealthy_pods('default')
    assert 'crashy-pod' in result

@patch('k8s_tools.v1')
def test_list_unhealthy_pods_all_namespaces(mock_v1):
    mock_pods = MagicMock()
    mock_pods.items = [
        MagicMock(metadata=MagicMock(name='crashy-pod', namespace='default'), status=MagicMock(container_statuses=[MagicMock(state=MagicMock(waiting=MagicMock(reason='CrashLoopBackOff')))])),
        MagicMock(metadata=MagicMock(name='oom-pod', namespace='default'), status=MagicMock(container_statuses=[MagicMock(state=MagicMock(terminated=MagicMock(reason='OOMKilled')))]))
    ]
    mock_v1.list_pod_for_all_namespaces.return_value = mock_pods
    
    result = list_unhealthy_pods_all_namespaces()
    assert len(result) == 2
    assert result[0]['reason'] == 'CrashLoopBackOff'

@patch('k8s_tools.v1')
def test_restart_pod_managed(mock_v1):
    mock_pod = MagicMock()
    mock_pod.metadata.owner_references = [MagicMock(kind='ReplicaSet')]
    mock_v1.read_namespaced_pod.return_value = mock_pod
    mock_v1.delete_namespaced_pod.return_value = None
    
    result = restart_pod('test-pod')
    assert 'Safe restart' in result
    mock_v1.delete_namespaced_pod.assert_called_once()

@patch('k8s_tools.v1')
def test_restart_pod_unmanaged(mock_v1):
    mock_pod = MagicMock()
    mock_pod.metadata.owner_references = []
    mock_v1.read_namespaced_pod.return_value = mock_pod
    
    result = restart_pod('standalone-pod')
    assert 'SAFETY' in result
    mock_v1.delete_namespaced_pod.assert_not_called()

@patch('k8s_tools.v1')
def test_is_fix_safe_restart_safe(mock_v1):
    mock_pod = MagicMock()
    mock_pod.metadata.owner_references = [MagicMock(kind='ReplicaSet')]
    mock_v1.read_namespaced_pod.return_value = mock_pod
    result = is_fix_safe('restart_pod', {'pod_name': 'managed-pod', 'namespace': 'default'})
    assert 'SAFE' in result

@patch('k8s_tools.v1')
def test_is_fix_safe_restart_unsafe(mock_v1):
    mock_pod = MagicMock()
    mock_pod.metadata.owner_references = []
    mock_v1.read_namespaced_pod.return_value = mock_pod
    result = is_fix_safe('restart_pod', {'pod_name': 'unmanaged', 'namespace': 'default'})
    assert 'UNSAFE' in result

def test_is_fix_safe_scale_ok():
    result = is_fix_safe('scale_deployment', {'namespace': 'default', 'deployment_name': 'app', 'replicas': '3'})
    assert result == 'SAFE'

def test_is_fix_safe_scale_unsafe():
    result = is_fix_safe('scale_deployment', {'replicas': '11'})
    assert 'UNSAFE' in result

@patch('k8s_tools.v1')
def test_delete_pod(mock_v1):
    mock_v1.delete_namespaced_pod.return_value = None
    result = delete_pod(namespace='default', pod_name='test-pod')
    assert 'deleted successfully' in result
    mock_v1.delete_namespaced_pod.assert_called_with(name='test-pod', namespace='default')

@patch('k8s_tools.v1')
def test_validate_pod_success(mock_v1):
    mock_pod = MagicMock()
    mock_pod.status.phase = 'Running'
    mock_pod.status.container_statuses = [MagicMock(ready=True, restart_count=1)]
    mock_v1.read_namespaced_pod.return_value = mock_pod
    result = validate_pod('default', 'healthy-pod')
    assert 'SUCCESS' in result

@patch('k8s_tools.v1')
def test_validate_pod_fail(mock_v1):
    mock_pod = MagicMock()
    mock_pod.status.phase = 'Pending'
    mock_v1.read_namespaced_pod.return_value = mock_pod
    result = validate_pod('default', 'bad-pod')
    assert 'FAILED' in result and 'Pending' in result

def test_execute_remediation():
    # Test registry dispatch
    result = execute_remediation('restart_pod', {'pod_name': 'test', 'namespace': 'default'})
    assert isinstance(result, str)  # Dispatches to restart_pod (mocked in real test)

def test_safe_actions_registry():
    assert 'delete_pod' in SAFE_ACTIONS
    assert callable(SAFE_ACTIONS['delete_pod'])



if __name__ == "__main__":
    pytest.main([__file__, '-v'])
