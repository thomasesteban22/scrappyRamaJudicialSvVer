"""API de control del scraper - FastAPI."""
import asyncio
import os
import subprocess
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from log_broker import broker
import magna

API_TOKEN = os.getenv('API_TOKEN', '')
DOCKER_CONTAINER = os.getenv('DOCKER_CONTAINER', 'scraper-rama')

# Estado global del runner
_runner_state = {
    "running": False,
    "current_execution_id": None,
    "started_at": None,
    "started_by": None,
}


# ─── Auth helper ───────────────────────────────────────────────────────
def check_token(token: str | None):
    if not API_TOKEN:
        return  # sin token configurado = libre (solo para debug)
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="No autorizado")


# ─── Pydantic models ──────────────────────────────────────────────────
class RunRequest(BaseModel):
    started_by: str = "sistema"


# ─── Lifespan: arrancar el log tailer en background ───────────────────
async def tail_docker_logs():
    """Sigue los logs del contenedor del scraper y los publica al broker."""
    await broker.publish(f"[api] Iniciando tail de docker logs -f {DOCKER_CONTAINER}")
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "-f", "--tail", "100", DOCKER_CONTAINER,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                if line:
                    await broker.publish(line)
            await proc.wait()
        except Exception as e:
            await broker.publish(f"[api] Error en tail: {e}")
        await broker.publish("[api] Reintentando tail en 3s...")
        await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(tail_docker_logs())
    yield
    task.cancel()


app = FastAPI(title="Scraper Control API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoints ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


@app.get("/api/status")
def get_status(x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)

    # Verificar estado del contenedor
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", DOCKER_CONTAINER],
            capture_output=True, text=True, timeout=5
        )
        container_status = result.stdout.strip()
    except Exception:
        container_status = "unknown"

    return {
        "container": container_status,
        "runner": _runner_state,
    }


@app.get("/api/config")
def get_config(x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    try:
        return magna.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/procesos")
def get_procesos(x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)
    try:
        procesos = magna.get_procesos()
        return {"total": len(procesos), "procesos": procesos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run")
async def run_manual(req: RunRequest, x_api_token: str | None = Header(default=None)):
    check_token(x_api_token)

    if _runner_state["running"]:
        raise HTTPException(status_code=409, detail="Ya hay una ejecución en curso")

    # Crear ejecución en MySQL via Magna
    try:
        ejec_id = magna.crear_ejecucion(tipo="manual", iniciado_por=req.started_by)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo registrar ejecución: {e}")

    _runner_state.update({
        "running": True,
        "current_execution_id": ejec_id,
        "started_at": datetime.utcnow().isoformat(),
        "started_by": req.started_by,
    })

    await broker.publish(f"[api] Ejecución manual #{ejec_id} iniciada por {req.started_by}")

    # Disparar el scraper en un proceso separado (lo conectamos en el Paso 4)
    asyncio.create_task(_run_scraper_once(ejec_id, req.started_by))

    return {"execution_id": ejec_id, "status": "started"}


async def _run_scraper_once(ejec_id: int, started_by: str):
    """Dispara una ejecución manual escribiendo el trigger file en el volumen del scraper."""
    try:
        # El scraper monta /app2/data como /app/data
        trigger_path = "/host_data/.run_now"
        try:
            with open(trigger_path, "w") as f:
                f.write(started_by)
            await broker.publish(f"[runner] Trigger manual creado para ejecución #{ejec_id} por {started_by}")
            await broker.publish(f"[runner] El scraper detectará el trigger en los próximos 10 segundos")
        except Exception as e:
            await broker.publish(f"[runner] ERROR creando trigger: {e}")
            magna.actualizar_ejecucion(ejec_id, estado="fallida")
            return

        # NOTA: El scraper actualiza la ejecución cuando termina su ciclo.
        # No hacemos polling aquí; confiamos en el reporte del scraper.
    finally:
        # Liberamos el lock pronto: la ejecución es asíncrona desde el lado del scraper
        await asyncio.sleep(15)  # margen para que el scraper detecte y arranque
        _runner_state.update({
            "running": False,
            "current_execution_id": None,
            "started_at": None,
            "started_by": None,
        })


@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    """WebSocket para logs en vivo (estilo docker logs -f)."""
    # Auth via query string: ?token=...
    token = ws.query_params.get("token")
    if API_TOKEN and token != API_TOKEN:
        await ws.close(code=1008, reason="No autorizado")
        return

    await ws.accept()
    q = await broker.subscribe()
    try:
        while True:
            line = await q.get()
            await ws.send_text(line)
    except WebSocketDisconnect:
        pass
    finally:
        await broker.unsubscribe(q)
