# Flujos principales de local-env

## 1. Flujo de arranque

El orden de inicio no es arbitrario: cada servicio depende de que el anterior este listo. Docker Compose modela estas dependencias con `depends_on`.

```mermaid
sequenceDiagram
    participant DC as Docker Compose
    participant B as bind (DNS)
    participant M as minica (CA)
    participant OS as opensearch (OpenSearch)
    participant OSD as opensearch-dashboards
    participant LS as localstack
    participant AMQ as activemq
    participant K as kafka
    participant KD as kafka-dashboards
    participant N as nginx

    DC->>B: arranca bind
    Note over B: DNS autoritativo listo en 10.0.1.3
    DC->>M: arranca minica
    Note over M: genera certs y queda en tail -f /dev/null
    DC->>OS: arranca opensearch (OpenSearch)
    Note over OS: necesita estar listo antes que localstack y opensearch-dashboards
    DC->>OSD: arranca opensearch-dashboards
    Note over OSD: depends_on opensearch
    DC->>LS: arranca localstack
    Note over LS: depends_on opensearch (usa OpenSearch como backend)
    DC->>AMQ: arranca activemq
    DC->>K: arranca kafka
    Note over K: modo KRaft; broker y controller en el mismo nodo, sin Zookeeper
    DC->>KD: arranca kafka-dashboards
    DC->>N: arranca nginx
    Note over N: depends_on todos los anteriores; sin nginx no hay acceso externo
```

**Por que este orden:**
- bind arranca primero porque nginx y el resto de contenedores necesitan resoluciones DNS durante su inicio
- minica arranca antes que nginx porque nginx necesita los certificados en `/etc/nginx/certs/` para poder levantar los bloques SSL
- opensearch arranca antes que localstack porque LocalStack usa OpenSearch como backend para el servicio `opensearch`
- kafka ya no depende de zookeeper: desde Confluent 8.x (Kafka 4.0) usa KRaft, con broker y controller integrados en el mismo proceso
- nginx arranca al final porque actua de fachada; si arrancara antes, llegarian peticiones a servicios que todavia no estan listos

---

## 2. Generacion de certificados (minica/entrypoint.sh)

Este proceso ocurre una sola vez al arrancar el contenedor minica.

**Paso 1 - Detectar dominios:**
Lee todos los ficheros `.conf` de `/etc/nginx/conf.d/http/`. Por cada fichero, usa el nombre del fichero (sin extension) como dominio. Por ejemplo, `local-env.com.conf` -> dominio `local-env.com`.

**Paso 2 - Excluir el dominio de LocalStack:**
El dominio configurado en `LOCALSTACK_HOST` (tipicamente `local-aws.com`) se excluye de la lista general porque necesita tratamiento especial en el paso 4.

**Paso 3 - Generar certificados generales:**
Para cada dominio de la lista general, llama a `minica` generando un certificado que cubre tanto el dominio raiz como el wildcard:
```
minica -domains "local-env.com,*.local-env.com"
```
Esto genera `cert.pem` y `key.pem` en `certs/live/<dominio>/`.

**Paso 4 - Generar certificado de LocalStack con SANs extra:**
Para `local-aws.com` genera un unico certificado con todos los Subject Alternative Names que necesita AWS SDK para validar URLs como `s3.us-east-1.local-aws.com`:
```
minica -domains "local-aws.com,*.local-aws.com,*.us-east-1.local-aws.com,*.s3.us-east-1.local-aws.com,*.us-east-1.opensearch.local-aws.com"
```

**Paso 5 - Generar keystores Java (JKS):**
Para cada directorio de certificado generado:
1. `openssl pkcs12 -export` -> crea `<dominio>.p12` (PKCS12, compatible con cualquier lenguaje)
2. `keytool -importkeystore` -> importa el .p12 al JKS `<dominio>.ks`
3. `keytool -import` -> anade la CA raiz al mismo JKS (para que la JVM confie en el emisor)

**Paso 6 - Generar truststore global:**
Crea `ca-cert.ts` con solo el certificado raiz de la CA. Las apps Java pueden usar este fichero como truststore para confiar en todos los certificados del entorno sin importar el dominio.

**Paso 7 - Permisos y sleep:**
Ajusta el propietario de `/app/certs/` a UID 1000 y queda en `tail -f /dev/null` para mantener el volumen accesible.

---

## 3. Resolucion DNS y enrutamiento de peticiones

El comportamiento del DNS cambia segun desde donde se realice la consulta.

### Desde el host (app corriendo en el sistema operativo del host)

