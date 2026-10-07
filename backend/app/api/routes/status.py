import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_user
from app.services.monitor import get_status

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("", dependencies=[Depends(get_current_user)])
def status_snapshot() -> dict:
    return get_status()


@router.websocket("/ws")
async def status_ws(websocket: WebSocket) -> None:
    """Push periódico de métricas. La autenticación del WS se hace con el token
    como query param (?token=...) porque los navegadores no permiten headers en WS."""
    from app.core.security import decode_access_token

    token = websocket.query_params.get("token")
    if not token or decode_access_token(token) is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_status())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
