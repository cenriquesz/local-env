# Integración de apps con local-env

Este documento explica cómo conectar una aplicación propia al entorno de desarrollo local-env para usar sus servicios (OpenSearch, Kafka, ActiveMQ, LocalStack) con HTTPS real y DNS propio.

---

## 1. Visión general del modelo de integración

local-env expone todos sus servicios a través de nginx (10.0.1.2), que actúa como punto de entrada único con TLS terminado por la CA local de minica. Hay dos modos de conexión según dónde corra la app:

### Modo A: app en el host (no contenerizada)

La app corre directamente en el host (con `mvn spring-boot:run`, `python app.py`, `node index.js`, etc.). Para que nginx pueda enrutar el tráfico de vuelta a ella, el .conf de nginx usa `host.docker.internal`, que resuelve al host desde dentro de los contenedores Docker.

```
Host
  mi-app (puerto 8080)  <---  nginx (10.0.1.2)  <---  navegador/cliente
```

La CA de minica debe estar instalada en el SO o configurada en el cliente para que HTTPS funcione sin errores de certificado.

### Modo B: app contenerizada (unida a local-env-net)

La app tiene su propio `compose.yaml` y une sus contenedores a la red Docker `local-env-net` (10.0.1.0/24). Desde dentro de esa red, nginx puede referenciar el contenedor directamente por nombre, sin pasar por el host.

```
local-env-net
  mi-servicio (contenedor)  <---  nginx (10.0.1.2)  <---  cliente externo
```

Esta opción es más robusta: elimina la dependencia de `host.docker.internal` y permite que los contenedores se comuniquen entre sí por nombre.

---

## 2. Puntos de extensión disponibles

Los directorios siguientes tienen un `.gitignore` que ignora todo excepto los ficheros del repo base. Cualquier fichero que añada la app queda ignorado por git, así el repo de local-env permanece limpio.

| Directorio | Qué acepta | Efecto |
|---|---|---|
| `services/nginx/etc/nginx/conf.d/http/` | Ficheros `.conf` de nginx (bloques `server`) | nginx los carga automáticamente al arrancar o al hacer `nginx -s reload`; minica detecta los `server_name` y genera los certificados TLS |
| `services/nginx/etc/nginx/conf.d/stream/` | Ficheros `.conf` de nginx (bloques `stream` para TCP) | Para proxies TCP/TLS adicionales (útil para protocolos que no son HTTP) |
| `services/localstack/init/ready.d/` | Scripts bash ejecutables | Se ejecutan en orden alfabético cuando LocalStack está listo y responde; usan `awslocal` para crear recursos AWS |

---

## 3. Estructura de directorios recomendada

Hay dos layouts posibles según la relación entre repos.

### Layout A: repos al mismo nivel (recomendado para proyectos independientes)

```
workspace/
  local-env/                          <- repo local-env
  mi-app/                             <- repo de la app
    Makefile
    local-env-setup/
      nginx/
        mi-app.local-env.com.conf     <- config nginx para el dominio de la app
      localstack/
        mi-app-init.sh                <- script de init de recursos AWS
    src/
    ...
```

El `Makefile` de la app apunta a `../local-env` para copiar los ficheros de configuración antes de arrancar.

### Layout B: local-env dentro de la app (gitignored)

```
mi-app/
  local-env/                          <- clon de local-env (en .gitignore de mi-app)
  Makefile
  local-env-setup/
    nginx/
      mi-app.local-env.com.conf
    localstack/
      mi-app-init.sh
  src/
  ...
```

Útil cuando se quiere que local-env forme parte del repositorio de la app sin commitear su contenido. Hay que añadir `local-env/` al `.gitignore` de la app.

---

## 4. Añadir un dominio nginx para tu app

### 4.1. Crear el fichero .conf

Crea `local-env-setup/nginx/mi-app.local-env.com.conf` en el repo de tu app. El bloque HTTP redirige a HTTPS y el bloque HTTPS hace el proxy al servicio real.

