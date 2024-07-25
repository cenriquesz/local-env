#!/bin/sh

# Definicion de directorios
NGINX_CONF_DIR="/etc/nginx/conf.d/http"

CERTS_DIR="/app/certs"
CA_CERT_PATH="$CERTS_DIR/ca_cert.pem"
CA_KEY_PATH="$CERTS_DIR/ca_key.pem"


# Extraemos los dominios
domains=""
for file in $NGINX_CONF_DIR/*.conf; do
  domain=$(basename $file .conf)
  if [ $domain != $LOCALSTACK_HOST ]; then
    domains="$domains $domain"
  fi
done


# Filtramos los dominios
unique_domains=$(echo $domains | tr ' ' '\n' | sort -u | tr '\n' ' ')


# Preparamos el directorio para ubicar los certificados
live_certs_dir="$CERTS_DIR/live"
mkdir -p $live_certs_dir
cd $live_certs_dir


# Generamos los certificados para los dominios
if [ -n "$unique_domains" ]; then
  for domain in $unique_domains; do
    echo "Generating self-signed certificate for $domain"
    minica -ca-alg rsa -ca-cert $CA_CERT_PATH -ca-key $CA_KEY_PATH -domains "$domain,*.$domain"
  done
fi


# Generamos los certificados para localstack
aws_domain="$LOCALSTACK_HOST"
aws_domain_list="
  $aws_domain
  *.$aws_domain
  *.us-east-1.$aws_domain
  *.s3.us-east-1.$aws_domain
  *.us-east-1.opensearch.$aws_domain
"
aws_domains=$(echo "$aws_domain_list" | sed 's/^ *//' | tr '\n' ',' | sed 's/^,*//;s/,*$//')
minica -ca-alg rsa -ca-cert $CA_CERT_PATH -ca-key $CA_KEY_PATH -domains $aws_domains

cd --

tail -f /dev/null
