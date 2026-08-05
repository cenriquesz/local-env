FROM alpine:latest

# Instalar bind
RUN apk add --no-cache bind bind-tools

# Crear directorios necesarios y copiar archivos de configuración
RUN mkdir -p /etc/bind/zones

# Exponer los puertos necesarios
EXPOSE 53/udp 53/tcp

# Comando para iniciar bind
CMD ["named", "-g", "-c", "/etc/bind/named.conf"]