```nginx
# Bloque HTTP: redirige a HTTPS
server {
    listen 80;
    server_name mi-app.local-env.com;
    return 301 https://$host$request_uri;
}

# Bloque HTTPS: proxy a la app
server {
    listen 443 ssl;
    server_name mi-app.local-env.com;

    ssl_certificate     /etc/nginx/certs/live/mi-app.local-env.com/cert.pem;
    ssl_certificate_key /etc/nginx/certs/live/mi-app.local-env.com/key.pem;

    location / {
        # Si la app corre en el host, usa host.docker.internal:PUERTO
        proxy_pass http://host.docker.internal:8080;

        # Si la app es un contenedor en local-env-net, usa el nombre del servicio:
        # proxy_pass http://mi-servicio:8080;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4.2. Copiar el .conf al directorio de extensión

```bash
cp local-env-setup/nginx/mi-app.local-env.com.conf \
   ../local-env/services/nginx/etc/nginx/conf.d/http/
```

### 4.3. Regenerar los certificados y recargar nginx

minica genera certificados TLS cuando arranca, leyendo los `server_name` de los `.conf` presentes. Si ya estaba corriendo cuando se añadió el nuevo `.conf`, hay que reiniciarlo:

```bash
cd ../local-env

# Reiniciar minica para que genere el cert del nuevo dominio
docker compose restart minica

# Esperar a que minica termine de generar los certs (unos segundos)
sleep 5

# Recargar nginx con la nueva configuración
docker compose exec nginx nginx -s reload
```

### 4.4. Verificar que funciona

```bash
# Comprueba que el dominio resuelve (debe devolver 10.0.1.2)
dig mi-app.local-env.com

# Comprueba que HTTPS responde
curl -v https://mi-app.local-env.com/health
```

Si la CA de minica está instalada en el SO, `curl` no necesita parámetros adicionales. Si no está instalada, añade `--cacert path/to/local-env/services/minica/app/certs/ca_cert.pem`.

---

## 5. Unir el contenedor de la app a la red local-env-net

Si la app tiene su propio `compose.yaml`, puede unirse a la red `local-env-net` declarándola como red externa:

```yaml
# compose.yaml de la app
services:
  mi-servicio:
    image: mi-imagen
    networks:
      - local-env-net
    # También puede estar en su propia red interna:
    # networks:
    #   - local-env-net
    #   - internal

networks:
  local-env-net:
    external: true
    name: local-env-net
```

Con esto, desde el `.conf` de nginx se puede referenciar el contenedor por nombre de servicio en lugar de `host.docker.internal`:

```nginx
proxy_pass http://mi-servicio:8080;
```

Ventajas de este modo:
- Funciona igual en Linux, Mac y Windows sin ajustes.
- El contenedor puede acceder directamente a OpenSearch, Kafka, etc. por su nombre DNS interno (`opensearch.local-env.com`).
- La comunicación entre contenedores no sale al host ni a la red del SO.

### Volumen compartido `local-env-storage` (alternativa al bind mount por ruta de host)

Todo lo descrito arriba (unir `local-env-net`, copiar `.conf` de nginx, copiar scripts de LocalStack) asume que tu app vive en el mismo host y puede escribir directamente en las carpetas del repo de local-env. Si eso no es práctico (la app corre en otra máquina Docker, o no quieres acoplar tu compose a la ruta relativa de local-env), local-env expone un volumen Docker con nombre, `local-env-storage`, con esta estructura interna:

```
local-env-storage/
├── certs/              # copia de services/minica/app/certs (CA, live/, stores/)
├── nginx-http/          # .conf HTTP adicionales, recogidos por nginx automaticamente
├── nginx-stream/        # .conf stream (TCP/TLS) adicionales
└── localstack-ready/     # scripts de init de LocalStack adicionales
```

- **certs/**: minica copia aquí sus certificados cada vez que arranca o se reinicia (además de escribirlos en el bind mount de siempre, que sigue siendo la fuente real).
- **nginx-http/** y **nginx-stream/**: nginx ya incluye de forma recursiva `conf.d/http/**/*.conf` y `conf.d/stream/**/*.conf`, y el volumen está montado anidado dentro de esas rutas (`conf.d/http/shared` y `conf.d/stream/shared`). Cualquier `.conf` que dejes en `nginx-http/` o `nginx-stream/` del volumen, nginx lo recoge solo, sin recargar nada especial más allá del `nginx -s reload` habitual.
- **localstack-ready/**: montado en `/etc/localstack/init/ready.d/shared`, dentro del directorio de init de LocalStack.

Cualquier `compose.yaml` externo lo consume declarándolo como volumen externo, igual que se hace con `local-env-net`:

```yaml
# compose.yaml de la app
services:
  mi-servicio:
    image: mi-imagen
    volumes:
      - local-env-storage:/local-env-storage