El host tiene configurado en su DNS `127.0.0.1:53` (o la IP del contenedor bind si es accesible directamente).

```
App (host)
  |
  | 1. resolucion DNS: opensearch.local-env.com ?
  v
bind:53 (via 127.0.0.1:53, vista "external")
  |
  | 2. responde: 127.0.0.1
  v
Puerto 443 del host
  |
  | 3. nginx escucha en 0.0.0.0:443 -> recibe la conexion
  v
nginx (SNI: opensearch.local-env.com)
  |
  | 4. proxea segun server_name
  v
https://opensearch:9200 (OpenSearch dentro de la red Docker)
```

La clave esta en la vista `external`: BIND resuelve a `127.0.0.1`, que es el loopback del host. Como nginx tiene el puerto 443 mapeado al host (`443:443`), la conexion llega a nginx aunque el DNS no sepa que nginx tiene la IP `10.0.1.2`.

### Desde otro contenedor en local-env-net

Un contenedor en la red `10.0.1.0/24` usa bind como servidor DNS (configurado via Docker o manualmente).

```
Contenedor (10.0.1.x)
  |
  | 1. resolucion DNS: opensearch.local-env.com ?
  v
bind (10.0.1.3), vista "internal" (origen en 10.0.1.0/24)
  |
  | 2. responde: 10.0.1.2
  v
nginx (10.0.1.2:443) dentro de la red Docker
  |
  | 3. proxea segun server_name
  v
https://opensearch:9200
```

La vista `internal` resuelve directamente a la IP de nginx dentro de la red, evitando salir al host.

---

## 4. Peticion HTTPS de extremo a extremo

Ejemplo completo: una app en el host llama a `https://opensearch.local-env.com/mi-indice/_search`.

**Salto 1 - Resolucion DNS:**
La app llama al resolver del SO. El SO consulta bind en `127.0.0.1:53`. Bind aplica la vista `external` y responde con `127.0.0.1`.

**Salto 2 - Establecimiento TLS:**
La app abre una conexion TCP a `127.0.0.1:443`. nginx responde con el certificado `certs/live/local-env.com/cert.pem`, que cubre `*.local-env.com`. Si la app tiene instalada la CA de minica (`ca_cert.pem`) en su trust store, la validacion TLS pasa sin errores.

**Salto 3 - Routing por SNI/Host:**
nginx recibe la conexion con SNI `opensearch.local-env.com`. Busca en sus bloques `server` el que tiene `server_name opensearch.local-env.com` con `listen 443 ssl` y lo encuentra en `conf.d/http/local-env.com.conf`.

**Salto 4 - Proxy al backend:**
nginx abre una conexion HTTPS a `https://opensearch:9200` dentro de la red Docker. OpenSearch atiende la peticion y devuelve la respuesta. nginx la retransmite a la app.

**Lo que ve la app:** una conexion HTTPS normal a un nombre de dominio con certificado valido. No sabe que hay nginx en medio ni que OpenSearch esta en un contenedor.

---

## 5. Init de LocalStack

Cuando LocalStack termina de arrancar, ejecuta automaticamente todos los scripts de `/etc/localstack/init/ready.d/`. El script base `init.sh` crea los recursos minimos que cualquier aplicacion del ecosistema puede necesitar.

**Recursos creados:**

1. **Rol IAM `BasicRole`** - rol con politica STS minima para que las apps puedan asumir roles localmente

2. **Dominio OpenSearch `test-opensearch`** - crea un dominio OpenSearch gestionado por LocalStack. Como `OPENSEARCH_CUSTOM_BACKEND` apunta a `opensearch:9200`, LocalStack redirige las operaciones al OpenSearch real del entorno en lugar de levantar uno propio

3. **Bucket S3 `test-bucket`** - bucket de proposito general

4. **Bucket S3 `sqs-bucket`** - bucket auxiliar para patrones de cola con S3 (DLQ, redrive, etc.)

5. **Colas SQS FIFO** - `test-sqs-queue-01.fifo` y `test-sqs-queue-02.fifo` con deduplicacion basada en contenido

6. **Identidad SES `no-reply@local-env.com`** - identidad verificada para poder enviar emails simulados sin necesidad de un dominio real

**Como anadir recursos propios:** crear un nuevo script `.sh` en `services/localstack/init/ready.d/`. El `.gitignore` del directorio excluye estos ficheros adicionales para que no contaminen el repo base. LocalStack ejecuta todos los scripts del directorio en orden alfabetico.
