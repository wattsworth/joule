#!/bin/bash

CA_CRT=ca.joule.crt
CA_KEY=ca.joule.key

set -e

CLIENT_KEY=$1.joule.key
CLIENT_CRT=$1.joule.crt

echo "#1 create a private key"
openssl genrsa -out $CLIENT_KEY 2048

#2 create CSR config

cat > csr.conf <<EOF
[ req ]
default_bits = 2048
default_keyfile = $CLIENT_KEY
default_md = sha256
prompt = no
utf8 = yes
distinguished_name = my_req_distinguished_name

[ my_req_distinguished_name ]
C = US
ST = MD
L = usna
O  = wattsworth
CN = $1.joule
EOF

echo "#2 create CSR"
openssl req -new -key $CLIENT_KEY -out client.csr -config csr.conf

echo "#3 create signed certificate"
openssl x509 -req -in client.csr -CA ca.joule.crt -CAkey ca.joule.key -CAcreateserial -out $CLIENT_CRT

echo "#4 cleaning up"
rm client.csr
rm csr.conf