volumes:
  local-env-storage:
    external: true
    name: local-env-storage
```

Desde ahí, la app deja sus ficheros en `/local-env-storage/nginx-http/mi-app.local-env.com.conf`, `/local-env-storage/localstack-ready/mi-app-init.sh`, o lee `/local-env-storage/certs/ca_cert.pem` - sin necesitar acceso al filesystem del host donde corre local-env.

**Nota:** esta vía es un complemento, no un reemplazo. Los directorios de extensión por bind mount (sección 2) siguen siendo el mecanismo principal y el único commiteado en `docs/`; usa `local-env-storage` solo cuando de verdad no tengas acceso a la ruta del host.

---

## 6. Inicializar recursos en LocalStack

### 6.1. Crear el script de init

Crea `local-env-setup/localstack/mi-app-init.sh`. El script usa `awslocal` (wrapper de `aws` CLI preconfigurado para LocalStack) para crear los recursos que necesite la app:

```bash
#!/bin/bash
# local-env-setup/localstack/mi-app-init.sh
# Se ejecuta automáticamente cuando LocalStack está listo.

set -e

echo "[mi-app] inicializando recursos LocalStack..."

# Buckets S3
awslocal s3api create-bucket --bucket mi-app-uploads
awslocal s3api create-bucket --bucket mi-app-exports

# Cola SQS FIFO
awslocal sqs create-queue \
  --queue-name mi-app-events.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

# Tabla DynamoDB
awslocal dynamodb create-table \
  --table-name mi-app-sessions \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Tema SNS
awslocal sns create-topic --name mi-app-notifications

echo "[mi-app] recursos LocalStack inicializados"
```

### 6.2. Hacer el script ejecutable y copiarlo

```bash
chmod +x local-env-setup/localstack/mi-app-init.sh

cp local-env-setup/localstack/mi-app-init.sh \
   ../local-env/services/localstack/init/ready.d/
```

El nombre del fichero determina el orden de ejecución (orden alfabético). Si hay dependencias entre scripts de distintas apps, usa un prefijo numérico: `01-mi-app-init.sh`, `02-otra-app-init.sh`.

### 6.3. Verificar que los recursos se crearon

```bash
# Listar los buckets S3 creados
awslocal --endpoint-url=https://s3.local-aws.com s3 ls

# Listar las colas SQS
awslocal --endpoint-url=https://sqs.us-east-1.local-aws.com sqs list-queues
```

---

## 7. Makefile de la app que orquesta local-env

El `Makefile` de la app centraliza todo el ciclo de vida: copiar la configuración a local-env, arrancar local-env con `make` (que sincroniza nginx y gestiona los profiles de Docker Compose) y arrancar la propia app.

```makefile
# Ruta a local-env. Ajusta según el layout elegido.
LOCAL_ENV_DIR ?= ../local-env
# Si local-env está dentro de la app (Layout B):
# LOCAL_ENV_DIR ?= ./local-env

# Directorios de extensión de local-env
NGINX_HTTP_DIR      = $(LOCAL_ENV_DIR)/services/nginx/etc/nginx/conf.d/http
LOCALSTACK_INIT_DIR = $(LOCAL_ENV_DIR)/services/localstack/init/ready.d

.PHONY: setup-local-env up down clean-local-env

