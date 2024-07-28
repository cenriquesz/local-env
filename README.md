# Local Environment with Docker for Development

## Getting Started

#TODO

## Troubleshooting

### Configure CA Certificates in Java

Ensure the `JAVA_HOME` variable is defined:

```sh
echo $JAVA_HOME
```

If it is empty, set the variable:

```sh
# For example, for Java 17 on Ubuntu
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
```

Next, define the path to the CA certificate:

```sh
ca_cert_path="./services/minica/app/certs/ca_cert.pem"
```

To import into Java's default CA keystore, use the `-cacerts` option:

```sh
keytool -import -trustcacerts -file $ca_cert_path -alias my-ca-cert -cacerts
```

To specify a custom path for the CA certificates, use:

```sh
ca_certs_path="$JAVA_HOME/lib/security/cacerts"
keytool -import -trustcacerts -file $ca_cert_path -alias my-ca-cert -keystore $ca_certs_path
```

### Configure SSL for ActiveMQ in Java Projects

Copy keystore to the project's resources ssl directory
```bash
ks_path="./local/env/services/minica/app/certs/stores/local-env.com.ks"
ssl_ks_path="./src/main/resources/ssl/activemq-local-env.ks"
cp $ks_path $ssl_ks_path
```

Copy truststore to the project's resources ssl directory
```bash
ts_path="./local/env/services/minica/app/certs/stores/ca-cert.ts"
ssl_ts_path="./src/main/resources/ssl/activemq-local-env.ts"
cp $ts_path $ssl_ts_path
```

### Configure SSL for Kafka in Java Projects

Copy truststore to the project's resources ssl directory
```bash
ts_path="./local/env/services/minica/app/certs/stores/ca-cert.ts"
ssl_ts_path="./src/main/resources/ssl/kafka-local-env.ts"
cp $ts_path $ssl_ts_path
```
