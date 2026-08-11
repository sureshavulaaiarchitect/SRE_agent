from infrastructure.evidence_collector import EvidenceCollector
import asyncio

async def crashloop_playbook(namespace: str, pod_name: str) -> dict:
    """
    Playbook for CrashLoopBackOff and general pod crashes.
    """
    # 1. Collect structured evidence in parallel
    collector = EvidenceCollector()
    evidence_obj = await collector.collect_full_evidence(namespace, pod_name)
    
    # 2. Analysis logic (simplified or AI-driven)
    # Note: In production, this would call AIRootCauseEngine for deep analysis
    analysis = f"Pod {pod_name} is in phase {evidence_obj.phase}. Exit code: {evidence_obj.exit_code}"
    
    # 3. Recommendation logic
    if evidence_obj.owner_ref:
        fix_desc = "Delete pod to restart container"
    else:
        fix_desc = "Delete standalone pod (manual recreation required)"
        
    logs_str = evidence_obj.logs or ""
    return {
        "Incident Detected": True,
        "Pod": pod_name,
        "Namespace": namespace,
        "Status": "CrashLoopBackOff",
        "Evidence": {
            "Exit Code": evidence_obj.exit_code,
            "Restart Count": evidence_obj.restart_count,
            "Image": evidence_obj.image,
            "Logs": logs_str[:100] + "..." if len(logs_str) > 100 else logs_str
        },
        "Root Cause": analysis,
        "Recommended Fix": fix_desc,
        "Approval Required": "yes",
        "Action Tool": "restart_pod",
        "Action Args": {"namespace": namespace, "pod_name": pod_name}
    }