# Copia los ficheros de configuración de la app a local-env.
# Se llama antes de arrancar local-env para que nginx y LocalStack
# los encuentren desde el primer arranque.
setup-local-env:
	cp local-env-setup/nginx/mi-app.local-env.com.conf $(NGINX_HTTP_DIR)/
	cp local-env-setup/nginx/local-env.json $(NGINX_HTTP_DIR)/mi-app.local-env.com.json
	cp local-env-setup/localstack/mi-app-init.sh $(LOCALSTACK_INIT_DIR)/

# Arranca todo el entorno: primero local-env, luego la app.
up: setup-local-env
	# Arrancar local-env (gestiona profiles y sincroniza nginx internamente)
	$(MAKE) -C $(LOCAL_ENV_DIR) up

	# Esperar a que minica genere el cert del nuevo dominio (primer arranque)
	sleep 5
	$(MAKE) -C $(LOCAL_ENV_DIR) nginx-reload

	# Arrancar la propia app
	docker compose up -d

# Para todo: primero la app, luego local-env.
down:
	docker compose down
	$(MAKE) -C $(LOCAL_ENV_DIR) down

# Limpia los ficheros de configuración copiados a local-env.
# Útil para dejar local-env en estado limpio entre sesiones.
clean-local-env:
	rm -f $(NGINX_HTTP_DIR)/mi-app.local-env.com.conf
	rm -f $(NGINX_HTTP_DIR)/mi-app.local-env.com.json
	rm -f $(LOCALSTACK_INIT_DIR)/mi-app-init.sh
```

Flujo habitual de trabajo:

```bash
# Primera vez (o después de clean-local-env)
make up

# Parar todo al terminar el día
make down

# Limpiar la configuración de esta app de local-env
make clean-local-env
```

### Por qué usar `make -C ../local-env up` y no `docker compose up -d`

El `Makefile` de local-env hace dos cosas que el comando directo no hace:

1. Sincroniza las configs nginx de los servicios opcionales (opensearch, kafka, etc.) en los directorios activos según lo configurado en `config.mk`.
2. Pasa los `--profile` correctos a Docker Compose para arrancar solo los servicios habilitados.

Llamar a `docker compose up -d` directamente saltaría ambos pasos.

---

## 8. Configuración de clientes por lenguaje

### Spring Boot / Java

#### OpenSearch

```yaml
# application-local.yml
spring:
  elasticsearch:
    uris: https://opensearch.local-env.com
    username: admin
    password: myPassword123!
```

El cliente de Spring Data Elasticsearch requiere que la CA de minica esté instalada en la JVM o que se configure un `SSLContext` personalizado. Consulta `docs/deployment.md` para el procedimiento de instalación de la CA.

#### Kafka

```yaml
# application-local.yml
spring:
  kafka:
    bootstrap-servers: kafka.local-env.com:9092
    properties:
      security.protocol: SSL
      ssl.truststore.location: classpath:ssl/kafka-local-env.ts
      ssl.truststore.password: password
```

El truststore `ca-cert.ts` se genera automáticamente por minica y está disponible en `local-env/services/minica/app/certs/stores/ca-cert.ts`. Cópialo a `src/main/resources/ssl/kafka-local-env.ts` en tu proyecto. Si tu proyecto no tiene acceso al filesystem de `local-env` (otra máquina, Docker remoto), descárgalo desde `https://dashboard.local-env.com/api/certs/stores/ca-cert.ts`.

#### ActiveMQ

```yaml
# application-local.yml
spring:
  activemq:
    broker-url: ssl://localhost:61617
    user: admin
    password: admin
  activemq-classic:
    pool:
      enabled: true
    ssl:
      key-store: classpath:ssl/activemq-local-env.ks
      key-store-password: password
      trust-store: classpath:ssl/activemq-local-env.ts
      trust-store-password: password
```

Los stores de ActiveMQ también los genera minica. Encuéntralos en `local-env/services/minica/app/certs/stores/` (usa `local-env.com.ks`/`local-env.com.ts` si no se ha generado un store específico para el dominio de ActiveMQ), o descárgalos desde el dashboard: `GET https://dashboard.local-env.com/api/certs/stores`.

