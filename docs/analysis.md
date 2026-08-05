# Análisis del proyecto local-env

## 1. Propósito del proyecto

`local-env` es un entorno de desarrollo local basado en Docker que permite a equipos de ingeniería simular servicios de producción sin depender de entornos remotos. Su objetivo principal es que una aplicación en desarrollo pueda conectarse a `https://opensearch.local-env.com` o `kafka.local-env.com:9092` exactamente igual que lo haría en producción: con HTTPS real, DNS propio y TLS auténtico firmado por una CA local.

El problema que resuelve es la brecha entre desarrollo y producción en cuanto a:

- Configuración de red: en producción las apps usan dominios FQDN, no `localhost`. Con `local-env` los dominios existen y resuelven correctamente.
- TLS: en producción todo va cifrado. `local-env` emite certificados reales firmados por una CA local (`minica`) en lugar de usar `skip_ssl_verify` o certificados autofirmados ad hoc.
- Servicios de infraestructura: OpenSearch, Kafka, ActiveMQ, AWS (via LocalStack) se ejecutan localmente con la misma interfaz que en producción.

Va dirigido a equipos que trabajan con aplicaciones Java o JVM en las que el cliente de Kafka, el cliente de OpenSearch o el SDK de AWS está configurado con URLs de producción, y se quiere reutilizar esa configuración en local sin parches.

---

## 2. Componentes

| Servicio | Imagen | Rol | URL de acceso | Obligatorio |
|---|---|---|---|---|
| `bind` | alpine + BIND9 | DNS autorizado para `*.local-env.com` y `*.local-aws.com` | - | Si |
| `minica` | golang + minica | CA local: genera certs TLS, keystores y truststores | - | Si |
| `nginx` | nginx:latest | Reverse proxy HTTP/HTTPS y TCP/TLS (Kafka, ActiveMQ) | - | Si |
| `opensearch` | opensearch:3.7.0 | Motor de búsqueda | `https://opensearch.local-env.com` | No |
| `opensearch-dashboards` | opensearch-dashboards:3.7.0 | UI de OpenSearch | `https://opensearch-dashboards.local-env.com` | No |
| `localstack` | localstack/localstack:stable | Emulación de servicios AWS | `https://*.local-aws.com` | No |
| `activemq` | apache/activemq-classic:latest | Broker de mensajería (JMS) | `https://activemq-dashboards.local-env.com`, `localhost:61617` (TCP/TLS) | No |
| `zookeeper` | cp-zookeeper:7.5.0 | Coordinador de Kafka | - (interno) | No (dependencia de Kafka) |
| `kafka` | cp-kafka:7.5.0 | Broker Kafka | `kafka.local-env.com:9092` (TCP/TLS) | No |
| `kafka-dashboards` | kafdrop | UI de Kafka | `https://kafka-dashboards.local-env.com` | No |

---

## 3. Red y DNS

### Red Docker

- Nombre: `local-env-net`
- Tipo: bridge
- Subred: `10.0.1.0/24`
- Gateway: `10.0.1.1`
- IPs fijas asignadas:
  - `nginx`: `10.0.1.2`
  - `bind`: `10.0.1.3`

### Resolución DNS con BIND9 (vistas internal/external)

BIND9 sirve dos vistas distintas según el origen de la consulta:

| Vista | Clientes | Resolución |
|---|---|---|
| `internal` | IPs en `10.0.1.0/24` (contenedores Docker) | `*.local-env.com` y `*.local-aws.com` -> `10.0.1.2` (nginx) |
| `external` | Cualquier otro cliente (host, VMs externas) | `*.local-env.com` y `*.local-aws.com` -> `127.0.0.1` |

Esta dualidad permite que tanto los contenedores como la máquina host resuelvan los dominios, pero apuntando a la IP correcta según desde donde se consulta. Los contenedores van directo a nginx dentro de la red Docker; el host va a `127.0.0.1`, donde nginx expone los puertos 80 y 443.

Para que el host use el DNS de `local-env`, hay que configurarlo como servidor DNS primario (por ejemplo, via `/etc/resolv.conf` o configuración de red del sistema operativo) apuntando a `127.0.0.1:53`.

---

## 4. Servicios obligatorios vs opcionales

### Núcleo (siempre deben estar activos)

Estos tres servicios son la infraestructura transversal de la que depende todo lo demás:

