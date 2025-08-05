if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <ip1> <ip2> ..."
  exit 1
fi

# Create a temp config file
CONFIG="openssl.cnf"

# Write base config
cat > "$CONFIG" <<EOF
[req]
default_bits       = 4096
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
CN = $1

[v3_req]
subjectAltName = @alt_names

[alt_names]
EOF

# Add each IP as IP.n in alt_names
count=1
for ip in "$@"; do
  echo "IP.$count = $ip" >> "$CONFIG"
  count=$((count + 1))
done

# Generate the cert and key
openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout server.key -out server.crt \
  -config "$CONFIG" -extensions v3_req
