import os
import json as json_lib
import re
import shutil
import asyncio
import base64
import socket
import ssl
import http.client
import subprocess
import threading
import time
from pathlib import Path
from typing import Generator
from urllib.request import urlopen, Request
from urllib.error import URLError

import docker
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

TAGS_METADATA = [
    {"name": "salud", "description": "Vista agregada de salud de local-env (core + servicios opcionales) en una sola llamada, pensada para apps externas que quieran verificar sus dependencias antes de arrancar."},
    {"name": "core", "description": "Reinicio de los servicios core de local-env (nginx, bind, minica, dashboard). No se pueden parar via API: son necesarios para que el entorno funcione."},
    {"name": "servicios", "description": "Arranque, parada y estado de los servicios opcionales (OpenSearch, LocalStack, ActiveMQ, Kafka, Postgres)."},
    {"name": "apps", "description": "Apps externas detectadas via los .conf de nginx fuera del core, incluyendo deteccion de su spec OpenAPI/Swagger si lo exponen."},
    {"name": "certificados", "description": "Certificados TLS y almacenes (keystores/truststores) generados por minica."},
    {"name": "nginx", "description": "Recarga de configuracion de nginx."},
    {"name": "minica", "description": "Gestion de la CA local y regeneracion de certificados."},
    {"name": "logs", "description": "Streaming de logs de contenedores."},
    {"name": "aws", "description": "Estado de LocalStack (emulacion de AWS) y sus recursos (buckets, colas)."},
    {"name": "db", "description": "Detalle de las bases de datos disponibles (tablas de Postgres, indices de OpenSearch)."},
    {"name": "mensajeria", "description": "Detalle de los sistemas de mensajeria (topics de Kafka, colas de ActiveMQ)."},
]

app = FastAPI(
    title="local-env dashboard",
    description="API del dashboard de local-env: estado de servicios, apps externas, certificados TLS y control basico del entorno.",
    version="1.2.0",
    openapi_tags=TAGS_METADATA,
)

# Rutas montadas en el contenedor
NGINX_CONF_HTTP     = Path("/etc/nginx/conf.d/http")
NGINX_CONF_HTTP_SVC = Path("/etc/nginx/conf.d/http/services")
NGINX_CONF_HTTP_AVL = Path("/etc/nginx/conf.d/http.available")
NGINX_CONF_STR_SVC  = Path("/etc/nginx/conf.d/stream/services")
NGINX_CONF_STR_AVL  = Path("/etc/nginx/conf.d/stream.available")
CERTS_DIR           = Path("/certs/live")
STORES_DIR          = Path("/certs/stores")
STORE_EXTENSIONS    = {".ks", ".ts", ".p12"}
CA_CERT_PATH        = Path("/certs/ca_cert.pem")
WORKSPACE           = Path("/workspace")

# IP fija de nginx en local-env-net (ver compose.yaml). Se usa para hablar con
# las apps a traves de nginx sin depender de que *.local-env.com resuelva
# correctamente desde dentro de un contenedor (la vista DNS "internal" de BIND
# solo se activa de forma fiable para clientes que consultan a bind directamente).
NGINX_IP = "10.0.1.2"

OPENAPI_CANDIDATE_PATHS = [
    "/openapi.json",
    "/v3/api-docs",
    "/swagger.json",
    "/swagger/v1/swagger.json",
    "/api-docs",
]

CORE_DOMAINS = {"local-env.com", "local-aws.com", "dashboard.local-env.com"}

# Servicios core: siempre presentes, no dependen de config.mk
CORE_SERVICES = {
    "nginx":     {"label": "nginx (proxy)",  "containers": ["nginx"],  "category": "core"},
    "bind":      {"label": "BIND9 (DNS)",    "containers": ["bind"],   "category": "core"},
    # minica genera los certs al arrancar y termina (exited/0): es su estado sano, no un fallo
    "minica":    {"label": "minica (CA)",    "containers": ["minica"], "category": "core", "one_shot": True},
    "dashboard": {"label": "Dashboard",      "containers": ["dashboard"], "category": "core"},
}

