<script setup>
import { onMounted, reactive, ref } from "vue";
import { apiFetch } from "../api.js";

const config = reactive({ enabled: false, nfqueue_num: 100, home_net: "" });
const status = reactive({ enabled: false, active: false });
const sources = ref([]);
const alerts = ref([]);
const newSource = reactive({ name: "", url: "", enabled: true });

const banner = ref(null);
const loading = ref(true);
const savingConfig = ref(false);
const syncing = ref(false);
const serviceBusy = ref(false);

async function loadAll() {
  loading.value = true;
  try {
    const [cfg, st, src, al] = await Promise.all([
      apiFetch("/suricata/config"),
      apiFetch("/suricata/status"),
      apiFetch("/suricata/sources"),
      apiFetch("/suricata/alerts?limit=50"),
    ]);
    Object.assign(config, cfg);
    Object.assign(status, st);
    sources.value = src;
    alerts.value = al;
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);

async function saveConfig() {
  savingConfig.value = true;
  banner.value = null;
  try {
    const cfg = await apiFetch("/suricata/config", {
      method: "PUT",
      body: {
        enabled: config.enabled,
        nfqueue_num: Number(config.nfqueue_num),
        home_net: config.home_net,
      },
    });
    Object.assign(config, cfg);
    banner.value = {
      type: "ok",
      message:
        "Configuración guardada. Recuerda: 1) reiniciar el servicio Suricata, y " +
        "2) pulsar 'Aplicar cambios' en Reglas para que nftables use la cola NFQUEUE.",
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
    const res = await apiFetch(`/suricata/service/${action}`, { method: "POST" });
    banner.value = { type: res.ok ? "ok" : "error", message: res.message || action };
    status.active = await apiFetch("/suricata/status").then((s) => s.active);
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    serviceBusy.value = false;
  }
}

async function addSource() {
  banner.value = null;
  try {
    await apiFetch("/suricata/sources", {
      method: "POST",
      body: { name: newSource.name, url: newSource.url || null, enabled: newSource.enabled },
    });
    newSource.name = "";
    newSource.url = "";
    newSource.enabled = true;
    sources.value = await apiFetch("/suricata/sources");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function removeSource(source) {
  if (!confirm(`¿Eliminar la fuente "${source.name}"?`)) return;
  try {
    await apiFetch(`/suricata/sources/${source.id}`, { method: "DELETE" });
    sources.value = await apiFetch("/suricata/sources");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function syncSources() {
  syncing.value = true;
  banner.value = null;
  try {
    const res = await apiFetch("/suricata/sources/sync", { method: "POST" });
    banner.value = { type: res.ok ? "ok" : "error", message: res.message || "Firmas sincronizadas" };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    syncing.value = false;
  }
}

async function refreshAlerts() {
  try {
    alerts.value = await apiFetch("/suricata/alerts?limit=50");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function blockIp(alert) {
  if (!alert.src_ip) return;
  if (!confirm(`¿Bloquear todo el tráfico desde ${alert.src_ip}?`)) return;
  try {
    await apiFetch("/suricata/block", {
      method: "POST",
      body: { ip: alert.src_ip, comment: `bloqueo desde alerta: ${alert.signature || ""}` },
    });
    banner.value = { type: "ok", message: `Regla de bloqueo creada para ${alert.src_ip}. Ve a Reglas y pulsa "Aplicar cambios".` };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}
</script>

<template>
  <h1 class="page-title">Suricata (L7 / IPS)</h1>

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
          <input id="suri-enabled" v-model="config.enabled" type="checkbox" />
          <label for="suri-enabled" style="margin: 0">Inspección L7 habilitada globalmente</label>
        </div>
        <div>
          <label>Número de cola NFQUEUE</label>
          <input v-model="config.nfqueue_num" type="number" min="0" max="65535" />
        </div>
        <div>
          <label>HOME_NET</label>
          <input v-model="config.home_net" placeholder="ej. 192.168.10.0/24" />
        </div>
      </div>
      <div class="btn-row">
        <button class="btn" :disabled="savingConfig" @click="saveConfig">
          {{ savingConfig ? "Guardando..." : "Guardar configuración" }}
        </button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('start')">Iniciar</button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('restart')">Reiniciar</button>
        <button class="btn secondary" :disabled="serviceBusy" @click="serviceAction('stop')">Detener</button>
      </div>
    </div>

    <div class="card">
      <h2>Fuentes de firmas</h2>
      <p style="color: var(--text-dim); margin-top: -6px">
        Usa un nombre ya registrado en suricata-update (ej. <code>et/open</code>) dejando la URL
        vacía, o pega la URL de un <code>.rules</code> (p. ej. de un repo GitHub) para añadirlo
        como fuente personalizada.
      </p>
      <table>
        <thead>
          <tr>
            <th>Nombre</th>
            <th>URL</th>
            <th>Activa</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id">
            <td>{{ s.name }}</td>
            <td style="word-break: break-all">{{ s.url || "(fuente registrada)" }}</td>
            <td>{{ s.enabled ? "sí" : "no" }}</td>
            <td><button class="btn danger" @click="removeSource(s)">Eliminar</button></td>
          </tr>
          <tr v-if="sources.length === 0">
            <td colspan="4">Sin fuentes configuradas todavía.</td>
          </tr>
        </tbody>
      </table>

      <div class="form-grid" style="margin-top: 14px">
        <div>
          <label>Nombre</label>
          <input v-model="newSource.name" placeholder="ej. et/open o mi-fuente" />
        </div>
        <div>
          <label>URL (opcional)</label>
          <input v-model="newSource.url" placeholder="https://raw.githubusercontent.com/.../rules.rules" />
        </div>
        <div class="checkbox-row" style="align-items: flex-end; padding-bottom: 8px">
          <input id="src-enabled" v-model="newSource.enabled" type="checkbox" />
          <label for="src-enabled" style="margin: 0">Activa</label>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn" :disabled="!newSource.name" @click="addSource">+ Añadir fuente</button>
        <button class="btn secondary" :disabled="syncing" @click="syncSources">
          {{ syncing ? "Sincronizando..." : "Actualizar firmas ahora" }}
        </button>
      </div>
    </div>

    <div class="card">
      <h2>Alertas recientes</h2>
      <div class="btn-row">
        <button class="btn secondary" @click="refreshAlerts">Refrescar</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Hora</th>
            <th>Origen</th>
            <th>Destino</th>
            <th>Firma</th>
            <th>Severidad</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(a, i) in alerts" :key="i">
            <td>{{ a.timestamp }}</td>
            <td>{{ a.src_ip }}</td>
            <td>{{ a.dest_ip }}</td>
            <td>{{ a.signature }}</td>
            <td>{{ a.severity }}</td>
            <td><button class="btn danger" @click="blockIp(a)">Bloquear IP</button></td>
          </tr>
          <tr v-if="alerts.length === 0">
            <td colspan="6">Sin alertas todavía.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
