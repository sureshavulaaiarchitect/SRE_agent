SYSTEM_PROMPT = '''\
You are a Kubernetes SRE agent.
Analyze the incident and return STRICT JSON only.

Input:
Pod: {pod_name}
Namespace: {namespace}
Reason: {reason}
Logs: {logs}

Output JSON:
{{
"root_cause": "...",
"confidence": "low|medium|high",
"action": "restart_pod|manual_investigation",
"explanation": "..."
}}

Do NOT ask questions. Do NOT explain outside JSON.
'''


def build_analysis_prompt(evidence) -> str:
    # Handle both dict (from tests) and Evidence object (from runtime)
    is_dict = isinstance(evidence, dict)

    def get_val(key, default=None):
        if is_dict:
            return evidence.get(key, default)
        return getattr(evidence, key, default)

    evidence_dict = {
        "pod_name": get_val("pod_name", "unknown"),
        "namespace": get_val("namespace", "unknown"),
        "reason": get_val("reason", get_val("phase", "unknown")),
        "logs": str(get_val("logs", "No logs available"))[:1000]
    }
    return SYSTEM_PROMPT.format(**evidence_dict)