| Servicio | Por qué es obligatorio |
|---|---|
| `bind` | Sin DNS no resuelven los dominios. Es la base para que cualquier otro servicio sea accesible por nombre. |
| `minica` | Genera los certificados TLS antes de que nginx arranque. Sin él, nginx no tiene certs y no puede servir HTTPS ni TLS. |
| `nginx` | Es el punto de entrada único para todo el tráfico. Sin él, ningún dominio es accesible aunque los servicios estén levantados. |

### Opcionales (se activan según las necesidades del proyecto)

| Servicio | Cuándo activarlo |
|---|---|
| `opensearch` + `opensearch-dashboards` | Cuando la app usa OpenSearch para búsqueda o analítica. |
| `localstack` | Cuando la app usa servicios AWS: S3, SQS, SES, OpenSearch Serverless, IAM. |
| `activemq` | Cuando la app usa JMS / ActiveMQ como broker de mensajería. |
| `zookeeper` + `kafka` + `kafka-dashboards` | Cuando la app produce o consume mensajes Kafka. `zookeeper` es dependencia interna de `kafka`. |

---

## 5. URLs de acceso disponibles

| URL | Protocolo | Backend | Descripción |
|---|---|---|---|
| `https://opensearch.local-env.com` | HTTPS | `opensearch:9200` | API REST de OpenSearch |
| `https://opensearch-dashboards.local-env.com` | HTTPS | `opensearch-dashboards:5601` | UI de OpenSearch Dashboards |
| `https://activemq-dashboards.local-env.com` | HTTPS | `activemq:8161` | Consola web de ActiveMQ |
| `https://kafka-dashboards.local-env.com` | HTTPS | `kafka-dashboards:9000` | UI de Kafdrop para Kafka |
| `https://*.local-aws.com` | HTTPS | `localstack:4566` | Endpoint AWS emulado (S3, SQS, SES, etc.) |
| `kafka.local-env.com:9092` | TCP/TLS | `kafka:9092` | Broker Kafka con TLS |
| `localhost:61617` | TCP/TLS | `activemq:61616` | Connector STOMP/OpenWire de ActiveMQ con TLS |

Todas las URLs HTTPS usan certificados firmados por la CA de `minica`. Para que las apps y el navegador confíen en ellos, hay que importar `minica.pem` (la CA raíz) en el truststore del sistema o del JVM correspondiente.

Para aplicaciones JVM, `minica` genera automáticamente:
- `ca-cert.ts`: truststore con solo la CA raíz, para importar en la JVM.
- `*.ks` / `*.p12`: keystores por dominio, si se necesita autenticación de cliente.

---

## 6. Estado actual del código

### Qué funciona bien

- **Infraestructura central sólida**: el trío `bind` + `minica` + `nginx` está bien diseñado. La separación de responsabilidades es clara y el mecanismo de generación de certs con keystores JVM es especialmente útil para aplicaciones Java.
- **TLS completo en todos los protocolos**: tanto HTTP/HTTPS como los streams TCP (Kafka, ActiveMQ) van cifrados. Esto es poco común en entornos de desarrollo locales y añade mucho valor.
- **DNS con vistas**: la distinción `internal`/`external` en BIND es una solución elegante que evita conflictos entre contenedores y host.
- **LocalStack init automatizado**: `init.sh` levanta automáticamente los recursos AWS más habituales (rol IAM, OpenSearch, S3, SQS, SES), lo que elimina pasos manuales en el primer arranque.
- **Estructura de extensión prevista**: los `.gitignore` en `conf.d/http/` y `conf.d/stream/` indican que el diseño contempla que las apps añadan sus propios `.conf`, aunque no está documentado.

### Qué está incompleto o falta

- **README en estado placeholder**: la sección "Getting Started" tiene solo `#TODO`. Cualquier desarrollador nuevo no sabe cómo arrancar el entorno.
- **Sin Makefile**: el arranque es `docker compose up` directamente, sin targets con defaults razonables (`up`, `down`, `logs`, `reset`).
- **Sin mecanismo de selección de servicios**: no hay forma declarativa de decir "quiero solo OpenSearch y LocalStack". Hay que listar los servicios manualmente en el comando.
- **`depends_on` de nginx acoplado a todos los servicios**: si cualquier servicio falla al arrancar, nginx queda en espera indefinida. Esto hace que el entorno sea frágil cuando solo se quiere un subconjunto de servicios.
- **Patrón de integración de apps sin documentar**: los `.gitignore` de extensión existen, pero no hay ningún documento que explique cómo una app añade su `.conf` a nginx ni cuál es el flujo esperado.