# Categorias para agrupar servicios en la UI (sidebar y ServicesView)
SERVICE_CATEGORIES = [
    {"id": "core",       "label": "Core"},
    {"id": "aws",        "label": "AWS"},
    {"id": "db",         "label": "Base de datos"},
    {"id": "mensajeria", "label": "Mensajeria"},
]

docker_client = docker.from_env()

# Definición de servicios core de local-env
SERVICES = {
    "opensearch": {
        "label": "OpenSearch",
        "profile": "opensearch",
        "category": "db",
        "containers": ["opensearch", "opensearch-dashboards"],
        "urls": [
            {"label": "OpenSearch", "url": "https://opensearch.local-env.com"},
            {"label": "Dashboards", "url": "https://opensearch-dashboards.local-env.com"},
        ],
        "http_configs": ["opensearch"],
        "stream_configs": [],
    },
    "localstack": {
        "label": "LocalStack (AWS) - contenedor",
        "profile": "localstack",
        "category": "aws",
        "containers": ["localstack"],
        "urls": [],
        "http_configs": [],
        "stream_configs": [],
    },
    "activemq": {
        "label": "ActiveMQ",
        "profile": "activemq",
        "category": "mensajeria",
        "containers": ["activemq"],
        "urls": [{"label": "Consola ActiveMQ", "url": "https://activemq-dashboards.local-env.com"}],
        "http_configs": ["activemq"],
        "stream_configs": ["activemq"],
    },
    "kafka": {
        "label": "Kafka",
        "profile": "kafka",
        "category": "mensajeria",
        "containers": ["kafka", "kafka-dashboards"],
        "urls": [{"label": "Kafdrop", "url": "https://kafka-dashboards.local-env.com"}],
        "http_configs": ["kafka"],
        "stream_configs": ["kafka"],
    },
    "postgres": {
        "label": "PostgreSQL",
        "profile": "postgres",
        "category": "db",
        "containers": ["postgres", "sql-admin"],
        "urls": [{"label": "sql-admin", "url": "https://sql-admin.local-env.com"}],
        "http_configs": ["postgres"],
        "stream_configs": [],
    },
}


