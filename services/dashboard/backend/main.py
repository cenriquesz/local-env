import os
import json as json_lib
import shutil
import asyncio
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

app = FastAPI(title="local-env dashboard")

# Rutas montadas en el contenedor
NGINX_CONF_HTTP     = Path("/etc/nginx/conf.d/http")
NGINX_CONF_HTTP_SVC = Path("/etc/nginx/conf.d/http/services")
NGINX_CONF_HTTP_AVL = Path("/etc/nginx/conf.d/http.available")
NGINX_CONF_STR_SVC  = Path("/etc/nginx/conf.d/stream/services")
NGINX_CONF_STR_AVL  = Path("/etc/nginx/conf.d/stream.available")
CERTS_DIR           = Path("/certs/live")
WORKSPACE           = Path("/workspace")

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


@app.get("/api/services")
def get_services():
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


@app.post("/api/services/{service_id}/start")
def start_service(service_id: str):
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


@app.post("/api/services/{service_id}/stop")
def stop_service(service_id: str):
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


@app.get("/api/apps")
def get_apps():
    """Detecta apps externas escaneando configs nginx no core."""
    core_configs = {"local-env.com", "local-aws.com", "dashboard.local-env.com"}
    apps_by_meta: dict[str, list] = {}

    for conf_file in NGINX_CONF_HTTP.glob("*.conf"):
        domain = conf_file.stem
        if domain in core_configs:
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


@app.get("/api/certs")
def get_certs():
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
                certs.append({
                    "domain": domain_dir.name,
                    "wildcard": True,
                    "expires": expires,
                    "cert_path": str(cert_file),
                })
    return certs


@app.post("/api/nginx/reload")
def reload_nginx():
    nginx_reload()
    return {"ok": True}


@app.post("/api/minica/restart")
def restart_minica():
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


@app.get("/api/logs/{container_name}")
async def stream_logs(container_name: str):
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


@app.get("/api/localstack/health")
def get_localstack_health():
    try:
        with urlopen("http://localstack:4566/_localstack/health", timeout=5) as r:
            return json_lib.loads(r.read())
    except (URLError, OSError):
        raise HTTPException(status_code=503, detail="LocalStack no disponible")


# Servir frontend compilado
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(static_dir / "index.html"))
