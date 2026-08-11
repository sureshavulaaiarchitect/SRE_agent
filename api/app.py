from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from api.routes import incidents, approvals, clusters, playbooks
from api.auth import create_access_token
from api.schemas import TokenRequest, TokenResponse
from api.websocket import feed_manager
from infrastructure.kubernetes_client import init_k8s_client
from observability import metrics_router
from configs.config import settings
import structlog
import asyncio
import json
from fastapi.responses import Response

logger = structlog.get_logger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous SRE Agent API",
        description="AI-powered Kubernetes incident detection and remediation platform.",
        version="2.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.include_router(incidents.router)
    app.include_router(approvals.router)
    app.include_router(clusters.router)
    app.include_router(playbooks.router)
    app.include_router(metrics_router)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutting down...")
        await feed_manager.shutdown()

    @app.post("/auth/token", response_model=TokenResponse)
    async def login(form_data: TokenRequest):
        from api.auth import verify_credentials
        role = verify_credentials(form_data.username, form_data.password)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        access_token = create_access_token(form_data.username, role)
        return TokenResponse(access_token=access_token)

    @app.websocket("/ws/incidents")
    async def incident_websocket(websocket: WebSocket, client_id: str = "unknown", token: str = None):
        if not token or token != settings.WS_AUTH_TOKEN:
             await websocket.close(code=1008, reason="Unauthorized")
             return

        client_ip = websocket.client.host if websocket.client else "unknown"
        
        success = await feed_manager.connect(websocket, client_id, client_ip)
        if not success:
            return

        try:
            while True:
                # Expect pong or keep-alive from client
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                if data.get("type") == "pong":
                    continue
        except (WebSocketDisconnect, asyncio.TimeoutError, Exception) as e:
            logger.debug("WebSocket connection closed", client_id=client_id, error=str(e))
        finally:
            feed_manager.disconnect(client_id)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        """
        Check connectivity to:
        - Database
        - Ollama
        - Kubernetes API
        """
        from infrastructure.database import engine
        from infrastructure.kubernetes_client import get_core_v1_api
        from ai.backends.ollama import check_ollama_health
        import sqlalchemy as sa

        checks = {}
        
        # 1. Database
        try:
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {str(e)}"

        # 2. Ollama
        if await check_ollama_health():
            checks["ollama"] = "ok"
        else:
            checks["ollama"] = "error: unreachable"

        # 3. Kubernetes
        try:
            v1 = get_core_v1_api()
            await asyncio.to_thread(v1.get_api_resources)
            checks["kubernetes"] = "ok"
        except Exception as e:
            checks["kubernetes"] = f"error: {str(e)}"

        is_ready = all(v == "ok" for v in checks.values())
        status_code = 200 if is_ready else 503
        
        return Response(
            content=json.dumps({"status": "ready" if is_ready else "not_ready", "checks": checks}),
            media_type="application/json",
            status_code=status_code
        )

    return app

app = create_app()
