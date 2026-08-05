import os
import json as json_lib
import shutil
import asyncio
import socket
import ssl
import http.client
import subprocess
from pathlib import Path
from typing import Generator
from urllib.request import urlopen
from urllib.error import URLError

import docker
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

TAGS_METADATA = [
    {"name": "servicios", "description": "Arranque, parada y estado de los servicios opcionales (OpenSearch, LocalStack, ActiveMQ, Kafka, Postgres)."},
    {"name": "apps", "description": "Apps externas detectadas via los .conf de nginx fuera del core, incluyendo deteccion de su spec OpenAPI/Swagger si lo exponen."},
    {"name": "certificados", "description": "Certificados TLS y almacenes (keystores/truststores) generados por minica."},
    {"name": "nginx", "description": "Recarga de configuracion de nginx."},
    {"name": "minica", "description": "Gestion de la CA local y regeneracion de certificados."},
    {"name": "logs", "description": "Streaming de logs de contenedores."},
    {"name": "aws", "description": "Estado de LocalStack (emulacion de AWS)."},
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

docker_client = docker.from_env()

# Definición de servicios core de local-env
SERVICES = {
    "opensearch": {
        "label": "OpenSearch",
        "profile": "opensearch",
        "containers": ["opensearch", "opensearch-dashboards"],
        "urls": [
            {"label": "OpenSearch", "url": "https://opensearch.local-env.com"},
            {"label": "Dashboards", "url": "https://opensearch-dashboards.local-env.com"},
        ],
        "http_configs": ["opensearch"],
        "stream_configs": [],
    },
    "localstack": {
        "label": "LocalStack (AWS)",
        "profile": "localstack",
        "containers": ["localstack"],
        "urls": [],
        "endpoints": [
            {"label": "S3",         "url": "https://s3.local-aws.com"},
            {"label": "SQS",        "url": "https://sqs.local-aws.com"},
            {"label": "SES",        "url": "https://ses.local-aws.com"},
            {"label": "STS",        "url": "https://sts.local-aws.com"},
            {"label": "OpenSearch", "url": "https://opensearch.local-aws.com"},
        ],
        "http_configs": [],
        "stream_configs": [],
    },
    "activemq": {
        "label": "ActiveMQ",
        "profile": "activemq",
        "containers": ["activemq"],
        "urls": [{"label": "Consola ActiveMQ", "url": "https://activemq-dashboards.local-env.com"}],
        "http_configs": ["activemq"],
        "stream_configs": ["activemq"],
    },
    "kafka": {
        "label": "Kafka",
        "profile": "kafka",
        "containers": ["kafka", "kafka-dashboards"],
        "urls": [{"label": "Kafdrop", "url": "https://kafka-dashboards.local-env.com"}],
        "http_configs": ["kafka"],
        "stream_configs": ["kafka"],
    },
    "postgres": {
        "label": "PostgreSQL",
        "profile": "postgres",
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


def get_container_info(name: str) -> dict:
    try:
        c = docker_client.containers.get(name)
        tags = c.image.tags
        image = tags[0] if tags else c.attrs.get("Config", {}).get("Image", "")
        return {"status": c.status, "image": image}
    except docker.errors.NotFound:
        return {"status": "not_found", "image": None}


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


@app.get("/api/services", tags=["servicios"], summary="Listar servicios opcionales y su estado")
def get_services():
    """Devuelve cada servicio opcional (OpenSearch, LocalStack, ActiveMQ, Kafka, Postgres) con el estado de sus contenedores y sus URLs."""
    expected_images = get_compose_images()
    result = []
    for key, cfg in SERVICES.items():
        containers_info = []
        statuses = []
        for name in cfg["containers"]:
            info = get_container_info(name)
            expected = expected_images.get(name)
            up_to_date = None
            if info["image"] and expected:
                up_to_date = normalize_image(info["image"]) == normalize_image(expected)
            containers_info.append({
                "name": name,
                "status": info["status"],
                "image": info["image"],
                "expected_image": expected,
                "up_to_date": up_to_date,
            })
            statuses.append(info["status"])
        running = sum(1 for s in statuses if s == "running")
        total = len(statuses)
        if running == total:
            overall = "running"
        elif running == 0:
            overall = "stopped"
        else:
            overall = "partial"
        result.append({
            "id": key,
            "label": cfg["label"],
            "status": overall,
            "containers": containers_info,
            "urls": cfg["urls"],
            "endpoints": cfg.get("endpoints"),
        })
    return result


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
        # Buscar local-env.json junto al conf para metadatos de la app
        meta_file = conf_file.parent / f"{conf_file.stem}.json"
        app_name = "Sin identificar"
        if meta_file.exists():
            import json
            try:
                meta = json.loads(meta_file.read_text())
                app_name = meta.get("app", app_name)
            except Exception:
                pass

        # Intentar encontrar el contenedor upstream leyendo el conf
        container_status = "unknown"
        try:
            content = conf_file.read_text()
            # Buscar patron set $upstream http://CONTAINER:PORT
            import re
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


@app.post("/api/minica/restart", tags=["minica"], summary="Reiniciar minica y regenerar certificados")
def restart_minica():
    """Reinicia el contenedor de minica (regenera los certificados que falten) y recarga nginx."""
    try:
        subprocess.run(
            ["docker", "compose", "restart", "minica"],
            cwd=str(WORKSPACE),
            capture_output=True,
            timeout=60,
        )
        nginx_reload()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


@app.get("/api/logs/{container_name}", tags=["logs"], summary="Stream de logs de un contenedor (SSE)")
async def stream_logs(container_name: str):
    """Server-Sent Events con las ultimas 100 lineas de log del contenedor y las siguientes en tiempo real."""
    async def event_generator() -> Generator:
        try:
            c = docker_client.containers.get(container_name)
            for line in c.logs(stream=True, follow=True, tail=100):
                decoded = line.decode("utf-8", errors="replace").rstrip()
                yield {"data": decoded}
                await asyncio.sleep(0)
        except docker.errors.NotFound:
            yield {"data": f"[error] contenedor '{container_name}' no encontrado"}
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


# Servir frontend compilado
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(str(static_dir / "index.html"))
