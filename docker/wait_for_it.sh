#!/bin/sh
set -e
if [ "$KAFKA_ENABLED" = "false" ]
then
 echo "kafka is disabled, exiting.."
 exit
fi
if [ "$REDIS_ENABLED" = "false" ]
then
 echo "redis is disabled, exiting.."
 exit
fi
HOST=$1
PORT=$2
echo "Waiting for ${HOST}..."
until nc -z "${HOST}" "$PORT"; do
  sleep 2
done
echo "${HOST} is up!"
exec "$@"
