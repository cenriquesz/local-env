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

First, define the paths for the ActiveMQ truststore and the CA certificate:

```sh
activemq_ts_path="/path-to-ssl-directory-for-activemq/activemq-truststore.ts"
ca_cert_path="./services/minica/app/certs/ca_cert.pem"
```

Then, import the CA certificate into the ActiveMQ truststore:

```sh
keytool -keystore $activemq_ts_path -alias activemq -import -file $ca_cert_path
```

### Configure SSL for Kafka in Java Projects

First, define the paths for the Kafka truststore and the CA certificate:

```sh
kafka_ts_path="/path-to-ssl-directory-for-kafka/kafka-truststore.ts"
ca_cert_path="./services/minica/app/certs/ca_cert.pem"
```

Then, import the CA certificate into the Kafka truststore:

```sh
keytool -keystore $kafka_ts_path -alias kafka -import -file $ca_cert_path
```
