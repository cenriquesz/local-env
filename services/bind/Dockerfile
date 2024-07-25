FROM alpine:latest

# Instalar bind
RUN apk add --no-cache bind

# Crear directorios necesarios y copiar archivos de configuración
RUN mkdir -p /etc/bind/zones
COPY named.conf /etc/bind/named.conf
COPY zones/* /etc/bind/zones/

# Exponer los puertos necesarios
EXPOSE 53/udp 53/tcp

# Comando para iniciar bind
CMD ["named", "-g", "-c", "/etc/bind/named.conf"]
