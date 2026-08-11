import yaml
import asyncio
from pathlib import Path
from dataclasses import dataclass
import structlog
from typing import Any, Dict, List, Optional
from configs.config import settings

logger = structlog.get_logger(__name__)

@dataclass
class PlaybookResult:
    evidence: dict
    fast_path: bool = False

class PlaybookEngine:
    def __init__(self, action_registry: dict):
        self.playbooks_dir = Path(settings.PLAYBOOKS_PATH)
        self._action_registry = action_registry

    def _load(self, incident_type: str) -> dict:
        path = self.playbooks_dir / f"{incident_type}.yaml"
        if not path.exists():
            path = self.playbooks_dir / "unknown.yaml"
        with open(path) as f:
            return yaml.safe_load(f)

    async def run(self, incident_type: str, context: dict) -> PlaybookResult:
        logger.info("=== PLAYBOOK START ===", incident_type=incident_type)
        logger.info("Loading playbook YAML")
        playbook = self._load(incident_type)
        collected = {}

        # Support sequential, parallel, conditional sections
        sections = playbook.get("sections", [{"type": "sequential", "steps": playbook.get("steps", [])}])
        
        for section in sections:
            section_result = await self._execute_section(section, context, collected)
            collected[f"section_{section.get('id', 'unnamed')}"] = section_result

        logger.info("=== PLAYBOOK COMPLETE ===", evidence_keys=len(collected), fast_path=False)
        return PlaybookResult(evidence=collected, fast_path=False)

    async def _execute_section(self, section: dict, ctx: dict, collected: dict) -> dict:
        section_type = section.get("type", "sequential")
        
        if section_type == "parallel":
            return await self._execute_parallel(section["steps"], ctx, collected)
        elif section_type == "conditional":
            return await self._execute_conditional(section, ctx, collected)
        else:
            # Sequential (default)
            results = {}
            for step in section.get("steps", []):
                try:
                    result = await self._execute_step(step, ctx, collected)
                    results[step["id"]] = result
                    collected[step["id"]] = result

                    if self._should_early_return(result):
                        logger.info("Fast path triggered in sequential", step=step["id"])
                        return {"early_exit": True, "results": results}
                except Exception as e:
                    logger.error("Sequential step failed", step=step["id"], error=str(e))
                    results[step["id"]] = {"error": str(e)}
            return results

    async def _execute_parallel(self, steps: List[dict], ctx: dict, collected: dict) -> dict:
        """Execute steps concurrently with timeout."""
        logger.info("Executing parallel steps", step_count=len(steps))
        tasks = [self._execute_step(step, ctx, collected) for step in steps]
        try:
            # asyncio.gather doesn't support timeout directly, use wait_for
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=60.0
            )
            logger.info("✓ Parallel section completed")
        except asyncio.TimeoutError:
            logger.error("Parallel section timed out after 60s")
            # Cancel all tasks on timeout
            for task in tasks:
                if isinstance(task, asyncio.Task):
                    task.cancel()
            results = [{"timeout": True} for _ in steps]
        
        results_dict = {steps[i]["id"]: r for i, r in enumerate(results)}
        return results_dict

    async def _execute_conditional(self, section: dict, ctx: dict, collected: dict) -> dict:
        """Execute if/then/else branches."""
        condition = section.get("if")
        if self._evaluate_condition(condition, ctx, collected):
            logger.info("Conditional true, executing then branch")
            return await self._execute_section({"type": "sequential", "steps": section.get("then", [])}, ctx, collected)
        else:
            logger.info("Conditional false, executing else branch")
            return await self._execute_section({"type": "sequential", "steps": section.get("else", [])}, ctx, collected)

    async def _execute_step(self, step: dict, ctx: dict, collected: dict) -> Any:
        action_name = step["action"]
        if action_name not in self._action_registry:
            raise ValueError(f"Action '{action_name}' not found in registry")
            
        # Handle retry logic
        retries = step.get("retry", 0)
        backoff = step.get("backoff", 1.0)
        
        for attempt in range(retries + 1):
            try:
                action_fn = self._action_registry[action_name]
                resolved_args = self._resolve_args(step.get("args", {}), ctx, collected)
                
                logger.info("Executing step", step_id=step["id"], action=action_name, attempt=attempt+1)
                logger.debug("Step args resolved", args=resolved_args)
                
                if asyncio.iscoroutinefunction(action_fn):
                    result = await asyncio.wait_for(action_fn(**resolved_args), timeout=step.get("timeout", 60.0))
                else:
                    result = action_fn(**resolved_args)
                
                logger.info("✓ Step completed", step_id=step["id"], action=action_name)
                logger.debug("Step result", result_type=type(result).__name__)
                return result
            except Exception as e:
                logger.warning(f"Step attempt {attempt + 1} failed", step=step["id"], error=str(e))
                if attempt < retries:
                    await asyncio.sleep(backoff * (2 ** attempt))
                else:
                    raise

    def _should_early_return(self, result: Any) -> bool:
        return (isinstance(result, dict) and result.get("early_return") or 
                (hasattr(result, "source") and result.source == "pattern_db"))

    def _evaluate_condition(self, condition: str, ctx: dict, collected: dict) -> bool:
        """Safer condition evaluation replacing eval()."""
        if not condition:
            return True
        
        if condition.startswith("{{") and condition.endswith("}}"):
            expr = condition.strip("{}").strip()
            # Split into simple parts: "key operator value"
            parts = expr.split()
            if len(parts) == 3:
                key, op, val = parts
                local_vars = {**ctx, **collected}
                actual_val = local_vars.get(key)
                
                # Try to convert val to appropriate type
                if val.isdigit():
                    val = int(val)
                elif val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.startswith("'") and val.endswith("'"):
                    val = val.strip("'")
                
                try:
                    if op == "==": return actual_val == val
                    if op == "!=": return actual_val != val
                    if op == ">":  return float(actual_val) > float(val)
                    if op == "<":  return float(actual_val) < float(val)
                    if op == ">=": return float(actual_val) >= float(val)
                    if op == "<=": return float(actual_val) <= float(val)
                except (ValueError, TypeError):
                    logger.warning("Comparison failed", key=key, op=op, val=val)
                    return False
            
            logger.warning("Unsupported condition format", condition=condition)
            return False
            
        return condition.lower() == "true"

    async def execute_manual(self, playbook_name: str, namespace: str, pod_name: str) -> dict:
        """Manually trigger a specific playbook."""
        logger.info("Executing manual playbook", playbook=playbook_name, pod=pod_name)
        context = {"namespace": namespace, "pod_name": pod_name}
        return await self.run(playbook_name, context)

    async def run_action(self, action_name: str, context: dict) -> Any:
        """Execute a single action directly from the registry."""
        if action_name not in self._action_registry:
            logger.warning("Action not found in registry", action=action_name)
            return f"Action {action_name} not available"
            
        action_fn = self._action_registry[action_name]
        args = {k: v for k, v in context.items() if k in ["namespace", "pod_name", "pod"]}
        
        logger.info("Executing direct action", action=action_name)
        if asyncio.iscoroutinefunction(action_fn):
            return await action_fn(**args)
        else:
            return action_fn(**args)

    def _resolve_args(self, args: dict, ctx: dict, collected: dict) -> dict:
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                var_name = v.strip("{}").strip()
                if var_name in ctx:
                    resolved[k] = ctx[var_name]
                elif var_name in collected:
                    resolved[k] = collected[var_name]
                elif var_name == "collected_evidence":
                    resolved[k] = collected
                else:
                    resolved[k] = None
            else:
                resolved[k] = v
        return resolved

