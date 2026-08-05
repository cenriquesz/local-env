# local-env

Entorno de desarrollo local basado en Docker que replica servicios de producción con HTTPS real, DNS propio y emulación de AWS. Una app puede conectarse a `https://opensearch.local-env.com` o `kafka.local-env.com:9092` igual que en producción, sin tocar `/etc/hosts` ni lidiar con certificados autofirmados ad hoc.

## Servicios disponibles

| Servicio | URL / Endpoint | Opcional |
|---|---|---|
| Dashboard local-env | `https://dashboard.local-env.com` | No (siempre activo) |
| OpenSearch | `https://opensearch.local-env.com` | Si |
| OpenSearch Dashboards | `https://opensearch-dashboards.local-env.com` | Si |
| LocalStack (AWS) | `https://*.local-aws.com` | Si |
| ActiveMQ (consola) | `https://activemq-dashboards.local-env.com` | Si |
| ActiveMQ (broker) | `activemq.local-env.com:61617` (TCP/TLS) | Si |
| Kafka (broker) | `kafka.local-env.com:9092` (TCP/TLS) | Si |
| Kafdrop (UI Kafka) | `https://kafka-dashboards.local-env.com` | Si |
| PostgreSQL | interno, sin acceso directo por dominio | Si |
| sql-admin (Adminer) | `https://sql-admin.local-env.com` | Si |

Los servicios `bind` (DNS), `minica` (CA/TLS), `nginx` (proxy) y `dashboard` arrancan siempre y son el nucleo del entorno. El resto son opcionales y se configuran en `config.mk`.

## Inicio rapido

### 1. Prerrequisitos

