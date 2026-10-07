<script setup>
import { ref } from "vue";
import { apiFetch } from "../api.js";

const banner = ref(null);
const exporting = ref(false);
const restoring = ref(false);
const fileInput = ref(null);

async function downloadBackup() {
  exporting.value = true;
  banner.value = null;
  try {
    const data = await apiFetch("/backup");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nftguard-backup-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    exporting.value = false;
  }
}

function pickFile() {
  fileInput.value?.click();
}

async function restoreFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;

  if (
    !confirm(
      "Esto SUSTITUYE toda la configuración actual (reglas, NAT, Suricata, WireGuard, usuarios) " +
        "por la del backup. No se aplica automáticamente a nftables/Suricata/WireGuard: tendrás " +
        "que volver a aplicar/reiniciar cada servicio después. ¿Continuar?",
    )
  ) {
    return;
  }

  restoring.value = true;
  banner.value = null;
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    await apiFetch("/backup/restore", { method: "POST", body: data });
    banner.value = {
      type: "ok",
      message: "Backup restaurado. Revisa Reglas/Suricata/WireGuard y vuelve a aplicar cada uno.",
    };
  } catch (e) {
    banner.value = { type: "error", message: e.message || "El fichero no es un JSON válido" };
  } finally {
    restoring.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">Backup / Restauración</h1>
  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>

  <div class="card">
    <h2>Exportar</h2>
    <p style="color: var(--text-dim)">
      Descarga toda la configuración (reglas, NAT, Suricata, WireGuard, usuarios) en un único
      fichero JSON. <strong>Es un fichero sensible</strong>: incluye hashes de contraseña y las
      claves privadas de WireGuard. Guárdalo con el mismo cuidado que la base de datos.
    </p>
    <div class="btn-row">
      <button class="btn" :disabled="exporting" @click="downloadBackup">
        {{ exporting ? "Generando..." : "Descargar backup" }}
      </button>
    </div>
  </div>

  <div class="card">
    <h2>Restaurar</h2>
    <p style="color: var(--text-dim)">
      Sustituye toda la configuración actual por la de un fichero de backup. No reinicia
      nftables/Suricata/WireGuard automáticamente.
    </p>
    <input ref="fileInput" type="file" accept="application/json" style="display: none" @change="restoreFile" />
    <div class="btn-row">
      <button class="btn danger" :disabled="restoring" @click="pickFile">
        {{ restoring ? "Restaurando..." : "Elegir fichero y restaurar" }}
      </button>
    </div>
  </div>
</template>
