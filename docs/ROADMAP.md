# Roadmap

## Fase 1 — Núcleo L3/L4
- [x] Estructura del proyecto y arquitectura.
- [x] Backend FastAPI: auth (JWT, primer usuario admin), modelos, BD SQLite.
- [x] Motor de reglas nftables: modelo de reglas, render Jinja2, validación y apply
      atómico con rollback.
- [x] API CRUD de reglas + endpoint de apply.
- [x] Script de instalación Debian (`deploy/install.sh`) + unidades systemd.
- [x] Frontend Vue: setup/login, listado/editor de reglas, NAT/port-forwarding,
      preview y apply con feedback de errores.
- [x] Dashboard básico: throughput e interfaces, conexiones activas (conntrack) vía
      WebSocket en vivo.

## Fase 2 — L7 (Suricata)
- [x] Integración NFQUEUE: reglas con `inspect_l7=True` se desvían a la cola de
      Suricata (`queue num N bypass`) en vez de aplicar accept/drop directo; si
      Suricata está deshabilitado globalmente, la regla usa su acción normal.
- [x] `suricata_service`: render de `suricata.yaml` y del override systemd
      (el nº de cola se pasa por `-q`), control start/stop/restart, gestión de
      *sources* de `suricata-update` (registradas o URLs propias, p. ej. GitHub).
- [x] Lectura de `eve.json` (ventana acotada en memoria) y API de alertas.
- [x] UI: página Suricata (config, fuentes, sincronizar firmas, alertas, "Bloquear IP").
- [x] Permisos de despliegue: grupo `suricata` compartido, regla polkit para que
      `nftguard` controle solo `suricata.service`.

## Fase 3 — VPN WireGuard
- [x] `wireguard_service`: generación de claves (curve25519 vía `cryptography`,
      sin depender del binario `wg` para esto), gestión de peers con asignación
      automática de IP.
- [x] Integración nftables: puerto UDP abierto en WAN, forwarding `wg0` ↔ LAN/WAN.
- [x] `wg syncconf` para aplicar cambios de peers sin cortar conexiones activas.
- [x] UI: alta/baja de peers, ver/descargar config, código QR para móvil.
- [x] Permisos de despliegue: `/etc/wireguard` para `nftguard`, regla polkit para
      `wg-quick@wg0.service`.

## Fase 4 — Pulido
- [x] Multiusuario y roles: admin (todo) / solo lectura, forzado en el backend
      (`require_admin`) en cada endpoint que muta estado — no solo ocultado en la UI.
- [x] Auditoría de cambios: tabla `AuditLog`, registrada en login, reglas, apply,
      config/servicio de Suricata y WireGuard, gestión de usuarios. Página de
      consulta (solo admin).
- [x] Backup/restore de configuración completa (JSON: reglas, NAT, Suricata,
      WireGuard, usuarios). Reemplazo total vía `/api/backup/restore`.
- [x] Hardening: rate-limit de login (5 fallos / 5 min → bloqueo 60s por IP), TLS
      autofirmado generado en `install.sh` (uvicorn sirve HTTPS directamente),
      cambio de contraseña propia.

## Pendiente real (requiere el Debian de pruebas)
- [ ] Ejecutar `install.sh` en el equipo real y validar que arranca todo
      (`nftguard-backend`, `suricata` vía NFQUEUE, `wg-quick@wg0`) sin intervención
      manual más allá de revisar `backend.env`.
- [ ] Sincronizar firmas de verdad con `suricata-update`, generar tráfico que
      dispare una alerta real y confirmar el bloqueo end-to-end.
- [ ] Conectar un cliente WireGuard real (móvil vía QR, o desktop vía .conf) y
      confirmar que llega a la LAN.
- [ ] Medir consumo de CPU/RAM en reposo y bajo carga en el hardware real objetivo.

## Ideas para más adelante (no bloqueantes)
- Ocultar/deshabilitar en la UI (no solo bloquear en el backend) los controles de
  escritura para usuarios de solo lectura en Reglas/NAT/Suricata/WireGuard.
- VLANs / más de dos interfaces (zonas más allá de WAN/LAN).
- Reglas basadas en grupos de IP reutilizables (nft sets) en vez de IP/CIDR sueltas.
