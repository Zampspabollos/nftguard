<script setup>
import { onMounted, ref } from "vue";
import RuleForm from "../components/RuleForm.vue";
import { ApiError, apiFetch } from "../api.js";

const rules = ref([]);
const loading = ref(true);
const errorMsg = ref("");
const banner = ref(null); // { type: 'ok'|'error', message }

const editing = ref(null); // null = oculto, {} = nueva, {...} = editar
const preview = ref(null);
const applying = ref(false);

async function loadRules() {
  loading.value = true;
  errorMsg.value = "";
  try {
    rules.value = await apiFetch("/rules");
  } catch (e) {
    errorMsg.value = e.message;
  } finally {
    loading.value = false;
  }
}

onMounted(loadRules);

function startCreate() {
  preview.value = null;
  editing.value = {};
}

function startEdit(rule) {
  preview.value = null;
  editing.value = rule;
}

function cancelEdit() {
  editing.value = null;
}

async function saveRule(payload) {
  banner.value = null;
  try {
    if (editing.value && editing.value.id) {
      await apiFetch(`/rules/${editing.value.id}`, { method: "PUT", body: payload });
    } else {
      await apiFetch("/rules", { method: "POST", body: payload });
    }
    editing.value = null;
    await loadRules();
  } catch (e) {
    banner.value = { type: "error", message: e instanceof ApiError ? e.message : String(e) };
  }
}

async function deleteRule(rule) {
  if (!confirm(`¿Eliminar la regla "${rule.comment || rule.id}"?`)) return;
  banner.value = null;
  try {
    await apiFetch(`/rules/${rule.id}`, { method: "DELETE" });
    await loadRules();
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}

async function showPreview() {
  banner.value = null;
  try {
    const data = await apiFetch("/rules/preview");
    preview.value = data.ruleset;
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
  <h1 class="page-title">Reglas L3/L4</h1>

  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>
  <div v-if="errorMsg" class="banner error">{{ errorMsg }}</div>

  <div class="btn-row">
    <button class="btn" @click="startCreate">+ Nueva regla</button>
    <button class="btn secondary" @click="showPreview">Vista previa del ruleset</button>
    <button class="btn secondary" :disabled="applying" @click="applyRules">
      {{ applying ? "Aplicando..." : "Aplicar cambios" }}
    </button>
  </div>

  <RuleForm v-if="editing" :initial="editing.id ? editing : null" @save="saveRule" @cancel="cancelEdit" />

  <div v-if="preview" class="card">
    <h2>Ruleset generado (sin aplicar)</h2>
    <pre class="ruleset">{{ preview }}</pre>
  </div>

  <div class="card">
    <h2>Reglas ({{ rules.length }})</h2>
    <p v-if="loading">Cargando...</p>
    <table v-else>
      <thead>
        <tr>
          <th>Prio.</th>
          <th>Cadena</th>
          <th>Acción</th>
          <th>Proto</th>
          <th>Origen</th>
          <th>Destino</th>
          <th>Comentario</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="rule in rules" :key="rule.id" :class="{ disabled: !rule.enabled }">
          <td>{{ rule.priority }}</td>
          <td>{{ rule.chain }}</td>
          <td>
            <span :class="['badge', rule.action]">{{ rule.action }}</span>
            <span v-if="rule.inspect_l7" class="badge" style="background: var(--accent-dim); color: #bfe4fc">L7</span>
          </td>
          <td>{{ rule.protocol }}</td>
          <td>
            {{ rule.src_iface || "*" }} {{ rule.src_ip || "" }}
            <template v-if="rule.src_port">:{{ rule.src_port }}</template>
          </td>
          <td>
            {{ rule.dst_iface || "*" }} {{ rule.dst_ip || "" }}
            <template v-if="rule.dst_port">:{{ rule.dst_port }}</template>
          </td>
          <td>{{ rule.comment }}</td>
          <td style="white-space: nowrap">
            <button class="btn secondary" @click="startEdit(rule)">Editar</button>
            <button class="btn danger" @click="deleteRule(rule)">Eliminar</button>
          </td>
        </tr>
        <tr v-if="rules.length === 0">
          <td colspan="8">No hay reglas todavía. El tráfico forward se deniega por defecto.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