#### AWS / LocalStack

```yaml
# application-local.yml
spring:
  cloud:
    aws:
      region:
        static: us-east-1
      credentials:
        access-key: test
        secret-key: test
      s3:
        endpoint: https://s3.local-aws.com
      sqs:
        endpoint: https://sqs.us-east-1.local-aws.com
      dynamodb:
        endpoint: https://dynamodb.us-east-1.local-aws.com
```

Si la CA de minica está instalada en el SO (y por tanto en el truststore por defecto de la JVM), no hace falta configuración SSL adicional.

---

### Python

#### boto3

```python
import boto3

# Con la ruta explícita a la CA de minica
ca_cert = "path/to/local-env/services/minica/app/certs/ca_cert.pem"

s3 = boto3.client(
    "s3",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    endpoint_url="https://s3.local-aws.com",
    verify=ca_cert,
)

sqs = boto3.client(
    "sqs",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    endpoint_url="https://sqs.us-east-1.local-aws.com",
    verify=ca_cert,
)

dynamodb = boto3.client(
    "dynamodb",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    endpoint_url="https://dynamodb.us-east-1.local-aws.com",
    verify=ca_cert,
)
```

Alternativa: instalar la CA en el SO con `docs/deployment.md` y omitir el parámetro `verify`. boto3 usa la CA del sistema por defecto.

#### opensearch-py

```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=["https://opensearch.local-env.com"],
    http_auth=("admin", "myPassword123!"),
    use_ssl=True,
    verify_certs=True,
    ca_certs="path/to/local-env/services/minica/app/certs/ca_cert.pem",
)

# Verificar la conexión
info = client.info()
print(f"OpenSearch {info['version']['number']} listo")
```

---

## 9. Visibilidad en el dashboard de local-env

local-env incluye un dashboard web accesible en `https://dashboard.local-env.com`. La sección "Apps" del dashboard detecta automáticamente todas las apps externas que hayan copiado un `.conf` en el directorio de extensión de nginx - sin necesidad de registro manual.

**Limitación conocida:** el dashboard monta directamente `services/nginx/etc/nginx/conf.d` del host, no el volumen `local-env-storage`. Las apps que dejen su `.conf` únicamente en `local-env-storage/nginx-http/` (sección 5) no aparecerán en el dashboard aunque nginx sí las sirva correctamente. Si necesitas visibilidad en el dashboard, usa el mecanismo de bind mount (sección 2/4).

### Qué detecta el dashboard

El dashboard escanea `services/nginx/etc/nginx/conf.d/http/` y muestra cualquier fichero `.conf` que no pertenezca al core de local-env. Para cada dominio detectado, intenta resolver el contenedor upstream leyendo el bloque `set $upstream` del `.conf` y consulta su estado a Docker.

### Identificar tu app: `local-env.json`

Sin metadatos adicionales, el dashboard agrupa los dominios bajo "Sin identificar". Para que aparezcan con el nombre correcto, crea un fichero `local-env.json` en tu carpeta de configuración de local-env y cópialo junto al `.conf`:

```json
{
  "app": "mi-app",
  "repo": "github.com/cenriquesz/mi-app"
}
```

El fichero debe nombrarse igual que el `.conf` pero con extensión `.json`. Por ejemplo, si el conf es `mi-app.local-env.com.conf`, el fichero de metadatos es `mi-app.local-env.com.json`. El Makefile de ejemplo de la sección 7 ya lo copia automáticamente.

Resultado en el dashboard:

```
Apps detectadas
  mi-app
    api.local-env.com     running   [Abrir]
    web.local-env.com     running   [Abrir]
```

### Requisito del .conf para detección de estado

Para que el dashboard pueda determinar el estado del contenedor de la app, el bloque `location` del `.conf` debe usar el patrón de variable proxy_pass (igual que los configs del core de local-env):

