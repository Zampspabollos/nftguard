# nftguard

Firewall L3/L4/L7 para Debian, pensado para equipos con pocos recursos, con interfaz
web de gestión.

- **L3/L4**: `nftables` (filtrado, NAT, port-forwarding, rate-limiting). Rendimiento
  nativo en kernel.
- **L7**: `Suricata` en modo IPS, pero solo recibe el tráfico que se desvía explícitamente
  vía `NFQUEUE` desde nftables (no todo el tráfico pasa por userspace). Firmas públicas
  gestionables desde la UI vía `suricata-update` (ET Open, abuse.ch, repos GitHub, etc.).
- **VPN**: WireGuard, alta/baja de peers desde la UI con config/QR descargables.
- **Gestión**: backend FastAPI + SQLite, frontend Vue 3. Todo corre como servicios
  systemd en Debian. Usuarios con rol admin/solo-lectura, auditoría de cambios,
  backup/restore de toda la configuración, login con rate-limit y TLS autofirmado.

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para el diseño completo y
[docs/ROADMAP.md](docs/ROADMAP.md) para qué falta probar en el Debian real.

## Estado del proyecto

Las 4 fases están implementadas y probadas (backend + navegador real) en un entorno
de desarrollo; falta la validación final en el Debian de pruebas con `nft`,
`suricata` y `wireguard-tools` instalados de verdad (ver "pendiente real" en el
roadmap). Para desplegar: compila el frontend, copia el proyecto al Debian de
pruebas y ejecuta `sudo deploy/install.sh`.

## Desarrollo

El desarrollo se hace en cualquier máquina; el despliegue y las pruebas reales de
`nftables`/`suricata`/`wireguard` requieren el Debian de pruebas (no funcionan en
Windows/macOS). Sin esos binarios, el backend funciona igual (CRUD de reglas,
preview del ruleset) pero "Validar"/"Aplicar" devuelven un error claro indicando
que falta `nft`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8443
```

```bash
cd frontend
npm install
npm run dev
```

El dev server de Vite (puerto 5173 por defecto) proxea `/api` hacia `localhost:8443`
(ver `frontend/vite.config.js`). En producción no hace falta Node: `npm run build`
genera `frontend/dist`, que el propio backend sirve como estáticos (ver `app/main.py`).
