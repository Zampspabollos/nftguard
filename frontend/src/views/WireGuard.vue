<script setup>
import { onMounted, onUnmounted, reactive, ref } from "vue";
import { apiFetch, apiFetchBlob } from "../api.js";

const config = reactive({
  enabled: false,
  public_key: "",
  listen_port: 51820,
  server_ip: "",
  network_cidr: "",
  dns: "",
  endpoint_host: "",
  client_allowed_ips: "",
});
const status = reactive({ enabled: false, active: false });
const peers = ref([]);
const newPeerName = ref("");

const banner = ref(null);
const loading = ref(true);
const savingConfig = ref(false);
const serviceBusy = ref(false);
const creatingPeer = ref(false);

const viewingConfig = ref(null); // { name, text }
const qrUrl = ref(null);
const qrPeerId = ref(null);

async function loadAll() {
  loading.value = true;
  try {
    const [cfg, st, pr] = await Promise.all([
      apiFetch("/wireguard/config"),
      apiFetch("/wireguard/status"),
      apiFetch("/wireguard/peers"),
    ]);
    Object.assign(config, cfg, { dns: cfg.dns || "", endpoint_host: cfg.endpoint_host || "" });
    Object.assign(status, st);
    peers.value = pr;
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);
onUnmounted(() => {
  if (qrUrl.value) URL.revokeObjectURL(qrUrl.value);
});

async function saveConfig() {
  savingConfig.value = true;
  banner.value = null;
  try {
    const cfg = await apiFetch("/wireguard/config", {
      method: "PUT",
      body: {
        enabled: config.enabled,
        listen_port: Number(config.listen_port),
        server_ip: config.server_ip,
        network_cidr: config.network_cidr,
        dns: config.dns || null,
        endpoint_host: config.endpoint_host || null,
        client_allowed_ips: config.client_allowed_ips,
      },
    });
    Object.assign(config, cfg, { dns: cfg.dns || "", endpoint_host: cfg.endpoint_host || "" });
    banner.value = {
      type: "ok",
      message: "Configuración guardada y sincronizada. Recuerda pulsar 'Aplicar cambios' en Reglas.",
    };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    savingConfig.value = false;
  }
}

async function serviceAction(action) {
  serviceBusy.value = true;
  banner.value = null;
  try {
    const res = await apiFetch(`/wireguard/service/${action}`, { method: "POST" });
    banner.value = { type: res.ok ? "ok" : "error", message: res.message || action };
    status.active = await apiFetch("/wireguard/status").then((s) => s.active);
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    serviceBusy.value = false;
  }
}

async function createPeer() {
  if (!newPeerName.value.trim()) return;
  creatingPeer.value = true;
  banner.value = null;
  try {
    const res = await apiFetch("/wireguard/peers", { method: "POST", body: { name: newPeerName.value.trim() } });
    newPeerName.value = "";
    peers.value = await apiFetch("/wireguard/peers");
    viewingConfig.value = { name: res.peer.name, text: res.config };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    creatingPeer.value = false;
  }
}

async function togglePeer(peer) {
  banner.value = null;
  try {
    await apiFetch(`/wireguard/peers/${peer.id}`, { method: "PUT", body: { enabled: !peer.enabled } });
    peers.value = await apiFetch("/wireguard/peers");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function deletePeer(peer) {
  if (!confirm(`¿Eliminar el peer "${peer.name}"? Dejará de poder conectarse.`)) return;
  banner.value = null;
  try {
    await apiFetch(`/wireguard/peers/${peer.id}`, { method: "DELETE" });
    peers.value = await apiFetch("/wireguard/peers");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function showConfig(peer) {
  banner.value = null;
  try {
    const res = await apiFetch(`/wireguard/peers/${peer.id}/config`);
    viewingConfig.value = { name: peer.name, text: res.config };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

function downloadConfig() {
  if (!viewingConfig.value) return;
  const blob = new Blob([viewingConfig.value.text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${viewingConfig.value.name}.conf`;
  a.click();
  URL.revokeObjectURL(url);
}

async function showQr(peer) {
  banner.value = null;
  try {
    const blob = await apiFetchBlob(`/wireguard/peers/${peer.id}/qrcode`);
    if (qrUrl.value) URL.revokeObjectURL(qrUrl.value);
    qrUrl.value = URL.createObjectURL(blob);
    qrPeerId.value = peer.id;
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}
</script>

<template>
  <h1 class="page-title">WireGuard (VPN)</h1>

  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>
  <p v-if="loading">Cargando...</p>

  <template v-else>
    <div class="card">
      <h2>
        Estado
        <span :style="{ color: status.active ? 'var(--ok)' : 'var(--text-dim)' }">
          ({{ status.active ? "servicio activo" : "servicio parado" }})
        </span>
      </h2>
      <div class="form-grid">
        <div class="checkbox-row">
          <input id="wg-enabled" v-model="config.enabled" type="checkbox" />
          <label for="wg-enabled" style="margin: 0">VPN habilitada</label>
        </div>
        <div>
          <label>Puerto de escucha</label>
          <input v-model="config.listen_port" type="number" min="1" max="65535" />
        </div>
        <div>
          <label>Host/IP público (endpoint)</label>
          <input v-model="config.endpoint_host" placeholder="ej. vpn.midominio.com" />
        </div>
      </div>
      <div class="form-grid">
        <div>
          <label>IP del servidor en la VPN</label>
          <input v-model="config.server_ip" placeholder="ej. 10.8.0.1" />
        </div>
        <div>
          <label>Subred de la VPN</label>
          <input v-model="config.network_cidr" placeholder="ej. 10.8.0.0/24" />
        </div>
        <div>
          <label>DNS para los clientes (opcional)</label>
          <input v-model="config.dns" placeholder="ej. 192.168.10.1" />
        </div>
        <div>
          <label>Redes que el cliente enruta por la VPN</label>
          <input v-model="config.client_allowed_ips" placeholder="ej. 192.168.10.0/24" />
        </div>
      </div>
      <p style="color: var(--text-dim); font-size: 12px">Clave pública del servidor: {{ config.public_key }}</p>
      <div class="btn-row">
        <button class="btn" :disabled="savingConfig" @click="saveConfig">
          {{ savingConfig ? "Guardando..." : "Guardar configuración" }}
        </button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('start')">Iniciar</button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('restart')">Reiniciar</button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('stop')">Detener</button>
      </div>
    </div>

    <div v-if="viewingConfig" class="card">
      <h2>Config de "{{ viewingConfig.name }}"</h2>
      <pre class="ruleset">{{ viewingConfig.text }}</pre>
      <div class="btn-row">
        <button class="btn secondary" @click="downloadConfig">Descargar .conf</button>
        <button class="btn secondary" @click="viewingConfig = null">Cerrar</button>
      </div>
    </div>

    <div v-if="qrUrl" class="card">
      <h2>Código QR</h2>
      <img :src="qrUrl" alt="QR WireGuard" style="background: #fff; padding: 12px; border-radius: 6px" />
      <div class="btn-row">
        <button class="btn secondary" @click="qrUrl = null">Cerrar</button>
      </div>
    </div>

    <div class="card">
      <h2>Peers ({{ peers.length }})</h2>
      <table>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>IP VPN</th>
            <th>Activo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in peers" :key="p.id" :class="{ disabled: !p.enabled }">
            <td>{{ p.name }}</td>
            <td>{{ p.address }}</td>
            <td>{{ p.enabled ? "sí" : "no" }}</td>
            <td style="white-space: nowrap">
              <button class="btn secondary" @click="showConfig(p)">Config</button>
              <button class="btn secondary" @click="showQr(p)">QR</button>
              <button class="btn secondary" @click="togglePeer(p)">{{ p.enabled ? "Desactivar" : "Activar" }}</button>
              <button class="btn danger" @click="deletePeer(p)">Eliminar</button>
            </td>
          </tr>
          <tr v-if="peers.length === 0">
            <td colspan="4">Sin peers todavía.</td>
          </tr>
        </tbody>
      </table>

      <div class="form-grid" style="margin-top: 14px">
        <div>
          <label>Nombre del nuevo peer</label>
          <input v-model="newPeerName" placeholder="ej. laptop-ruben" @keyup.enter="createPeer" />
        </div>
      </div>
      <div class="btn-row">
        <button class="btn" :disabled="creatingPeer || !newPeerName.trim()" @click="createPeer">+ Añadir peer</button>
      </div>
    </div>
  </template>
</template>