class _SNIHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection que conecta por IP pero usa `sni_host` para el SNI/TLS,
    evitando depender de la resolucion DNS de *.local-env.com dentro del contenedor."""

    def __init__(self, ip: str, sni_host: str, context: ssl.SSLContext, timeout: float):
        super().__init__(ip, 443, timeout=timeout, context=context)
        self._sni_host = sni_host

    def connect(self):
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self._sni_host)


def _fetch_json_via_nginx(domain: str, path: str, timeout: float = 2.0) -> dict | None:
    """GET a `https://<domain><path>` pasando por nginx (10.0.1.2), devuelve el JSON o None."""
    ctx = ssl.create_default_context(cafile=str(CA_CERT_PATH)) if CA_CERT_PATH.exists() else ssl._create_unverified_context()
    conn = _SNIHTTPSConnection(NGINX_IP, domain, ctx, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Host": domain})
        resp = conn.getresponse()
        if resp.status != 200:
            return None
        return json_lib.loads(resp.read())
    except Exception:
        return None
    finally:
        conn.close()


def get_container_env(name: str) -> dict:
    """Lee las variables de entorno reales de un contenedor en marcha (via Docker API),
    para no depender de leer ficheros .env del host."""
    try:
        c = docker_client.containers.get(name)
        env_list = c.attrs.get("Config", {}).get("Env", [])
        return dict(e.split("=", 1) for e in env_list if "=" in e)
    except Exception:
        return {}


def docker_exec(name: str, cmd: list[str], environment: dict | None = None, timeout: float = 10.0) -> str | None:
    """Ejecuta `cmd` dentro del contenedor `name` (docker exec) y devuelve su stdout, o None
    si el contenedor no esta corriendo o el comando falla."""
    try:
        c = docker_client.containers.get(name)
        if c.status != "running":
            return None
        exit_code, output = c.exec_run(cmd, environment=environment, demux=False)
        if exit_code != 0:
            return None
        return output.decode("utf-8", errors="replace")
    except Exception:
        return None


def get_container_info(name: str) -> dict:
    try:
        c = docker_client.containers.get(name)
        tags = c.image.tags
        image = tags[0] if tags else c.attrs.get("Config", {}).get("Image", "")
        exit_code = c.attrs.get("State", {}).get("ExitCode")
        return {"status": c.status, "image": image, "exit_code": exit_code}
    except docker.errors.NotFound:
        return {"status": "not_found", "image": None, "exit_code": None}


def get_compose_images() -> dict:
    compose_file = WORKSPACE / "compose.yaml"
    result = {}
    if compose_file.exists():
        data = yaml.safe_load(compose_file.read_text())
        for svc_cfg in (data.get("services") or {}).values():
            container = svc_cfg.get("container_name")
            image = svc_cfg.get("image", "")
            if container and image and not image.startswith("local-env/"):
                result[container] = image
    return result


def normalize_image(image: str) -> str:
    return image if ":" in image else image + ":latest"


def nginx_reload():
    try:
        nginx = docker_client.containers.get("nginx")
        nginx.exec_run("nginx -s reload")
    except Exception:
        pass


def sync_nginx_for_service(service_key: str):
    cfg = SERVICES[service_key]
    NGINX_CONF_HTTP_SVC.mkdir(parents=True, exist_ok=True)
    NGINX_CONF_STR_SVC.mkdir(parents=True, exist_ok=True)
    for conf in cfg["http_configs"]:
        src = NGINX_CONF_HTTP_AVL / f"{conf}.conf"
        dst = NGINX_CONF_HTTP_SVC / f"{conf}.conf"
        if src.exists():
            shutil.copy(src, dst)
    for conf in cfg["stream_configs"]:
        src = NGINX_CONF_STR_AVL / f"{conf}.conf"
        dst = NGINX_CONF_STR_SVC / f"{conf}.conf"
        if src.exists():
            shutil.copy(src, dst)


def remove_nginx_for_service(service_key: str):
    cfg = SERVICES[service_key]
    for conf in cfg["http_configs"]:
        dst = NGINX_CONF_HTTP_SVC / f"{conf}.conf"
        dst.unlink(missing_ok=True)
    for conf in cfg["stream_configs"]:
        dst = NGINX_CONF_STR_SVC / f"{conf}.conf"
        dst.unlink(missing_ok=True)


def _aggregate_status(containers: list[str], expected_images: dict, one_shot: bool = False) -> tuple[str, list[dict]]:
    """Calcula el estado agregado (running/idle/partial/stopped/error) de un grupo de contenedores.

    `one_shot` es para contenedores que hacen su trabajo y terminan (p.ej. minica genera certs
    y sale con codigo 0): un `exited(0)` en ese caso es el estado sano ("idle"), no un fallo."""
    containers_info = []
    statuses = []
    for name in containers:
        info = get_container_info(name)
        expected = expected_images.get(name)
        up_to_date = None
        if info["image"] and expected:
            up_to_date = normalize_image(info["image"]) == normalize_image(expected)
        status = info["status"]
        if one_shot and status == "exited":
            status = "idle" if info["exit_code"] == 0 else "error"
        containers_info.append({
            "name": name,
            "status": status,
            "image": info["image"],
            "expected_image": expected,
            "up_to_date": up_to_date,
        })
        statuses.append(status)

    healthy = {"running", "idle"}
    if statuses and all(s in healthy for s in statuses):
        overall = "idle" if all(s == "idle" for s in statuses) else "running"
    elif any(s in healthy for s in statuses):
        overall = "partial"
    else:
        overall = "error" if any(s == "error" for s in statuses) else "stopped"
    return overall, containers_info


@app.get("/api/services", tags=["servicios"], summary="Listar servicios opcionales y su estado")
def get_services():
    """Devuelve cada servicio opcional (OpenSearch, LocalStack, ActiveMQ, Kafka, Postgres) con el estado de sus contenedores y sus URLs."""
    expected_images = get_compose_images()
    result = []
    for key, cfg in SERVICES.items():
        overall, containers_info = _aggregate_status(cfg["containers"], expected_images)
        result.append({
            "id": key,
            "label": cfg["label"],
            "category": cfg["category"],
            "status": overall,
            "containers": containers_info,
            "urls": cfg["urls"],
        })
    return result


@app.get("/api/service-categories", tags=["servicios"], summary="Categorias para agrupar servicios")
def get_service_categories():
    """Orden y etiquetas de las categorias usadas para agrupar servicios en la UI (sidebar y vista Servicios)."""
    return SERVICE_CATEGORIES


@app.get("/api/health", tags=["salud"], summary="Salud agregada de local-env (core + servicios opcionales)")
def get_health():
    """Vista de una sola llamada para que apps externas comprueben, antes de arrancar, que local-env
    esta disponible y que servicios opcionales (Kafka, OpenSearch, LocalStack...) tienen arrancados.

    `status` es "healthy" si todo el core esta sano (running, o idle para minica tras generar los
    certs), "degraded" si algo del core esta parcial, parado o en error, y no tiene en cuenta el
    estado de los servicios opcionales (son opcionales por definicion)."""
    expected_images = get_compose_images()

    core = []
    core_running = True
    for key, cfg in CORE_SERVICES.items():
        overall, containers_info = _aggregate_status(cfg["containers"], expected_images, one_shot=cfg.get("one_shot", False))
        if overall not in ("running", "idle"):
            core_running = False
        core.append({
            "id": key,
            "label": cfg["label"],
            "category": cfg["category"],
            "status": overall,
            "containers": containers_info,
        })

    return {
        "status": "healthy" if core_running else "degraded",
        "core": core,
        "services": get_services(),
    }


@app.post("/api/services/{service_id}/start", tags=["servicios"], summary="Arrancar un servicio opcional")
def start_service(service_id: str):
    """Sincroniza la config de nginx del servicio, levanta sus contenedores con docker compose y recarga nginx."""
    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    cfg = SERVICES[service_id]
    sync_nginx_for_service(service_id)
    try:
        subprocess.run(
            ["docker", "compose", "--profile", cfg["profile"], "up", "-d"] + cfg["containers"],
            cwd=str(WORKSPACE),
            capture_output=True,
            timeout=120,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    nginx_reload()
    return {"ok": True}


@app.post("/api/services/{service_id}/stop", tags=["servicios"], summary="Parar un servicio opcional")
def stop_service(service_id: str):
    """Detiene los contenedores del servicio y retira su config de nginx."""
    if service_id not in SERVICES:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    cfg = SERVICES[service_id]
    for container_name in cfg["containers"]:
        try:
            c = docker_client.containers.get(container_name)
            c.stop(timeout=10)
        except docker.errors.NotFound:
            pass
    remove_nginx_for_service(service_id)
    nginx_reload()
    return {"ok": True}


@app.get("/api/apps", tags=["apps"], summary="Listar apps externas")
def get_apps():
    """Detecta apps externas escaneando los .conf de nginx que no son del core de local-env."""
    apps_by_meta: dict[str, list] = {}

    for conf_file in NGINX_CONF_HTTP.glob("*.conf"):
        domain = conf_file.stem
        if domain in CORE_DOMAINS:
            continue
        # El nombre de la app es el dominio sin el sufijo de zona
        app_name = domain
        for suffix in (".local-env.com", ".local-aws.com"):
            if domain.endswith(suffix):
                app_name = domain[: -len(suffix)]
                break

        # Intentar encontrar el contenedor upstream leyendo el conf
        container_status = "unknown"
        try:
            content = conf_file.read_text()
            # Buscar patron set $upstream http://CONTAINER:PORT
            m = re.search(r'set \$upstream https?://([^:]+):', content)
            if m:
                container_name = m.group(1)
                container_status = get_container_info(container_name)["status"]
        except Exception:
            pass

        if app_name not in apps_by_meta:
            apps_by_meta[app_name] = []
        apps_by_meta[app_name].append({
            "domain": domain,
            "url": f"https://{domain}",
            "status": container_status,
        })

    return [{"name": name, "services": services} for name, services in apps_by_meta.items()]


@app.get("/api/apps/{domain}/openapi", tags=["apps"], summary="Detectar y proxear el spec OpenAPI de una app")
def get_app_openapi(domain: str):
    """Prueba rutas habituales de OpenAPI/Swagger (`/openapi.json`, `/v3/api-docs`, `/swagger.json`...)
    contra el dominio, a traves de nginx, y devuelve el primer spec valido encontrado."""
    if domain in CORE_DOMAINS or not (NGINX_CONF_HTTP / f"{domain}.conf").exists():
        raise HTTPException(status_code=404, detail="App no encontrada")
    for path in OPENAPI_CANDIDATE_PATHS:
        data = _fetch_json_via_nginx(domain, path)
        if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
            return data
    raise HTTPException(status_code=404, detail="No se encontro un spec OpenAPI/Swagger en las rutas habituales")


@app.get("/api/certs", tags=["certificados"], summary="Listar certificados TLS por dominio")
def get_certs():
    """Certificados wildcard generados por minica en `live/`, con fecha de expiracion y el keystore asociado si existe."""
    certs = []
    if CERTS_DIR.exists():
        for domain_dir in sorted(CERTS_DIR.iterdir()):
            if domain_dir.is_dir():
                cert_file = domain_dir / "cert.pem"
                expires = None
                if cert_file.exists():
                    try:
                        result = subprocess.run(
                            ["openssl", "x509", "-enddate", "-noout", "-in", str(cert_file)],
                            capture_output=True, text=True, timeout=5
                        )
                        # notAfter=Jun 27 12:00:00 2027 GMT
                        line = result.stdout.strip()
                        if "=" in line:
                            expires = line.split("=", 1)[1].strip()
                    except Exception:
                        pass
                keystore = f"{domain_dir.name}.ks"
                certs.append({
                    "domain": domain_dir.name,
                    "wildcard": True,
                    "expires": expires,
                    "cert_path": str(cert_file),
                    "keystore": keystore if (STORES_DIR / keystore).exists() else None,
                })
    return certs


def _safe_store_path(filename: str) -> Path:
    """Resuelve un nombre de fichero dentro de STORES_DIR evitando path traversal."""
    candidate = STORES_DIR / Path(filename).name
    try:
        candidate.resolve().relative_to(STORES_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Nombre de fichero inválido")
    if not candidate.is_file() or candidate.suffix not in STORE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")
    return candidate


@app.get("/api/certs/stores", tags=["certificados"], summary="Listar keystores y truststores disponibles")
def get_cert_stores():
    """Lista los keystores/truststores (.ks/.ts/.p12) generados por minica, listos para descargar."""
    stores = []
    if STORES_DIR.exists():
        for f in sorted(STORES_DIR.iterdir()):
            if f.is_file() and f.suffix in STORE_EXTENSIONS:
                stores.append({
                    "filename": f.name,
                    "type": f.suffix.lstrip("."),
                    "size": f.stat().st_size,
                })
    return stores


@app.get("/api/certs/stores/{filename}", tags=["certificados"], summary="Descargar un keystore o truststore")
def download_cert_store(filename: str):
    """Descarga un fichero concreto de `certs/stores/` (p.ej. `ca-cert.ts` o `local-env.com.ks`), contraseña `password`."""
    path = _safe_store_path(filename)
    return FileResponse(str(path), media_type="application/octet-stream", filename=path.name)


@app.post("/api/nginx/reload", tags=["nginx"], summary="Recargar la configuracion de nginx")
def reload_nginx():
    nginx_reload()
    return {"ok": True}


def _restart_containers(containers: list[str]):
    for name in containers:
        subprocess.run(
            ["docker", "compose", "restart", name],
            cwd=str(WORKSPACE),
            capture_output=True,
            timeout=60,
        )


def _delayed_restart(containers: list[str], delay: float = 0.5):
    """Espera un poco antes de reiniciar - usado cuando el propio contenedor que atiende
    la peticion es el que se va a reiniciar (dashboard), para poder devolver antes la respuesta."""
    time.sleep(delay)
    _restart_containers(containers)


@app.post("/api/minica/restart", tags=["minica"], summary="Reiniciar minica y regenerar certificados")
def restart_minica():
    """Reinicia el contenedor de minica (regenera los certificados que falten) y recarga nginx."""
    try:
        _restart_containers(["minica"])
        nginx_reload()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


@app.post("/api/core/{service_id}/restart", tags=["core"], summary="Reiniciar un servicio core")
def restart_core_service(service_id: str):
    """Reinicia el/los contenedor(es) de un servicio core (nginx, bind, minica, dashboard).
    No hay endpoint para pararlos: son necesarios para que local-env funcione."""
    if service_id not in CORE_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio core no encontrado")
    containers = CORE_SERVICES[service_id]["containers"]

    if service_id == "dashboard":
        threading.Thread(target=_delayed_restart, args=(containers,), daemon=True).start()
        return {"ok": True}

    try:
        _restart_containers(containers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if service_id != "nginx":
        nginx_reload()
    return {"ok": True}


@app.get("/api/logs/{container_name}", tags=["logs"], summary="Stream de logs de un contenedor (SSE)")
async def stream_logs(container_name: str):
    """Server-Sent Events con las ultimas 100 lineas de log del contenedor y las siguientes en tiempo real.

    `c.logs(stream=True, follow=True)` del SDK de Docker es un iterador sincrono y bloqueante: cada
    linea espera en un socket hasta que el contenedor escribe algo. Si se itera directamente dentro
    de una corrutina, ese bloqueo congela TODO el event loop de asyncio (todo uvicorn, no solo esta
    peticion) mientras el contenedor este callado. Por eso la lectura se hace en un hilo aparte que
    empuja las lineas a una cola, y la corrutina solo hace `await queue.get()`."""
    loop  = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def producer():
        try:
            c = docker_client.containers.get(container_name)
            for line in c.logs(stream=True, follow=True, tail=100):
                decoded = line.decode("utf-8", errors="replace").rstrip()
                loop.call_soon_threadsafe(queue.put_nowait, decoded)
        except docker.errors.NotFound:
            loop.call_soon_threadsafe(queue.put_nowait, f"[error] contenedor '{container_name}' no encontrado")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    async def event_generator() -> Generator:
        threading.Thread(target=producer, daemon=True).start()
        try:
            while True:
                line = await queue.get()
                if line is _SENTINEL:
                    break
                yield {"data": line}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


@app.get("/api/localstack/health", tags=["aws"], summary="Salud de LocalStack")
def get_localstack_health():
    """Proxy al endpoint de salud de LocalStack (`/_localstack/health`)."""
    try:
        with urlopen("http://localstack:4566/_localstack/health", timeout=5) as r:
            return json_lib.loads(r.read())
    except (URLError, OSError):
        raise HTTPException(status_code=503, detail="LocalStack no disponible")


# Servicios AWS emulados por LocalStack que se muestran como tarjeta propia (uno por cada uno,
# ademas de la tarjeta del contenedor). El id coincide con la clave que usa `_localstack/health`.
LOCALSTACK_SERVICES = [
    {"id": "s3",         "label": "S3",         "endpoint": "https://s3.local-aws.com"},
    {"id": "sqs",        "label": "SQS",        "endpoint": "https://sqs.local-aws.com"},
    {"id": "ses",        "label": "SES",        "endpoint": "https://ses.local-aws.com"},
    {"id": "sts",        "label": "STS",        "endpoint": "https://sts.local-aws.com"},
    {"id": "opensearch", "label": "OpenSearch", "endpoint": "https://opensearch.local-aws.com"},
]


def _localstack_s3_buckets() -> list[dict]:
    out = docker_exec("localstack", ["awslocal", "s3api", "list-buckets", "--output", "json"])
    if not out:
        return []
    try:
        return [{"name": b["Name"], "arn": b.get("BucketArn")} for b in json_lib.loads(out).get("Buckets", [])]
    except Exception:
        return []


def _localstack_sqs_queues() -> list[dict]:
    out = docker_exec("localstack", ["awslocal", "sqs", "list-queues", "--output", "json"])
    if not out:
        return []
    queues = []
    try:
        urls = json_lib.loads(out).get("QueueUrls", [])
    except Exception:
        return []
    for url in urls:
        name = url.rstrip("/").rsplit("/", 1)[-1]
        arn = None
        attrs_out = docker_exec(
            "localstack",
            ["awslocal", "sqs", "get-queue-attributes", "--queue-url", url, "--attribute-names", "QueueArn", "--output", "json"],
        )
        if attrs_out:
            try:
                arn = json_lib.loads(attrs_out).get("Attributes", {}).get("QueueArn")
            except Exception:
                pass
        queues.append({"name": name, "arn": arn})
    return queues


@app.get("/api/localstack/services", tags=["aws"], summary="Servicios AWS de LocalStack: endpoint, estado y recursos creados")
def get_localstack_services():
    """Una tarjeta por servicio AWS emulado (S3, SQS, SES, STS, OpenSearch), con su endpoint, si esta
    activo o solo disponible bajo demanda, y sus recursos ya creados (buckets, colas) con su ARN
    para los servicios donde eso aplica."""
    try:
        with urlopen("http://localstack:4566/_localstack/health", timeout=5) as r:
            states = json_lib.loads(r.read()).get("services", {})
    except (URLError, OSError):
        raise HTTPException(status_code=503, detail="LocalStack no disponible")

    resources_by_id = {
        "s3": _localstack_s3_buckets(),
        "sqs": _localstack_sqs_queues(),
    }

    services = [
        {
            "id": svc["id"],
            "label": svc["label"],
            "endpoint": svc["endpoint"],
            "state": states.get(svc["id"], "unavailable"),
            "resources": resources_by_id.get(svc["id"]),
        }
        for svc in LOCALSTACK_SERVICES
    ]
    return {"services": services}


@app.get("/api/postgres/tables", tags=["db"], summary="Tablas creadas en la base de datos Postgres")
def get_postgres_tables():
    """Lista las tablas del esquema `public` y su numero de filas, ejecutando `psql` dentro del
    propio contenedor de Postgres (credenciales leidas de su entorno real, no de un .env)."""
    env = get_container_env("postgres")
    user = env.get("POSTGRES_USER", "finuser")
    db   = env.get("POSTGRES_DB", "findb")
    pg_env = {"PGPASSWORD": env.get("POSTGRES_PASSWORD", "")}

    tables_out = docker_exec(
        "postgres",
        ["psql", "-U", user, "-d", db, "-t", "-A", "-c",
         "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"],
        environment=pg_env,
    )
    if tables_out is None:
        raise HTTPException(status_code=503, detail="Postgres no disponible")

    tables = []
    for name in (t.strip() for t in tables_out.splitlines()):
        if not name:
            continue
        count_out = docker_exec(
            "postgres",
            ["psql", "-U", user, "-d", db, "-t", "-A", "-c", f'SELECT count(*) FROM "{name}";'],
            environment=pg_env,
        )
        rows = int(count_out.strip()) if count_out and count_out.strip().isdigit() else None
        tables.append({"name": name, "rows": rows})

    return {"database": db, "tables": tables}


@app.get("/api/kafka/topics", tags=["mensajeria"], summary="Topics creados en Kafka")
def get_kafka_topics():
    """Lista los topics de Kafka (excluyendo los internos `__consumer_offsets` etc.) ejecutando
    `kafka-topics` dentro del propio contenedor."""
    out = docker_exec("kafka", ["kafka-topics", "--bootstrap-server", "localhost:9092", "--list"])
    if out is None:
        raise HTTPException(status_code=503, detail="Kafka no disponible")
    topics = [t.strip() for t in out.splitlines() if t.strip() and not t.startswith("__")]
    return {"topics": topics}


def _jolokia_get(path: str) -> dict | None:
    """GET a la API Jolokia de ActiveMQ (consola admin), con credenciales por defecto de la imagen
    y el header Origin que exige Jolokia para aceptar la peticion."""
    env = get_container_env("activemq")
    user = env.get("ACTIVEMQ_ADMIN_LOGIN", "admin")
    password = env.get("ACTIVEMQ_ADMIN_PASSWORD", "admin")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = Request(
        f"http://activemq:8161/api/jolokia/{path}",
        headers={"Authorization": f"Basic {auth}", "Origin": "http://activemq:8161"},
    )
    try:
        with urlopen(req, timeout=5) as r:
            return json_lib.loads(r.read())
    except (URLError, OSError):
        return None


def _jolokia_destination_names(objects: list) -> list[str]:
    names = []
    for obj in objects:
        object_name = obj.get("objectName", "") if isinstance(obj, dict) else str(obj)
        m = re.search(r"destinationName=([^,]+)", object_name)
        if m:
            names.append(m.group(1))
    return sorted(names)


@app.get("/api/activemq/queues", tags=["mensajeria"], summary="Colas y topics creados en ActiveMQ")
def get_activemq_queues():
    """Lista las colas y topics realmente creados en el broker de ActiveMQ, via la API Jolokia
    de su consola de administracion."""
    data = _jolokia_get("read/org.apache.activemq:type=Broker,brokerName=localhost")
    if data is None or "value" not in data:
        raise HTTPException(status_code=503, detail="ActiveMQ no disponible")
    value = data["value"]
    return {
        "queues": _jolokia_destination_names(value.get("Queues", [])),
        "topics": _jolokia_destination_names(value.get("Topics", [])),
    }


@app.get("/api/opensearch/indices", tags=["db"], summary="Indices creados en OpenSearch")
def get_opensearch_indices():
    """Lista los indices de OpenSearch (excluyendo los ocultos que empiezan por `.`), con
    autenticacion admin leida del entorno real del contenedor."""
    env = get_container_env("opensearch")
    password = env.get("OPENSEARCH_INITIAL_ADMIN_PASSWORD")
    if not password:
        raise HTTPException(status_code=503, detail="OpenSearch no disponible")
    auth = base64.b64encode(f"admin:{password}".encode()).decode()
    req = Request(
        "https://opensearch:9200/_cat/indices?format=json",
        headers={"Authorization": f"Basic {auth}"},
    )
    ctx = ssl._create_unverified_context()
    try:
        with urlopen(req, timeout=5, context=ctx) as r:
            data = json_lib.loads(r.read())
    except (URLError, OSError):
        raise HTTPException(status_code=503, detail="OpenSearch no disponible")

    internal_prefixes = (".", "security-auditlog", "top_queries")
    indices = [
        {"name": idx["index"], "docs": idx.get("docs.count"), "size": idx.get("store.size"), "health": idx.get("health")}
        for idx in data
        if not idx.get("index", "").startswith(internal_prefixes)
    ]
    indices.sort(key=lambda i: i["name"])
    return {"indices": indices}


# Servir frontend compilado
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(str(static_dir / "index.html"))
