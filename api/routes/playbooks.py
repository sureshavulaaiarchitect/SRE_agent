from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import PlaybookResponse, PlaybookDetails
from api.auth import require_role, get_current_user
from pathlib import Path
import yaml
from infrastructure.database import get_db

router = APIRouter(prefix="/playbooks", tags=["playbooks"])
PLAYBOOKS_DIR = Path("playbooks/")

@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(user: dict = Depends(get_current_user)):
    """Return all playbook names, YAML content, and parsed details."""
    results = []
    for f in PLAYBOOKS_DIR.glob("*.yaml"):
        content = f.read_text()
        details = None
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            # Steps in YAML are dicts; extract a human-readable string per step.
            raw_steps = data.get('steps', [])
            step_labels = [
                f"{s.get('id', '?')}: {s.get('action', '?')}"
                if isinstance(s, dict) else str(s)
                for s in raw_steps
            ]
            details = PlaybookDetails(
                name=data.get('name', f.stem),
                description=data.get('description', 'No description'),
                trigger=data.get('trigger', 'automatic'),
                steps=step_labels
            )
        results.append(PlaybookResponse(name=f.stem, content=content, details=details))
    return results

@router.post("/{name}/execute")
async def execute_playbook(
    name: str,
    namespace: str = "default",
    pod_name: str = "manual-target",
    user: dict = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a playbook execution via the unified investigation service."""
    from agent.investigation import InvestigationService
    investigator = InvestigationService()
    
    # We trigger a full investigation which will result in a recommended action
    # The 'name' of the playbook can be used to influence the investigation if needed, 
    # but for now, we rely on the unified investigator to classify and recommend.
    result = await investigator.investigate_and_save(
        namespace=namespace,
        pod_name=pod_name,
        cluster_id="manual",
        db=db,
        reason="manual_trigger"
    )
    return {"status": "success", "incident": result}

@router.put("/{name}", response_model=PlaybookResponse)
async def update_playbook(
    name: str,
    content: str,
    user: dict = Depends(require_role("admin"))
):
    """Update a playbook (admin only). Validates YAML before saving."""
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    path = PLAYBOOKS_DIR / f"{name}.yaml"
    path.write_text(content)
    return PlaybookResponse(name=name, content=content)
