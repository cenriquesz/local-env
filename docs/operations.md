# Operaciones de local-env

Guía de operaciones del día a día: gestión de certificados, DNS, logs, diagnóstico y mantenimiento.

---

## 1. Gestión de certificados

### Dónde están los ficheros

```
services/minica/app/certs/
├── ca_cert.pem          # CA raíz (se mantiene entre reinicios)
├── ca_key.pem           # Clave privada de la CA (no compartir)
├── live/
│   ├── local-env.com/
│   │   ├── cert.pem     # Certificado del dominio
│   │   └── key.pem      # Clave privada del dominio
│   └── local-aws.com/
│       ├── cert.pem
│       └── key.pem
└── stores/
    ├── ca-cert.ts           # Truststore JVM con la CA raíz
    ├── local-env.com.ks     # Keystore JVM para local-env.com
    ├── local-env.com.p12    # Mismo en PKCS12
    ├── local-aws.com.ks     # Keystore JVM para local-aws.com
    └── local-aws.com.p12    # Mismo en PKCS12
```

### Ciclo de vida

- minica genera la CA (`ca_cert.pem` y `ca_key.pem`) la primera vez que arranca, si no existen.
- Por cada dominio que aparezca en la configuración de nginx, minica genera un certificado en `live/<dominio>/`. Solo genera si el directorio no existe todavía.
- Los stores de Java se regeneran cada vez que minica arranca.
- La CA persiste entre reinicios porque el volumen de minica monta `/app` desde el host. Cambiar la CA implica reinstalarla en el SO y en la JVM de todos los proyectos que la usen.

### Renovar certificados de dominio sin cambiar la CA

Útil cuando los certificados están a punto de caducar o se han corrompido, pero no se quiere perder la confianza en la CA ya instalada.

```bash
rm -rf services/minica/app/certs/live
docker compose restart minica
docker compose exec nginx nginx -s reload
```

Verificar que los nuevos certificados se generaron:

```bash
ls -la services/minica/app/certs/live/
openssl x509 -in services/minica/app/certs/live/local-env.com/cert.pem \
  -noout -dates
```

### Regenerar todo (CA incluida)

Solo necesario si la CA se ha comprometido o se quiere empezar desde cero. Después hay que reinstalar la CA en el SO y en la JVM de todos los proyectos.

```bash
docker compose stop minica
rm -rf services/minica/app/certs/live services/minica/app/certs/stores \
       services/minica/app/certs/ca_cert.pem services/minica/app/certs/ca_key.pem
docker compose start minica
docker compose exec nginx nginx -s reload
```

Tras esto, seguir los pasos de instalación de la CA del documento de deployment.

### Añadir un nuevo dominio

1. Crear el fichero de configuración nginx para el nuevo dominio:

```bash
# Ejemplo: nuevo-dominio.local-env.com
cat > services/nginx/etc/nginx/conf.d/http/nuevo-dominio.conf << 'EOF'
server {
    listen 443 ssl;
    server_name nuevo-dominio.local-env.com;

    ssl_certificate     /etc/nginx/certs/live/local-env.com/cert.pem;
    ssl_certificate_key /etc/nginx/certs/live/local-env.com/key.pem;

    location / {
        proxy_pass http://nombre-servicio:puerto;
        proxy_set_header Host $host;
    }
}
EOF
```

2. Reiniciar minica para que genere el certificado del nuevo dominio (si es un subdominio de local-env.com ya está cubierto por el wildcard; si es un dominio nuevo, minica lo añadirá):

```bash
docker compose restart minica
```

3. Recargar nginx:

```bash
docker compose exec nginx nginx -s reload
```

4. Verificar:

```bash
curl -v https://nuevo-dominio.local-env.com
```

---

## 2. Actualización de zonas DNS

BIND9 gestiona las zonas `local-env.com` y `local-aws.com`. Los ficheros de zona se encuentran en `services/bind/`.

### Estructura de ficheros

```
services/bind/
├── named.conf           # Configuración principal de BIND
└── zones/
    ├── local-env.com.zone
    └── local-aws.com.zone
```

### Editar una zona

Abrir el fichero de zona correspondiente y añadir o modificar los registros. Ejemplo de registro A:

```
nuevo-host    IN  A  10.0.1.2
```

Incrementar el serial en la sección SOA para que BIND detecte el cambio:

```
@   IN  SOA ns1.local-env.com. admin.local-env.com. (
            2024010102 ; serial - incrementar este valor
            ...
        )
```

### Aplicar los cambios

BIND en este entorno no tiene `rndc` configurado, así que hay que reiniciar el contenedor:

```bash
docker compose restart bind
```

Verificar que el nuevo registro resuelve:

```bash
nslookup nuevo-host.local-env.com 127.0.0.1
```

---

## 3. Logs y diagnóstico

### Ver logs por servicio

