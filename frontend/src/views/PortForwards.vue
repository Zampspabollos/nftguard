<script setup>
import { onMounted, ref } from "vue";
import PortForwardForm from "../components/PortForwardForm.vue";
import { apiFetch } from "../api.js";

const items = ref([]);
const loading = ref(true);
const errorMsg = ref("");
const banner = ref(null);
const creating = ref(false);
const applying = ref(false);

async function load() {
  loading.value = true;
  errorMsg.value = "";
  try {
    items.value = await apiFetch("/rules/portforwards");
  } catch (e) {
    errorMsg.value = e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function save(payload) {
  banner.value = null;
  try {
    await apiFetch("/rules/portforwards", { method: "POST", body: payload });
    creating.value = false;
    await load();
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function remove(pf) {
  if (!confirm(`¿Eliminar la redirección del puerto ${pf.wan_port}?`)) return;
  banner.value = null;
  try {
    await apiFetch(`/rules/portforwards/${pf.id}`, { method: "DELETE" });
    await load();
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function applyRules() {
  applying.value = true;
  banner.value = null;
  try {
    const res = await apiFetch("/rules/apply", { method: "POST" });
    banner.value = { type: "ok", message: `Reglas aplicadas: ${res.message}` };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    applying.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">NAT / Port-forwarding</h1>
  <p style="color: var(--text-dim); margin-top: -12px">
    Redirige un puerto de la interfaz WAN a un host interno. Requiere modo gateway.
  </p>

  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>
  <div v-if="errorMsg" class="banner error">{{ errorMsg }}</div>

  <div class="btn-row">
    <button class="btn" @click="creating = true">+ Nueva redirección</button>
    <button class="btn secondary" :disabled="applying" @click="applyRules">
      {{ applying ? "Aplicando..." : "Aplicar cambios" }}
    </button>
  </div>

  <PortForwardForm v-if="creating" @save="save" @cancel="creating = false" />

  <div class="card">
    <h2>Redirecciones ({{ items.length }})</h2>
    <p v-if="loading">Cargando...</p>
    <table v-else>
      <thead>
        <tr>
          <th>Proto</th>
          <th>Puerto WAN</th>
          <th>Destino</th>
          <th>Comentario</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="pf in items" :key="pf.id" :class="{ disabled: !pf.enabled }">
          <td>{{ pf.protocol }}</td>
          <td>{{ pf.wan_port }}</td>
          <td>{{ pf.dst_ip }}:{{ pf.dst_port }}</td>
          <td>{{ pf.comment }}</td>
          <td><button class="btn danger" @click="remove(pf)">Eliminar</button></td>
        </tr>
        <tr v-if="items.length === 0">
          <td colspan="5">No hay redirecciones configuradas.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
