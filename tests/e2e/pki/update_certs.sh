#!/bin/bash

# resign all of the certificates

# renew the certificate authority


cat > csr.conf <<EOF
[ req ]
default_bits = 2048
default_md = sha256
prompt = no
utf8 = yes
distinguished_name = my_req_distinguished_name

[ my_req_distinguished_name ]
C = US
ST = MD
L = usna
O  = wattsworth
CN = ca.joule
EOF
openssl req -key ca.joule.key -new -x509 -days 365 -config csr.conf -out ca.joule.crt

# renew the node certificates
for NAME in "node1" "node2"
do

CLIENT_KEY=$NAME.joule.key
CLIENT_CRT=$NAME.joule.crt

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
CN = $NAME.joule
EOF


openssl req -new -key $CLIENT_KEY -out client.csr -config csr.conf

openssl x509 -req -in client.csr -CA ca.joule.crt -CAkey ca.joule.key -CAcreateserial -out $CLIENT_CRT


done

rm *.csr