```bash
# Todos los servicios en tiempo real
docker compose logs -f

# Un servicio concreto
docker compose logs -f nginx
docker compose logs -f localstack
docker compose logs -f bind
docker compose logs -f minica

# Las últimas N líneas
docker compose logs --tail 100 opensearch
```

### Estado de los contenedores

```bash
# Estado y salud de todos los contenedores
docker compose ps

# Inspeccionar un contenedor concreto
docker inspect local-env-nginx-1
```

### Comandos de diagnóstico de red

```bash
# Verificar que el DNS del contenedor bind responde
nslookup opensearch.local-env.com 127.0.0.1
nslookup s3.local-aws.com 127.0.0.1

# Verificar conectividad HTTPS (necesita CA instalada o usar -k para omitir)
curl -v https://opensearch.local-env.com
curl -k -v https://opensearch.local-env.com  # omite verificacion de cert

# Verificar certificado directamente
openssl s_client -connect opensearch.local-env.com:443 \
  -CAfile services/minica/app/certs/ca_cert.pem < /dev/null

# Ver datos del certificado que sirve un dominio
openssl s_client -connect opensearch.local-env.com:443 < /dev/null 2>/dev/null \
  | openssl x509 -noout -text

# Verificar que nginx carga la config sin errores
docker compose exec nginx nginx -t

# Ver conexiones activas en nginx
docker compose exec nginx nginx -s status 2>/dev/null || true
```

### Diagnóstico de LocalStack

```bash
# Estado general
curl https://localstack.local-aws.com/_localstack/health | python3 -m json.tool
# El dashboard (https://dashboard.local-env.com) muestra el estado de los servicios AWS activos de forma visual

# Listar buckets S3
aws --endpoint-url https://s3.local-aws.com s3 ls

# Logs de LocalStack con nivel de detalle alto
docker compose logs -f localstack
```

### Diagnóstico de OpenSearch

```bash
# Estado del cluster
curl -u admin:myPassword123! https://opensearch.local-env.com/_cluster/health | python3 -m json.tool

# Listar índices
curl -u admin:myPassword123! https://opensearch.local-env.com/_cat/indices?v
```

---

## 4. Problemas conocidos y soluciones

### Problema 1: Puerto 53 ocupado en Ubuntu

**Síntoma:** el contenedor `bind` no arranca o falla con "address already in use" en el puerto 53.

**Causa:** systemd-resolved ocupa el puerto 53 por defecto en Ubuntu 18.04 y posteriores.

**Solución:**

```bash
# Opción A: deshabilitar el stub listener de systemd-resolved
sudo bash -c 'echo -e "[Resolve]\nDNSStubListener=no" \
  >> /etc/systemd/resolved.conf'
sudo systemctl restart systemd-resolved

# Opción B: deshabilitar completamente systemd-resolved
sudo systemctl disable --now systemd-resolved
```

Después de cualquiera de las dos opciones, volver a arrancar bind:

```bash
docker compose up -d bind
```

---

### Problema 2: Certificados no confiados en el navegador

**Síntoma:** Chrome o Firefox muestran "Tu conexión no es privada" aunque la CA esté instalada en el SO.

**Causa:** el navegador tiene su propio caché de HSTS o no ha recargado el almacén de confianza del SO.

**Solución:**

1. Cerrar completamente el navegador (todas las ventanas) y volver a abrirlo.
2. Si persiste en Chrome, ir a `chrome://net-internals/#hsts`, introducir el dominio en "Delete domain security policies" y pulsar Delete.
3. Si persiste, verificar que la CA se instaló correctamente en el SO (ver sección de instalación de CA en el documento de deployment) y repetir el proceso.

---

### Problema 3: java.security.cert.CertPathValidatorException

**Síntoma:** una aplicación Java lanza una excepción al conectar a cualquier servicio HTTPS del entorno.

**Causa:** la JVM no tiene la CA de minica en su truststore (`cacerts`).

**Solución:**

```bash
sudo keytool -import -trustcacerts \
  -file services/minica/app/certs/ca_cert.pem \
  -alias local-env-ca-cert \
  -cacerts
# Contrasena por defecto del cacerts: changeit
```

Verificar que se importó:

```bash
keytool -list -cacerts | grep local-env
```

Si la aplicación usa un truststore propio en lugar del del JDK, importar la CA en ese truststore específico con la opción `-keystore <ruta>`.

---

### Problema 4: LocalStack - "token required" o funciones no disponibles

**Síntoma:** LocalStack arranca pero al usarlo devuelve errores de autenticación o ciertas funciones (como OpenSearch) no están disponibles.

**Causa:** el `LOCALSTACK_AUTH_TOKEN` no está configurado o no es válido.

**Solución:**

