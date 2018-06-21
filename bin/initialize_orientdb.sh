#!/bin/sh

PARENT_DIR=$(dirname $(cd "$(dirname "$0")"; pwd))
ORIENTDB_DIR="$PARENT_DIR/orientdb/"

ORIENTDB_VERSION=${1:-"2.2.30"}
ORIENTDB_PACKAGE="orientdb-${ORIENTDB_VERSION}"
ORIENTDB_LAUNCHER="${ORIENTDB_DIR}/bin/server.sh"

echo "=== Initializing CI environment ==="

cd "$PARENT_DIR"

if [ ! -d "$ORIENTDB_DIR" ]; then
    mkdir $ORIENTDB_DIR
else
    echo "!!! Directory $ORIENTDB_DIR exists !!!"
fi
# Download and extract OrientDB
echo "--- Downloading OrientDB v${ORIENTDB_VERSION} ---"
wget -O ${ORIENTDB_DIR}${ORIENTDB_PACKAGE}.tar.gz "http://orientdb.com/download.php?file=orientdb-community-${ORIENTDB_VERSION}.tar.gz&os=linux"
tar -C ${ORIENTDB_DIR} --strip-components=1 -zxvf $ORIENTDB_DIR${ORIENTDB_PACKAGE}.tar.gz
cp orientdb-server-config.xml ${ORIENTDB_DIR}config/

# Start OrientDB in background.
echo "--- Starting an instance of OrientDB ---"
sh -C ${ORIENTDB_LAUNCHER} &

# Wait a bit for OrientDB to finish the initialization phase.
sleep 5
printf "\n=== The CI environment has been initialized ===\n"
