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
stores_dir="$CERTS_DIR/stores"
mkdir -p $live_certs_dir
mkdir -p $stores_dir

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

for dir in * ; do
  if [[ -f "$dir/cert.pem" && -f "$dir/key.pem" && ! -f "$stores_dir/$dir.p12" ]]; then
    # Generamos el cert.p12
    openssl pkcs12 -export -in "$dir/cert.pem" -inkey "$dir/key.pem" -out "$stores_dir/$dir.p12" -name $dir -password pass:password

    # Generamos el keystore
    keytool -importkeystore -deststorepass password -destkeystore "$stores_dir/$dir.ks" -srckeystore "$stores_dir/$dir.p12" -srcstoretype PKCS12 -srcstorepass password -alias $dir
    keytool -import -trustcacerts -alias ca-cert -file $CA_CERT_PATH -keystore "$stores_dir/$dir.ks" -storepass password -noprompt
  fi
done

cd --

# Generamos el truststore
if [[ ! -f "$stores_dir/ca-cert.ts" ]]; then
  keytool -import -trustcacerts -alias ca-cert -file $CA_CERT_PATH -keystore "$stores_dir/ca-cert.ts" -storepass password -noprompt
fi

chown -R 1000:1000 $CERTS_DIR

tail -f /dev/null