1. Registrarse en [localstack.cloud](https://localstack.cloud) (gratuito).
2. Copiar el token desde el dashboard de LocalStack.
3. Editar `.env` y poner el token real en `LOCALSTACK_AUTH_TOKEN`.
4. Reiniciar LocalStack:

```bash
docker compose restart localstack
```

---

### Problema 5: nginx arranca con "host not found in upstream"

**Síntoma:** nginx no arranca o aparece en estado `restarting`. Los logs muestran `host not found in upstream "nombre-servicio"`.

**Causa:** la configuración de nginx referencia un servicio que no está corriendo en la red Docker.

**Solución:**

Opción A - arrancar el servicio faltante:

```bash
docker compose ps  # identificar qué servicio falta
docker compose up -d <nombre-servicio>
docker compose exec nginx nginx -s reload
```

Opción B - deshabilitar el .conf de nginx para ese servicio:

```bash
# Comentar o eliminar el .conf del servicio no usado
# Por ejemplo, si no se usa activemq-dashboards:
docker compose exec nginx nginx -t  # primero verificar qué fichero falla
# Editar el .conf correspondiente para comentar el server block
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
```

---

### Problema 6: minica no genera certs para un dominio nuevo

**Síntoma:** nginx carga el nuevo .conf pero no puede leer el certificado; los logs de nginx muestran que el fichero de cert no existe.

**Causa:** minica solo genera certificados al arrancar. Si el .conf de nginx se añadió después del último arranque de minica, el directorio del dominio no existe.

**Solución:**

```bash
docker compose restart minica
docker compose exec nginx nginx -s reload
```

---

### Problema 7: Kafka - connection refused en kafka.local-env.com:9092

**Síntoma:** un cliente Kafka no puede conectar a `kafka.local-env.com:9092`. El error es "Connection refused" o "Name or service not known".

**Causa posible A:** el DNS del host no resuelve `kafka.local-env.com`.

```bash
# Verificar:
nslookup kafka.local-env.com 127.0.0.1
```

Si no resuelve, revisar la configuración DNS del SO (ver sección 3 del documento de deployment) y verificar que bind está corriendo:

```bash
docker compose ps bind
```

**Causa posible B:** bind está corriendo pero el SO no le consulta para ese dominio.

Revisar la configuración de systemd-resolved (Linux) o los ficheros en `/etc/resolver/` (macOS).

**Causa posible C:** el contenedor de Kafka no está corriendo.

```bash
docker compose ps kafka
docker compose logs kafka
```

---

### Problema 8: Error "driver failed programming" al arrancar

**Síntoma:** `docker compose up` falla con un error relacionado con la red, del tipo "driver failed programming external connectivity" o "network already exists".

**Causa:** la subred `local-env-net` (10.0.1.0/24) existe de un arranque anterior que no terminó limpiamente.

**Solución:**

```bash
docker network rm local-env-net
docker compose up -d
```

Si el comando `docker network rm` falla porque hay contenedores conectados:

```bash
docker compose down
docker network rm local-env-net
docker compose up -d
```

---

### Problema 9: OpenSearch - error 401 / Authentication error

**Síntoma:** las peticiones a OpenSearch devuelven HTTP 401 o los logs muestran "Authentication finally failed".

**Causa:** la contraseña en `OPENSEARCH_PASSWORD` no cumple los requisitos de seguridad de OpenSearch (mínimo 8 caracteres, con mayúsculas, minúsculas, números y símbolos).

**Solución:**

1. Editar `.env` y cambiar `OPENSEARCH_PASSWORD` a un valor que cumpla los requisitos, por ejemplo `Admin1234!`.
2. Hacer un fresh start para que OpenSearch inicialice con la nueva contraseña:

```bash
docker compose down -v
docker compose up -d
```

Nota: `-v` borra los volúmenes, incluidos los datos de OpenSearch. No usar en producción o si se tienen datos que conservar.

---

## 5. Mantenimiento del entorno

### Limpiar datos sin borrar imágenes

Elimina todos los datos persistidos (índices de OpenSearch, tópicos de Kafka, colas de ActiveMQ, recursos de LocalStack) pero mantiene las imágenes Docker descargadas.

```bash
docker compose down -v
docker compose up -d
```

### Actualizar imágenes Docker

```bash
# Descargar las versiones más recientes de todas las imágenes
docker compose pull

# Reiniciar con las nuevas imágenes
docker compose down
docker compose up -d
```

### Fresh start completo

Borra datos, imágenes descargadas y certificados generados. El siguiente arranque descargará las imágenes de nuevo y regenerará todos los certificados (incluyendo la CA).

Recordar reinstalar la CA en el SO y en la JVM después de este proceso.

```bash
docker compose down -v --rmi all
rm -rf services/minica/app/certs/live \
       services/minica/app/certs/stores \
       services/minica/app/certs/ca_cert.pem \
       services/minica/app/certs/ca_key.pem
docker compose up -d
```

### Liberar espacio en Docker

```bash
# Eliminar imágenes, contenedores y redes no usados (no toca volúmenes)
docker system prune

# Incluir volúmenes (cuidado: borra datos)
docker system prune --volumes
```

### Verificar uso de recursos

```bash
# Uso de CPU y memoria de los contenedores en tiempo real
docker stats

# Espacio usado por imágenes, contenedores y volúmenes
docker system df
```
