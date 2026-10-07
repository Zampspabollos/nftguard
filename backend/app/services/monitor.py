"""Métricas básicas del sistema para el dashboard. Lee directamente de /proc, sin
dependencias externas, para mantener el footprint mínimo."""

from pathlib import Path

_NET_DEV = Path("/proc/net/dev")
_CONNTRACK_COUNT = Path("/proc/sys/net/netfilter/nf_conntrack_count")
_CONNTRACK_MAX = Path("/proc/sys/net/netfilter/nf_conntrack_max")


def interface_stats() -> dict[str, dict[str, int]]:
    if not _NET_DEV.exists():
        return {}
    stats: dict[str, dict[str, int]] = {}
    lines = _NET_DEV.read_text().splitlines()[2:]
    for line in lines:
        name, rest = line.split(":", 1)
        fields = rest.split()
        stats[name.strip()] = {
            "rx_bytes": int(fields[0]),
            "rx_packets": int(fields[1]),
            "tx_bytes": int(fields[8]),
            "tx_packets": int(fields[9]),
        }
    return stats


def conntrack_stats() -> dict[str, int]:
    def _read(path: Path) -> int | None:
        return int(path.read_text().strip()) if path.exists() else None

    return {"count": _read(_CONNTRACK_COUNT) or 0, "max": _read(_CONNTRACK_MAX) or 0}


def get_status() -> dict:
    return {"interfaces": interface_stats(), "conntrack": conntrack_stats()}