- Docker Desktop >= 24 o Docker Engine + Compose plugin
- Puertos libres en el host: `53` (UDP/TCP), `80`, `443`, `9092`, `61617`
- 8 GB de RAM disponibles para Docker
- [LocalStack Auth Token](https://localstack.cloud) si se usa LocalStack con OpenSearch (plan gratuito)

### 2. Configuracion

```bash
git clone git@github.com:cenriquesz/local-env.git
cd local-env
cp .env.example .env
# Editar .env y poner el LOCALSTACK_AUTH_TOKEN real
```

### 3. Arrancar

```bash
# Arrancar con todos los servicios (configuración por defecto)
make up

# Personalizar servicios antes de arrancar: editar config.mk
# Por ejemplo, deshabilitar kafka y activemq:
# ENABLE_KAFKA     ?= false
# ENABLE_ACTIVEMQ  ?= false
make up
```

### 4. Configurar DNS del sistema operativo

Sin esto los dominios `*.local-env.com` y `*.local-aws.com` no resuelven desde el host.

**Linux (systemd-resolved)** - crear `/etc/systemd/resolved.conf.d/local-env.conf`:
```ini
[Resolve]
DNS=127.0.0.1
Domains=~local-env.com ~local-aws.com
```
```bash
sudo systemctl restart systemd-resolved
```

**macOS** - crear dos ficheros:
```bash
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/local-env.com
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/local-aws.com
```

**Windows** - anadir `127.0.0.1` como DNS adicional en el adaptador de red activo.

**Alternativa rapida** - anadir entradas en `/etc/hosts`:
```
127.0.0.1 dashboard.local-env.com
127.0.0.1 opensearch.local-env.com opensearch-dashboards.local-env.com
127.0.0.1 activemq.local-env.com activemq-dashboards.local-env.com
127.0.0.1 kafka.local-env.com kafka-dashboards.local-env.com
127.0.0.1 local-aws.com
```

### 5. Instalar la CA de minica

La CA se genera al primer arranque en `services/minica/app/certs/ca_cert.pem`. Instalarla para que los certificados sean de confianza:

**Linux (Ubuntu/Debian):**
```bash
sudo cp services/minica/app/certs/ca_cert.pem /usr/local/share/ca-certificates/local-env-ca.crt
sudo update-ca-certificates
```

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain \
  services/minica/app/certs/ca_cert.pem
```

**Windows (PowerShell como administrador):**
```powershell
certutil -addstore -f "ROOT" services\minica\app\certs\ca_cert.pem
```

**JVM:**
```bash
sudo keytool -import -trustcacerts \
  -file services/minica/app/certs/ca_cert.pem \
  -alias local-env-ca-cert -cacerts
```

### 6. Verificar

```bash
# DNS resuelve
nslookup opensearch.local-env.com 127.0.0.1

# HTTPS funciona
curl -s https://opensearch.local-env.com/_cluster/health | jq .status

# LocalStack disponible
curl -s https://s3.local-aws.com
```

## Documentacion

| Doc | Contenido |
|---|---|
| [docs/analysis.md](docs/analysis.md) | Análisis del proyecto: componentes, estado actual, gaps identificados |
| [docs/architecture.md](docs/architecture.md) | Arquitectura: red Docker, DNS, TLS, proxy nginx, emulación AWS |
| [docs/flows.md](docs/flows.md) | Flujos: arranque, generación de certificados, resolución DNS, petición HTTPS |
| [docs/deployment.md](docs/deployment.md) | Despliegue: instalación paso a paso, selección de servicios, keystores Java |
| [docs/operations.md](docs/operations.md) | Operaciones: gestión de certs, zonas DNS, logs, problemas conocidos |
| [docs/integration.md](docs/integration.md) | Integración: patrón repos hermanos, Makefile de la app, local-env.json para el dashboard, clientes Spring Boot / Python |

## Integrar tu app

`local-env` tiene puntos de extension pensados para que una app aporte su propia configuracion sin modificar el repo:

- `services/nginx/etc/nginx/conf.d/http/` - pon aqui el .conf nginx de tu app (ej: `mi-app.local-env.com.conf`). minica genera el certificado automaticamente al detectarlo.
- `services/localstack/init/ready.d/` - pon aqui un script bash con `awslocal` para crear tus recursos AWS al arrancar LocalStack.

Estos directorios tienen `.gitignore` que excluye el contenido de apps, asi el repo local-env queda limpio.

Ver [docs/integration.md](docs/integration.md) para la guia completa con ejemplos de Makefile, configuracion Spring Boot, boto3 y mas.

## Dashboard

`https://dashboard.local-env.com` es la interfaz web de gestion del entorno. Arranca siempre junto con el nucleo (bind, minica, nginx) y no requiere configuracion adicional.

**Funcionalidades:**

- **Servicios** - cards con estado en tiempo real de cada contenedor (OpenSearch, Kafka, ActiveMQ, LocalStack). Permite arrancar y parar servicios individualmente sin tocar la terminal.
- **Apps externas** - detecta automaticamente las apps integradas que han dropado su `.conf` nginx en el punto de extension. Muestra nombre, URL y estado del contenedor de la app.
- **Certificados** - lista los certificados TLS generados por minica con su dominio y fecha de expiracion.
- **Logs** - drawer de logs en tiempo real (SSE) por contenedor.

El dashboard monta el socket de Docker (solo lectura de estado) y los directorios de configuracion de nginx para detectar servicios y apps activas.

### Frontend del dashboard

El frontend (Vue 3) se compila a `services/dashboard/frontend/dist/`, que esta en `.gitignore` por ser un artefacto compilado. El contenedor monta ese directorio como volumen (`./services/dashboard/frontend/dist:/app/static`) para poder ver cambios sin rebuild, asi que hace falta compilarlo al menos una vez tras clonar el repo.

`make up` lo hace automaticamente (target `dashboard-build`, se omite si `dist/` ya existe) usando un contenedor Node efimero, sin necesitar Node.js instalado en el host.

Si cambias el codigo del frontend (`services/dashboard/frontend/src/`) y quieres verlo reflejado sin reiniciar el contenedor del dashboard:
```bash
make dashboard-build-force
```

## Estructura del proyecto

```
local-env/
  Makefile            <- comandos principales (make up/down/status/logs)
  config.mk           <- selección de servicios opcionales
  compose.yaml
  .env.example
  services/
    bind/               <- DNS BIND9 (Dockerfile + zonas)
    minica/             <- CA local + generacion de certs (Dockerfile + entrypoint.sh)
    nginx/
      etc/nginx/
        nginx.conf
        conf.d/
          http/         <- proxies HTTP/HTTPS (punto de extension para apps)
          stream/       <- proxies TCP/TLS (Kafka, ActiveMQ)
    dashboard/          <- UI web de gestion (FastAPI + Vue 3, siempre activo)
    localstack/
      init/ready.d/     <- scripts de init AWS (punto de extension para apps)
      services/         <- configuracion de servicios AWS
      volume/           <- datos persistentes (gitignored)
  docs/                 <- documentacion completa
```

## Keystores y truststores para Java

Tras el primer arranque, minica genera en `services/minica/app/certs/stores/`:

```bash
# Para Kafka
cp services/minica/app/certs/stores/ca-cert.ts \
  <tu-proyecto>/src/main/resources/ssl/kafka-local-env.ts

# Para ActiveMQ
cp services/minica/app/certs/stores/local-env.com.ks \
  <tu-proyecto>/src/main/resources/ssl/activemq-local-env.ks
cp services/minica/app/certs/stores/ca-cert.ts \
  <tu-proyecto>/src/main/resources/ssl/activemq-local-env.ts
```

Contrasena de todos los stores: `password`

## Problemas frecuentes

**Puerto 53 ocupado en Ubuntu**: `sudo systemctl stop systemd-resolved` o configurar `DNSStubListener=no` en `/etc/systemd/resolved.conf`.

**Certificados no confiados tras instalar la CA**: reiniciar el navegador. En Chrome: `chrome://net-internals/#hsts` -> borrar el dominio.

**nginx error "host not found in upstream"**: el servicio no esta arrancado. Ver estado con `docker compose ps` y arrancar el servicio o eliminar su .conf de nginx.

**minica no genera cert para un nuevo dominio**: reiniciar minica despues de anadir el .conf nginx:
```bash
docker compose restart minica
docker compose exec nginx nginx -s reload
```

Ver [docs/operations.md](docs/operations.md) para la lista completa de problemas y soluciones.
