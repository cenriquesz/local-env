# Utiliza la imagen oficial de Go como base
FROM golang:1.19-alpine

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Descarga e instala Minica
RUN go install github.com/jsha/minica@latest

# Crea un punto de montaje para compartir con el host
VOLUME ["/app"]

# Define el script de entrada como el entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
