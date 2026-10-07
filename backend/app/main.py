from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import audit, auth, backup, rules, status, suricata, users, wireguard
from app.db.database import init_db

app = FastAPI(title="nftguard")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rules.router)
app.include_router(status.router)
app.include_router(suricata.router)
app.include_router(wireguard.router)
app.include_router(audit.router)
app.include_router(backup.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
