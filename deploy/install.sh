#!/usr/bin/env bash
# Instalación de nftguard en Debian. Pensado para un equipo de pruebas: idempotente
# dentro de lo razonable, pero no es un gestor de paquetes, se asume Debian 12+.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este script debe ejecutarse como root." >&2
  exit 1
fi

NFTGUARD_HOME=/opt/nftguard
NFTGUARD_ETC=/etc/nftguard
NFTGUARD_VAR=/var/lib/nftguard
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Instalando dependencias del sistema"
apt-get update
apt-get install -y --no-install-recommends \
  nftables \
  suricata \
  wireguard-tools \
  python3 \
  python3-venv \
  python3-pip \
  openssl \
  rsync

echo "==> Habilitando IP forwarding"
cat >/etc/sysctl.d/99-nftguard.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
sysctl --system >/dev/null

echo "==> Deshabilitando el servicio nftables de Debian (lo gestiona nftguard)"
systemctl disable --now nftables.service || true

echo "==> Deshabilitando el suricata.service por defecto (lo gestiona nftguard, en modo NFQUEUE)"
systemctl disable --now suricata.service || true

echo "==> Creando usuario de sistema nftguard"
id -u nftguard >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin nftguard

echo "==> Dando a nftguard acceso al grupo 'suricata' (config/reglas/logs compartidos)"
usermod -aG suricata nftguard

echo "==> Copiando backend a ${NFTGUARD_HOME}"
mkdir -p "${NFTGUARD_HOME}"
rsync -a --delete --exclude ".venv" --exclude "__pycache__" "${SRC_DIR}/backend" "${NFTGUARD_HOME}/"

if [[ -d "${SRC_DIR}/frontend/dist" ]]; then
  echo "==> Copiando frontend ya compilado (frontend/dist)"
  mkdir -p "${NFTGUARD_HOME}/frontend"
  rsync -a --delete "${SRC_DIR}/frontend/dist" "${NFTGUARD_HOME}/frontend/"
else
  echo "    AVISO: no existe frontend/dist. Compílalo antes de instalar:"
  echo "      cd frontend && npm install && npm run build"
  echo "    Este equipo no necesita Node.js: el build se hace en tu máquina de"
  echo "    desarrollo y solo se copia el resultado estático."
fi

mkdir -p "${NFTGUARD_ETC}" "${NFTGUARD_VAR}"
chown -R nftguard:nftguard "${NFTGUARD_HOME}" "${NFTGUARD_ETC}" "${NFTGUARD_VAR}"

echo "==> Preparando directorios de Suricata compartidos entre nftguard y suricata"
mkdir -p /etc/suricata /var/lib/suricata/rules /var/log/suricata
touch /var/lib/suricata/rules/suricata.rules
# Grupo compartido 'suricata': nftguard escribe config/reglas y lee eve.json; el
# propio proceso suricata (run-as user: suricata) necesita leer/escribir lo mismo.
# El bit setgid hace que los ficheros nuevos (eve.json, reglas descargadas) hereden
# el grupo, para que nftguard pueda seguir leyéndolos sin tocar permisos a mano.
chgrp -R suricata /etc/suricata /var/lib/suricata/rules /var/log/suricata
chmod -R g+rwX /etc/suricata /var/lib/suricata/rules /var/log/suricata
chmod g+s /etc/suricata /var/lib/suricata/rules /var/log/suricata

mkdir -p /etc/systemd/system/suricata.service.d
chown nftguard:nftguard /etc/systemd/system/suricata.service.d
chmod 750 /etc/systemd/system/suricata.service.d

echo "==> Preparando /etc/wireguard para nftguard"
mkdir -p /etc/wireguard
chown nftguard:nftguard /etc/wireguard
chmod 700 /etc/wireguard

echo "==> Permitiendo a nftguard arrancar/parar/recargar justo suricata.service y wg-quick@wg0 (polkit)"
mkdir -p /etc/polkit-1/rules.d
cp "${SRC_DIR}/deploy/polkit/60-nftguard-suricata.rules" /etc/polkit-1/rules.d/
cp "${SRC_DIR}/deploy/polkit/61-nftguard-wireguard.rules" /etc/polkit-1/rules.d/
systemctl restart polkit 2>/dev/null || true

echo "==> Deshabilitando wg-quick@wg0 por defecto (lo gestiona nftguard)"
systemctl disable --now wg-quick@wg0.service 2>/dev/null || true

if [[ ! -f "${NFTGUARD_ETC}/backend.env" ]]; then
  echo "==> Generando ${NFTGUARD_ETC}/backend.env"
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat >"${NFTGUARD_ETC}/backend.env" <<EOF
NFTGUARD_SECRET_KEY=${SECRET}
NFTGUARD_DB_PATH=${NFTGUARD_VAR}/nftguard.db
NFTGUARD_MODE=gateway
NFTGUARD_WAN_IFACE=eth0
NFTGUARD_LAN_IFACE=eth1
NFTGUARD_LAN_NETWORK=192.168.10.0/24
NFTGUARD_WEB_UI_PORT=8443
NFTGUARD_RULESET_DIR=${NFTGUARD_ETC}
NFTGUARD_RULESET_PATH=${NFTGUARD_ETC}/ruleset.nft
NFTGUARD_RULESET_BACKUP_PATH=${NFTGUARD_ETC}/ruleset.nft.bak
EOF
  chmod 600 "${NFTGUARD_ETC}/backend.env"
  chown nftguard:nftguard "${NFTGUARD_ETC}/backend.env"
  echo "    Revisa las interfaces WAN/LAN en ese fichero antes de arrancar el servicio."
fi

if [[ ! -f "${NFTGUARD_ETC}/tls.crt" ]]; then
  echo "==> Generando certificado TLS autofirmado para la UI (válido 10 años)"
  echo "    Sustitúyelo por uno real (p. ej. Let's Encrypt) si expones esto fuera de la LAN."
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -keyout "${NFTGUARD_ETC}/tls.key" -out "${NFTGUARD_ETC}/tls.crt" \
    -subj "/CN=nftguard"
  chmod 600 "${NFTGUARD_ETC}/tls.key"
  chown nftguard:nftguard "${NFTGUARD_ETC}/tls.key" "${NFTGUARD_ETC}/tls.crt"
fi

echo "==> Creando virtualenv e instalando dependencias Python"
sudo -u nftguard python3 -m venv "${NFTGUARD_HOME}/backend/.venv"
sudo -u nftguard "${NFTGUARD_HOME}/backend/.venv/bin/pip" install --upgrade pip
sudo -u nftguard "${NFTGUARD_HOME}/backend/.venv/bin/pip" install -r "${NFTGUARD_HOME}/backend/requirements.txt"

echo "==> Instalando unidad systemd"
cp "${SRC_DIR}/deploy/systemd/nftguard-backend.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now nftguard-backend.service

echo "==> Listo. Backend escuchando en :8443 (solo accesible desde la LAN definida)."
echo "    Completa el alta del usuario admin en https://<ip-lan>:8443/"
