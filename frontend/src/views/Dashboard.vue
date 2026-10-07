<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { apiFetch, wsStatusUrl } from "../api.js";

const status = ref({ interfaces: {}, conntrack: { count: 0, max: 0 } });
const connected = ref(false);
const errorMsg = ref("");
let socket = null;
let reconnectTimer = null;

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let value = bytes;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

const interfaceList = computed(() =>
  Object.entries(status.value.interfaces || {})
    .filter(([name]) => name !== "lo")
    .map(([name, stats]) => ({ name, ...stats })),
);

const conntrackPct = computed(() => {
  const { count, max } = status.value.conntrack || {};
  if (!max) return 0;
  return Math.min(100, Math.round((count / max) * 100));
});

function connect() {
  try {
    socket = new WebSocket(wsStatusUrl());
  } catch {
    scheduleReconnect();
    return;
  }
  socket.onopen = () => {
    connected.value = true;
    errorMsg.value = "";
  };
  socket.onmessage = (event) => {
    status.value = JSON.parse(event.data);
  };
  socket.onclose = () => {
    connected.value = false;
    scheduleReconnect();
  };
  socket.onerror = () => {
    connected.value = false;
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connect, 3000);
}

onMounted(async () => {
  try {
    status.value = await apiFetch("/status");
  } catch (e) {
    errorMsg.value = e.message;
  }
  connect();
});

onUnmounted(() => {
  clearTimeout(reconnectTimer);
  if (socket) socket.close();
});
</script>

<template>
  <h1 class="page-title">Dashboard</h1>
  <div v-if="errorMsg" class="banner error">{{ errorMsg }}</div>

  <div class="card">
    <h2>
      Estado de la conexión en vivo
      <span :style="{ color: connected ? 'var(--ok)' : 'var(--danger)' }">
        ({{ connected ? "conectado" : "reconectando..." }})
      </span>
    </h2>
  </div>

  <div class="card">
    <h2>Interfaces</h2>
    <div class="grid">
      <div v-for="iface in interfaceList" :key="iface.name" class="stat">
        <div class="label">{{ iface.name }}</div>
        <div class="value">↓ {{ formatBytes(iface.rx_bytes) }}</div>
        <div class="value">↑ {{ formatBytes(iface.tx_bytes) }}</div>
      </div>
      <div v-if="interfaceList.length === 0" class="stat">
        <div class="label">Sin datos de interfaces todavía</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Conexiones activas (conntrack)</h2>
    <div class="stat">
      <div class="label">{{ status.conntrack.count }} / {{ status.conntrack.max || "?" }}</div>
      <div class="value">{{ conntrackPct }}%</div>
    </div>
  </div>
</template>
