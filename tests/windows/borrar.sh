#!/bin/bash
# Borra todo lo que creó tests/windows/crear.sh: la instancia (con su disco), el
# grupo de seguridad y la llave. Después de esto la prueba no cuesta nada más.
#
#   AWS_PROFILE=mi-perfil AWS_REGION=us-east-2 tests/windows/borrar.sh
set -uo pipefail
: "${AWS_PROFILE:?Define AWS_PROFILE}" "${AWS_REGION:?Define AWS_REGION}"
export AWS_PROFILE AWS_REGION
E="$(cd "$(dirname "$0")" && pwd)/.estado"
NOMBRE=dixi-tower-windows-prueba

if [ -s "$E/instancia.txt" ]; then
  ID=$(cat "$E/instancia.txt")
  aws ec2 terminate-instances --instance-ids "$ID" --query 'TerminatingInstances[0].CurrentState.Name' --output text
  aws ec2 wait instance-terminated --instance-ids "$ID" && echo "Instancia $ID terminada (su disco se borra con ella)"
fi
[ -s "$E/grupo.txt" ] && aws ec2 delete-security-group --group-id "$(cat "$E/grupo.txt")" >/dev/null && echo "Grupo de seguridad borrado"
aws ec2 delete-key-pair --key-name "$NOMBRE" >/dev/null && echo "Llave borrada en AWS"
rm -rf "$E"

QUEDAN=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=$NOMBRE" \
  "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId' --output text)
DISCOS=$(aws ec2 describe-volumes --filters "Name=tag:Name,Values=$NOMBRE" --query 'Volumes[].VolumeId' --output text)
if [ -z "$QUEDAN$DISCOS" ]; then echo "No queda nada de la prueba en AWS."; else echo "Aún quedan: $QUEDAN $DISCOS"; fi
