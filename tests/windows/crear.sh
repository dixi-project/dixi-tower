#!/bin/bash
# Crea en AWS una máquina Windows Server 2025 con virtualización anidada (WSL2
# posible) para probar Dixi Tower en Windows. Todo lleva el nombre dixi-tower-windows-prueba.
#
#   AWS_PROFILE=mi-perfil AWS_REGION=us-east-2 tests/windows/crear.sh
#
# Costo aproximado: 0,40 USD por hora (m8i.xlarge con licencia de Windows) hasta
# que se ejecute tests/windows/borrar.sh. El escritorio remoto (3389) y SSH (22)
# quedan abiertos solo para la IP pública de quien lo ejecuta.
set -euo pipefail
: "${AWS_PROFILE:?Define AWS_PROFILE}" "${AWS_REGION:?Define AWS_REGION}"
export AWS_PROFILE AWS_REGION
E="$(cd "$(dirname "$0")" && pwd)/.estado"     # llave, ids y contraseña; fuera de git
mkdir -p "$E" && chmod 700 "$E"
NOMBRE=dixi-tower-windows-prueba
TIPO="${TIPO:-m8i.xlarge}"                     # 8.ª generación Intel: virtualización anidada

VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
AMI=$(aws ssm get-parameter --name /aws/service/ami-windows-latest/Windows_Server-2025-English-Full-Base --query Parameter.Value --output text)
MI_IP="$(curl -s https://checkip.amazonaws.com)/32"
echo "Región $AWS_REGION · VPC $VPC · AMI $AMI · tu IP $MI_IP"

aws ec2 create-key-pair --key-name "$NOMBRE" --query KeyMaterial --output text > "$E/$NOMBRE.pem"
chmod 600 "$E/$NOMBRE.pem"
ssh-keygen -q -t ed25519 -N "" -C "$NOMBRE" -f "$E/id_prueba"

SG=$(aws ec2 create-security-group --group-name "$NOMBRE" --vpc-id "$VPC" \
  --description "Escritorio remoto y SSH para la prueba de Dixi Tower en Windows" --query GroupId --output text)
echo "$SG" > "$E/grupo.txt"
for puerto in 3389 22; do
  aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port "$puerto" --cidr "$MI_IP" >/dev/null
done

ETIQUETAS="[{Key=Name,Value=$NOMBRE},{Key=Proyecto,Value=dixi-tower}]"
aws ec2 run-instances --image-id "$AMI" --instance-type "$TIPO" --count 1 \
  --key-name "$NOMBRE" --security-group-ids "$SG" \
  --cpu-options NestedVirtualization=enabled --metadata-options HttpTokens=required \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":80,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications "ResourceType=instance,Tags=$ETIQUETAS" "ResourceType=volume,Tags=$ETIQUETAS" \
  --query 'Instances[0].InstanceId' --output text > "$E/instancia.txt"
ID=$(cat "$E/instancia.txt")
aws ec2 wait instance-running --instance-ids "$ID"
IP=$(aws ec2 describe-instances --instance-ids "$ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > "$E/ip.txt"
echo "Instancia $ID en $IP. Esperando la contraseña de Administrator (suele tardar unos minutos)…"

umask 077
for _ in $(seq 1 45); do
  P=$(aws ec2 get-password-data --instance-id "$ID" --priv-launch-key "$E/$NOMBRE.pem" \
      --query PasswordData --output text 2>/dev/null | tr -d '\r\n')
  if [ -n "$P" ] && [ "$P" != "None" ]; then printf '%s' "$P" > "$E/contrasena.txt"; break; fi
  sleep 20
done
[ -s "$E/contrasena.txt" ] || { echo "Sin contraseña todavía; vuelve a intentarlo en unos minutos."; exit 1; }

cat <<EOF

Lista. Escritorio remoto: $IP, usuario Administrator.
Copia la contraseña sin mostrarla:   tr -d '\r\n' < "$E/contrasena.txt" | pbcopy

Para entrar por SSH, pega esto en PowerShell (Admin) dentro de la máquina:

if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) { Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null }
Set-Service sshd -StartupType Automatic; Start-Service sshd
\$f = "\$env:ProgramData\\ssh\\administrators_authorized_keys"
Set-Content -Path \$f -Encoding ascii -Value '$(cat "$E/id_prueba.pub")'
icacls \$f /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP'; Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Profile Any
New-ItemProperty -Path 'HKLM:\\SOFTWARE\\OpenSSH' -Name DefaultShell -Value 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe' -PropertyType String -Force | Out-Null

Después:  ssh -i "$E/id_prueba" -o UserKnownHostsFile="$E/known_hosts" Administrator@$IP
Al terminar:  tests/windows/borrar.sh
EOF
