# Despliegue de local-env

Guía de puesta en marcha del entorno de desarrollo local. Incluye OpenSearch, Kafka, ActiveMQ y LocalStack (AWS), todos con HTTPS real via minica y DNS via BIND9.

---

## 1. Prerrequisitos

### Software

- Docker Desktop >= 24, o Docker Engine con el plugin Docker Compose
- Git

### Puertos libres en el host

| Puerto | Protocolo | Servicio |
|--------|-----------|---------|
| 53 | UDP y TCP | BIND9 (DNS) |
| 80 | TCP | nginx (HTTP) |
| 443 | TCP | nginx (HTTPS) |
| 9092 | TCP | Kafka (TLS) |
| 61617 | TCP | ActiveMQ (TLS) |

### Memoria para Docker

Se recomiendan al menos 8 GB asignados a Docker. En Docker Desktop: Settings -> Resources -> Memory.

### LocalStack Auth Token

LocalStack requiere un token para funciones avanzadas, incluyendo el soporte de OpenSearch. El token es gratuito; obtenerlo en [localstack.cloud](https://localstack.cloud).

---

## 2. Primera puesta en marcha

### 2.1 Clonar y preparar el fichero de entorno

```bash
git clone <url-del-repo> local-env
cd local-env

cp .env.example .env
```

Editar `.env` y sustituir `LOCALSTACK_AUTH_TOKEN` por el token real:

```
LOCALSTACK_AUTH_TOKEN=ls-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

El resto de valores del `.env.example` son válidos para arrancar sin cambios adicionales.

### 2.2 Arrancar los servicios

```bash
make up
```

Esto sincroniza las configs de nginx según los servicios habilitados en `config.mk` y lanza Docker Compose con los profiles correspondientes. Los servicios core (bind, minica, nginx) arrancan siempre.

Para personalizar qué servicios opcionales se levantan, editar `config.mk` antes de ejecutar `make up` (ver sección 7).

### 2.3 Esperar a que los servicios levanten

BIND y minica deben terminar antes de que nginx pueda resolver los upstreams. En un primer arranque, minica genera todos los certificados, lo que puede tardar entre 15 y 30 segundos.

Verificar el estado:

```bash
docker compose ps
```

Todos los servicios deben aparecer en estado `running` o `healthy`. Si alguno aparece como `restarting`, revisar sus logs:

```bash
docker compose logs -f <nombre-servicio>
```

### 2.4 Instalar la CA de minica en el sistema operativo

Paso obligatorio para que los certificados HTTPS sean confiados. Ver sección 4 para instrucciones detalladas.

### 2.5 Configurar el DNS del sistema operativo

Paso necesario para que los dominios `*.local-env.com` y `*.local-aws.com` resuelvan. Ver sección 3 para instrucciones por SO.

### 2.6 Verificar que todo funciona

Ver sección 5.

---

## 3. Configuración DNS del sistema operativo

El DNS del host debe delegar los dominios `local-env.com` y `local-aws.com` al BIND9 del contenedor, que escucha en `127.0.0.1:53`.

### Linux con systemd-resolved

Crear el fichero de configuración de dominio:

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d

sudo tee /etc/systemd/resolved.conf.d/local-env.conf > /dev/null <<'EOF'
[Resolve]
DNS=127.0.0.1
Domains=~local-env.com ~local-aws.com
EOF

sudo systemctl restart systemd-resolved
```

Nota: si el puerto 53 está ocupado por systemd-resolved (frecuente en Ubuntu), ver el problema 1 de la sección de problemas conocidos.

### macOS

```bash
sudo mkdir -p /etc/resolver

echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/local-env.com
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/local-aws.com
```

Los cambios se aplican sin reiniciar. Verificar con `scutil --dns`.

### Windows

1. Abrir Panel de Control -> Centro de redes y recursos compartidos -> Cambiar configuración del adaptador.
2. Click derecho en el adaptador de red activo -> Propiedades.
3. Seleccionar "Protocolo de Internet versión 4 (TCP/IPv4)" -> Propiedades.
4. Añadir `127.0.0.1` como servidor DNS adicional (o primario).

### Alternativa universal: /etc/hosts

Si no se quiere o no se puede configurar el DNS del SO, se pueden añadir entradas manuales. La desventaja es que los subdominios dinámicos de LocalStack (como `s3.us-east-1.local-aws.com`) no funcionan automáticamente y hay que añadir cada subdominio a mano.

En Linux y macOS (`/etc/hosts`), en Windows (`C:\Windows\System32\drivers\etc\hosts`):

```
127.0.0.1 opensearch.local-env.com
127.0.0.1 opensearch-dashboards.local-env.com
127.0.0.1 activemq-dashboards.local-env.com
127.0.0.1 kafka-dashboards.local-env.com
127.0.0.1 kafka.local-env.com
127.0.0.1 local-aws.com
127.0.0.1 s3.local-aws.com
```

---

## 4. Instalar la CA de minica

minica genera una CA raíz propia en el primer arranque. Esta CA firma todos los certificados del entorno. Hay que instalarla en el SO (y en la JVM si se usa Java) para evitar errores de certificado no confiado.

La CA se encuentra en: `services/minica/app/certs/ca_cert.pem`

### Linux (Ubuntu / Debian)

```bash
sudo cp services/minica/app/certs/ca_cert.pem \
  /usr/local/share/ca-certificates/local-env-ca.crt

sudo update-ca-certificates
```

Verificar:

```bash
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt \
  services/minica/app/certs/live/local-env.com/cert.pem
```

### macOS

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain \
  services/minica/app/certs/ca_cert.pem
```

Verificar abriendo https://opensearch.local-env.com en Safari o Chrome (debe mostrar el candado sin advertencias).

### Windows (PowerShell como administrador)

```powershell
certutil -addstore -f "ROOT" services\minica\app\certs\ca_cert.pem
```

Reiniciar el navegador después de instalar.

### JVM (cualquier SO)

La JVM mantiene su propio almacén de confianza independiente del SO. Hay que importar la CA con `keytool`:

```bash
ca_cert_path="./services/minica/app/certs/ca_cert.pem"

# Opción 1: truststore del JDK (Java 9+, requiere contrasena del cacerts, por defecto "changeit")
sudo keytool -import -trustcacerts \
  -file "$ca_cert_path" \
  -alias local-env-ca-cert \
  -cacerts

# Opción 2: ruta explícita al cacerts
sudo keytool -import -trustcacerts \
  -file "$ca_cert_path" \
  -alias local-env-ca-cert \
  -keystore "$JAVA_HOME/lib/security/cacerts"
```

Verificar que la CA se importó:

```bash
keytool -list -cacerts | grep local-env
```

---

## 5. Verificar que todo funciona

### DNS

```bash
nslookup opensearch.local-env.com 127.0.0.1
nslookup s3.local-aws.com 127.0.0.1
```

Deben devolver `127.0.0.1`.

### HTTPS y servicios web

```bash
# OpenSearch API
curl -u admin:myPassword123! https://opensearch.local-env.com

# LocalStack S3
curl https://s3.local-aws.com

# Verificacion de certificado (debe decir "verification OK" si la CA esta instalada)
openssl s_client -connect opensearch.local-env.com:443 \
  -CAfile services/minica/app/certs/ca_cert.pem < /dev/null
```

### Interfaces web

| Servicio | URL |
|---------|-----|
| Dashboard local-env | https://dashboard.local-env.com |
| OpenSearch Dashboards | https://opensearch-dashboards.local-env.com |
| Consola ActiveMQ | https://activemq-dashboards.local-env.com |
| Kafdrop (Kafka UI) | https://kafka-dashboards.local-env.com |
| LocalStack health | https://localstack.local-aws.com/_localstack/health |

Credenciales por defecto de ActiveMQ: `admin` / `admin`.

### Kafka

```bash
# Verificar que el DNS resuelve y el puerto responde
nslookup kafka.local-env.com 127.0.0.1
# Debería devolver 10.0.1.2 (IP interna de nginx)
```

Para un test real se necesita un cliente Kafka con TLS configurado (ver sección 6).

### nginx

```bash
# Verificar que la config de nginx no tiene errores
docker compose exec nginx nginx -t
```

---

## 6. Keystores y truststores para proyectos Java

Tras el primer arranque, minica genera en `services/minica/app/certs/stores/` los almacenes listos para usar:

| Fichero | Contenido | Uso |
|--------|-----------|-----|
| `ca-cert.ts` | Truststore con la CA raíz | Kafka, ActiveMQ (lado cliente) |
| `local-env.com.ks` | Keystore con cert de local-env.com | ActiveMQ (si se necesita mTLS) |
| `local-env.com.p12` | Mismo cert en formato PKCS12 | Alternativa a .ks |
| `local-aws.com.ks` | Keystore con cert de local-aws.com | LocalStack TLS |
| `local-aws.com.p12` | Mismo en PKCS12 | Alternativa a .ks |

La contraseña de todos los stores es `password`.

### Proyecto Java con Kafka

```bash
cp services/minica/app/certs/stores/ca-cert.ts \
  <PROYECTO>/src/main/resources/ssl/kafka-local-env.ts
```

Configuración Spring Boot (`application-local.yml`):

```yaml
spring:
  kafka:
    bootstrap-servers: kafka.local-env.com:9092
    security:
      protocol: SSL
    ssl:
      trust-store-location: classpath:ssl/kafka-local-env.ts
      trust-store-password: password
      trust-store-type: JKS
```

### Proyecto Java con ActiveMQ

```bash
cp services/minica/app/certs/stores/local-env.com.ks \
  <PROYECTO>/src/main/resources/ssl/activemq-local-env.ks

cp services/minica/app/certs/stores/ca-cert.ts \
  <PROYECTO>/src/main/resources/ssl/activemq-local-env.ts
```

ActiveMQ escucha en `localhost:61617` (TLS). Configuración Spring Boot:

```yaml
spring:
  activemq:
    broker-url: ssl://localhost:61617
    user: admin
    password: admin
```

Y en el bean de conexión, configurar el `SslContext` apuntando al keystore y truststore copiados.

---

## 7. Selección de servicios

La selección de servicios se hace mediante `config.mk`. Contiene cuatro variables, una por servicio opcional:

```make
# Selección de servicios opcionales
# Cambiar a false para deshabilitar un servicio
ENABLE_OPENSEARCH ?= true
ENABLE_LOCALSTACK ?= true
ENABLE_ACTIVEMQ   ?= true
ENABLE_KAFKA      ?= true
```

Para deshabilitar un servicio, cambiar su valor a `false` y ejecutar `make up` de nuevo. Los servicios core (`bind`, `minica`, `nginx`) no aparecen aquí porque arrancan siempre y no son opcionales.

Ejemplo: entorno solo con OpenSearch y LocalStack, sin Kafka ni ActiveMQ:

```make
ENABLE_OPENSEARCH ?= true
ENABLE_LOCALSTACK ?= true
ENABLE_ACTIVEMQ   ?= false
ENABLE_KAFKA      ?= false
```

El `Makefile` lee `config.mk` y se encarga de:

1. Construir los `--profile` de Docker Compose correspondientes.
2. Copiar a `services/nginx/etc/nginx/conf.d/http/services/` y `stream/services/` solo los ficheros `.conf` de los servicios habilitados, antes de lanzar los contenedores.

Esto garantiza que nginx no intente resolver upstreams de servicios que no están corriendo.

---

## 8. Comandos frecuentes

| Acción | Comando |
|--------|---------|
| Arrancar el entorno | `make up` |
| Parar el entorno | `make down` |
| Reiniciar el entorno | `make restart` |
| Ver estado de los contenedores | `make status` |
| Ver logs en tiempo real | `make logs` |
| Ver logs de un servicio | `docker compose logs -f nginx` |
| Sincronizar configs nginx y arrancar | `make up` (lo hace automáticamente) |
| Recargar config nginx en caliente | `make nginx-reload` |
| Verificar config nginx | `docker compose exec nginx nginx -t` |
| Parar y borrar datos (fresh start) | `docker compose down -v` |
| Regenerar certificados | ver sección de operaciones |

`make down` para todos los servicios independientemente de lo que haya en `config.mk` en ese momento, de modo que no queden contenedores huérfanos si se cambia la selección de servicios entre arranques.

`make nginx-reload` es útil cuando se añaden ficheros `.conf` de apps externas en los directorios de extensión (`http/` o `stream/`) sin necesidad de reiniciar los contenedores.
