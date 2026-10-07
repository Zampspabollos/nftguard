<script setup>
import { onMounted, ref } from "vue";
import { apiFetch } from "../api.js";

const entries = ref([]);
const loading = ref(true);
const banner = ref(null);

async function load() {
  loading.value = true;
  banner.value = null;
  try {
    entries.value = await apiFetch("/audit?limit=200");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <h1 class="page-title">Auditoría</h1>
  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>

  <div class="btn-row">
    <button class="btn secondary" @click="load">Refrescar</button>
  </div>

  <div class="card">
    <h2>Últimas {{ entries.length }} acciones</h2>
    <p v-if="loading">Cargando...</p>
    <table v-else>
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Usuario</th>
          <th>Acción</th>
          <th>Detalle</th>
          <th>Resultado</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id">
          <td style="white-space: nowrap">{{ new Date(e.timestamp).toLocaleString() }}</td>
          <td>{{ e.username }}</td>
          <td>{{ e.action }}</td>
          <td>{{ e.detail }}</td>
          <td>
            <span :class="['badge', e.ok ? 'accept' : 'drop']">{{ e.ok ? "ok" : "fallo" }}</span>
          </td>
        </tr>
        <tr v-if="entries.length === 0">
          <td colspan="5">Sin actividad registrada todavía.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
