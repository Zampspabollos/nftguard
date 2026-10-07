from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NFTGUARD_", env_file=".env", extra="ignore")

    # General
    mode: str = "gateway"  # "gateway" o "host"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 12

    # Red
    wan_iface: str = "eth0"
    lan_iface: str = "eth1"
    lan_network: str = "192.168.10.0/24"
    web_ui_port: int = 8443

    # Almacenamiento
    db_path: str = "./nftguard.db"

    # nftables
    nft_bin: str = "/usr/sbin/nft"
    ruleset_dir: str = "/etc/nftguard"
    ruleset_path: str = "/etc/nftguard/ruleset.nft"
    ruleset_backup_path: str = "/etc/nftguard/ruleset.nft.bak"

    # Suricata (L7)
    suricata_bin: str = "/usr/bin/suricata"
    suricata_update_bin: str = "/usr/bin/suricata-update"
    suricata_config_path: str = "/etc/suricata/suricata.yaml"
    suricata_rules_dir: str = "/var/lib/suricata/rules"
    suricata_log_dir: str = "/var/log/suricata"
    suricata_eve_path: str = "/var/log/suricata/eve.json"
    suricata_service_name: str = "suricata.service"
    suricata_systemd_override_dir: str = "/etc/systemd/system/suricata.service.d"
    systemctl_bin: str = "/usr/bin/systemctl"

    # WireGuard (VPN)
    wg_bin: str = "/usr/bin/wg"
    wireguard_iface: str = "wg0"
    wireguard_conf_path: str = "/etc/wireguard/wg0.conf"


settings = Settings()