---

## 7. Gaps identificados y propuestas

### Gap 1 - Sin Makefile

**Problema**: arrancar el entorno requiere conocer la sintaxis de `docker compose` y qué servicios existen. No hay un punto de entrada único con defaults razonables.

**Propuesta**: añadir un `Makefile` con targets básicos:

```makefile
up:        ## Arranca los servicios definidos en config.mk
    docker compose up -d $(CORE) $(SERVICES)

down:      ## Para todos los servicios
    docker compose down

logs:      ## Muestra logs en tiempo real
    docker compose logs -f

reset:     ## Para, borra volúmenes y vuelve a arrancar
    docker compose down -v && $(MAKE) up
```

---

### Gap 2 - Sin selección de servicios

**Problema**: todos los servicios arrancan siempre. Un desarrollador que solo necesita OpenSearch levanta también Kafka, ActiveMQ, Zookeeper y LocalStack sin quererlo.

**Propuesta**: un fichero `config.mk` (no commiteado, generado desde `config.mk.example`) donde el usuario declara qué servicios quiere:

```makefile
# config.mk - copia de config.mk.example, no commitear
SERVICES = opensearch opensearch-dashboards localstack
```

El `Makefile` lo incluye y construye el comando:

```makefile
CORE = bind minica nginx
-include config.mk
SERVICES ?=

up:
    docker compose up -d $(CORE) $(SERVICES)
```

Así el núcleo siempre arranca y el usuario elige el resto sin tocar `compose.yaml`.

---

### Gap 3 - `depends_on` de nginx acoplado a todos los servicios

**Problema**: el `depends_on` de nginx incluye todos los servicios opcionales. Si alguno falla o no se quiere arrancar, nginx queda en espera indefinida y el entorno no levanta.

**Propuesta**: eliminar los servicios opcionales del `depends_on` de nginx. Nginx solo debería depender de `minica` (necesita los certs para arrancar). Los servicios opcionales pueden no estar levantados: nginx devolverá `502` en sus rutas, lo cual es un comportamiento correcto y esperado.

---

### Gap 4 - Nginx no es condicional

**Problema**: todas las rutas están siempre en la configuración de nginx. Si `kafka-dashboards` no está levantado, nginx arranca sin error pero devuelve `502` para esa ruta. En un entorno parcial esto genera confusión.

**Propuesta**: separar cada servicio en su propio `.conf` (por ejemplo: `opensearch.conf`, `kafka.conf`, `activemq.conf`) en lugar de un único `local-env.com.conf` monolítico. El `Makefile` copia a `conf.d/http/` solo los `.conf` de los servicios declarados en `config.mk` antes de llamar a `docker compose up`. Así nginx solo tiene las rutas de los servicios que van a estar disponibles.

---

### Gap 5 - README incompleto

**Problema**: la sección "Getting Started" del README contiene solo `#TODO`. Un desarrollador nuevo no sabe cómo arrancar el entorno, qué prerequisitos necesita ni cómo configurar el DNS y la CA en su máquina.

**Propuesta**: completar el README con al menos:

1. Prerequisitos: Docker, Docker Compose, y cómo configurar DNS en el sistema operativo para apuntar a `127.0.0.1`.
2. Primer arranque: `cp config.mk.example config.mk`, editar `config.mk`, y `make up`.
3. Importar la CA: cómo añadir `minica.pem` al sistema y al JVM truststore.
4. Verificación: qué URLs deben responder y cómo comprobarlo con `curl`.

---

### Gap 6 - Patrón de integración de apps sin documentar

**Problema**: los `.gitignore` en `conf.d/http/` y `conf.d/stream/` permiten a las apps añadir sus propios `.conf` de nginx sin que se commiteen al repo. Es un mecanismo de extensión útil, pero no está documentado en ningún sitio. Ningún desarrollador nuevo sabe que existe ni cómo usarlo.

**Propuesta**: documentar el patrón en el README o en un fichero dedicado `docs/integrating-your-app.md`:

1. Explicar qué son los `.conf` de extensión y por qué no se commitean.
2. Mostrar un ejemplo de `.conf` para añadir una app al proxy (`server_name myapp.local-env.com`).
3. Documentar cómo pedir a `minica` un certificado para el nuevo dominio o usar el wildcard existente.
4. Indicar que el fichero `.conf` debe copiarse antes de `make up` o que `make up` puede automatizar esa copia si la app lo configura.
