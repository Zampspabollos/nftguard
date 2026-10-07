# Arquitectura

## Objetivo

Firewall gateway/router (LAN/WAN) sobre Debian, con filtrado L3/L4 por `nftables`,
inspección L7 selectiva con Suricata, VPN WireGuard, y gestión completa vía web.
Prioridad: rendir bien en hardware modesto.

## Principio de diseño: "el kernel filtra, el userspace solo mira lo necesario"

`nftables` hace todo el trabajo de L3/L4 en kernel (filtrado, estado de conexión vía
`conntrack`, NAT, rate-limiting). Esto es prácticamente gratis en CPU.

La inspección L7 (Suricata) es cara en CPU/RAM si se aplica a todo el tráfico. Por eso
**no se inspecciona todo**: nftables desvía a una cola `NFQUEUE` solo el tráfico que
interesa inspeccionar (por ejemplo: paquetes nuevos de conexiones TCP a puertos
HTTP/HTTPS/DNS, o lo que el usuario marque explícitamente desde la UI). El resto del
tráfico nunca pasa por Suricata. Esto es lo que permite tener "capacidades L7" sin pagar
el coste de L7 en todo el tráfico.

```
Internet (WAN) ──> [nftables: filtrado L3/L4, conntrack, NAT] ──> LAN
                              │
                              │ (solo flujos marcados)
                              ▼
                        NFQUEUE n ──> Suricata (IPS inline)
                              │
                     accept/drop/alert ──> de vuelta al kernel
```

## Componentes

### Plano de datos

- **nftables**: una única tabla `inet nftguard` generada por el backend (nunca se edita
  a mano en producción). Cadenas `input`, `forward`, `output`, NAT (`prerouting`/
  `postrouting`). Zonas = interfaces (`wan_iface`, `lan_iface`), no VLANs en la v1.
- **Suricata**: modo IPS vía `NFQUEUE` (`af-packet` queda como alternativa futura si se
  necesita inspeccionar un segmento completo en bridge). El número de cola se fija por
  línea de comandos (`-q N`, vía un override systemd que reescribe el backend), y en
  `suricata.yaml` con `fail-open: yes` + `queue ... bypass` en nftables: si Suricata se
  cae, ese tráfico pasa sin inspeccionar en vez de bloquearse por completo. Reglas
  gestionadas con `suricata-update`; el backend expone qué *sources* (registradas o URLs
  propias, incl. repos GitHub) están activas. Permisos: `nftguard` (sin privilegios de
  root) comparte grupo del sistema `suricata` para leer/escribir config, reglas y
  `eve.json`, y una regla polkit le permite arrancar/parar/recargar *solo*
  `suricata.service`, sin darle control sobre el resto de systemd.
- **WireGuard**: interfaz `wg0`. Las claves se generan con la librería `cryptography`
  (curve25519), sin depender del binario `wg` solo para eso. El backend reescribe
  `wg0.conf` y recarga con `wg syncconf` (no corta conexiones activas al añadir/quitar
  peers). Gestionado vía el unit estándar de Debian `wg-quick@wg0.service`. nftables
  abre el puerto UDP en WAN y permite el forwarding `wg0` ↔ LAN/WAN cuando la VPN está
  habilitada. Permisos: `/etc/wireguard` es de `nftguard`, y una regla polkit le permite
  controlar *solo* `wg-quick@wg0.service`.

### Plano de control (backend FastAPI)

- `services/nftables_engine.py`: renderiza el ruleset desde los modelos de la BD
  (Jinja2), lo valida (`nft -c -f`) y lo aplica de forma atómica con rollback a la
  última versión buena si falla.
- `services/suricata_service.py`: gestiona `suricata-update`, arranque/parada del
  proceso IPS, lectura de alertas (`eve.json`).
- `services/wireguard_service.py`: gestión de peers/claves.
- `services/monitor.py`: métricas de interfaces, conntrack, throughput para el
  dashboard (push por WebSocket).
- `services/audit.py`: registro de auditoría (quién hizo qué) para las acciones que
  cambian estado.
- `services/backup_service.py`: export/import de toda la configuración como JSON.
- SQLite como única base de datos (sin daemon adicional).

### Usuarios, permisos y auditoría

Dos roles: administrador (lee y escribe todo) y solo-lectura. La distinción se aplica
en el backend (`api/deps.py:require_admin`) en cada endpoint que muta estado —
reglas, apply, config/servicio de Suricata y WireGuard, gestión de usuarios — no solo
ocultando botones en la UI, así que un usuario de solo lectura no puede saltársela
llamando a la API directamente. Cada una de esas acciones queda registrada en
`AuditLog` (quién, cuándo, qué, resultado).

### Hardening del propio backend

- Login con rate-limit en memoria: 5 fallos en 5 minutos bloquean esa IP 60s.
- TLS: `install.sh` genera un certificado autofirmado y uvicorn sirve HTTPS
  directamente (sin reverse proxy). Sustituible por uno real si se expone fuera de
  la LAN.
- Contraseñas con bcrypt (librería `bcrypt` directamente, no vía `passlib`: en las
  versiones recientes de `bcrypt` rompía la detección de backend de `passlib`).

### Frontend

Vue 3 + Vite, build estático servido por el propio backend (sin Node en producción).

## Por qué estas elecciones

- **nftables** en vez de iptables: sucesor oficial, reglas atómicas, sets nativos,
  mejor rendimiento con muchas reglas.
- **Suricata** en vez de Snort/otros: mantenido activamente, soporta reglas ET,
  modo NFQUEUE nativo, `eve.json` fácil de consumir desde un backend.
- **SQLite** en vez de Postgres/MySQL: cero huella de daemon adicional, adecuado para
  un equipo de pocos recursos y una sola instancia.
- **FastAPI**: async nativo (necesario para WebSocket de métricas en vivo sin hilos
  bloqueantes), tipado con Pydantic, bajo consumo comparado con stacks más pesados.

## Lo que NO se gestiona manualmente en el servidor

El fichero de reglas nftables activo (`/etc/nftguard/ruleset.nft`) es generado. Un
cambio manual se sobrescribirá en el siguiente "apply" desde la UI. Si se necesita algo
que la UI no cubre todavía, se añade como feature al modelo de reglas, no como edición
directa.