```nginx
location / {
    resolver 10.0.1.3 valid=10s ipv6=off;
    set $upstream http://mi-contenedor:8080;
    proxy_pass $upstream;
    ...
}
```

El dashboard extrae el nombre del contenedor (`mi-contenedor`) del valor de `$upstream` y consulta su estado a Docker. Con `proxy_pass http://mi-contenedor:8080;` directo (sin variable) también funciona nginx, pero el dashboard no puede extraer el nombre del contenedor y mostrará estado "unknown".

### Documentación OpenAPI/Swagger automática

Cada servicio detectado en la vista "Apps" tiene un botón **API**. Al pulsarlo, el dashboard prueba automáticamente, a través de nginx, las rutas donde suelen vivir los specs OpenAPI/Swagger:

| Ruta | Frameworks típicos |
|---|---|
| `/openapi.json` | FastAPI, Express con swagger-jsdoc, NestJS |
| `/v3/api-docs` | Spring Boot con Springdoc |
| `/swagger.json` | Varios |
| `/swagger/v1/swagger.json` | ASP.NET con Swashbuckle |
| `/api-docs` | Varios |

Si tu app expone su spec en alguna de esas rutas, no tienes que hacer nada más: aparecerá renderizado con Swagger UI dentro del propio dashboard. Si no responde ninguna, el dashboard simplemente muestra un aviso — no afecta al resto de la detección de la app (estado, URL, etc).

Si tu spec vive en una ruta distinta a las anteriores, de momento no hay forma de configurarla desde el dashboard; la alternativa es enlazarla directamente desde tu propia consola/README, o exponerla también en `/openapi.json` (redirect o alias) para que el dashboard la encuentre.

---

## 10. Notas y advertencias

- **`host.docker.internal` en Linux:** en Docker Desktop (Mac/Windows) está disponible por defecto. En Docker Engine Linux, local-env ya lo configura con `extra_hosts: ["host.docker.internal:host-gateway"]` en el servicio nginx. Si la app corre en otro contenedor no perteneciente a local-env-net, puede que necesite añadir el mismo `extra_hosts` en su propio `compose.yaml`.

- **Contraseña de los stores:** todos los keystores y truststores generados por minica tienen la contraseña `password` (sin cambiar). No son apropiados para entornos que no sean desarrollo local.

- **Subdominios de local-aws.com sin configuración extra:** cualquier subdominio de `local-aws.com` (por ejemplo `mi-bucket.s3.local-aws.com`) resuelve automáticamente y llega a LocalStack gracias a la configuración de BIND9. Solo hace falta que el recurso AWS exista (creado con `awslocal`).

- **Proxy por nombre de contenedor:** si se quiere referenciar un contenedor desde nginx por nombre de servicio (`proxy_pass http://mi-servicio:8080`), ese contenedor debe estar unido a `local-env-net`. Los contenedores en redes distintas no son accesibles por nombre desde nginx.

- **El .gitignore de local-env protege el repo base:** los `.gitignore` de los directorios de extensión solo permiten los ficheros que pertenecen al repo de local-env. Los ficheros de configuración de apps quedan ignorados automáticamente y no se commitean por accidente.

- **Orden de los scripts de init en LocalStack:** los scripts en `ready.d/` se ejecutan en orden alfabético. Si hay dependencias entre ellos (por ejemplo, un script crea un topic SNS al que otro se suscribe), usa prefijos numéricos para controlar el orden: `01-infraestructura.sh`, `02-mi-app.sh`.

- **Primera ejecución de minica:** en el primer arranque, minica genera la CA y los certificados de todos los dominios presentes en los `.conf` de nginx. Esto puede tardar entre 5 y 15 segundos. El `sleep 5` del Makefile de ejemplo puede no ser suficiente en máquinas lentas; ajústalo si ves errores de certificado en el arranque.

- **Instalar la CA de minica en el SO:** para que los navegadores y clientes que usan la CA del sistema confíen en los certificados, instala `local-env/services/minica/app/certs/ca_cert.pem` como CA raíz de confianza. El procedimiento está detallado en `docs/deployment.md`.
