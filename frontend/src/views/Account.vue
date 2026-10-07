<script setup>
import { reactive, ref } from "vue";
import { apiFetch } from "../api.js";
import { authUser } from "../auth.js";

const form = reactive({ current_password: "", new_password: "", confirm: "" });
const banner = ref(null);
const saving = ref(false);

async function submit() {
  banner.value = null;
  if (form.new_password !== form.confirm) {
    banner.value = { type: "error", message: "Las contraseñas nuevas no coinciden" };
    return;
  }
  saving.value = true;
  try {
    await apiFetch("/auth/password", {
      method: "PUT",
      body: { current_password: form.current_password, new_password: form.new_password },
    });
    form.current_password = "";
    form.new_password = "";
    form.confirm = "";
    banner.value = { type: "ok", message: "Contraseña actualizada." };
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">Mi cuenta</h1>
  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>

  <div class="card">
    <h2>Sesión</h2>
    <p>
      Usuario: <strong>{{ authUser.username }}</strong> ·
      Rol: {{ authUser.is_admin ? "administrador" : "solo lectura" }}
    </p>
  </div>

  <form class="card" @submit.prevent="submit">
    <h2>Cambiar contraseña</h2>
    <div class="form-grid">
      <div>
        <label>Contraseña actual</label>
        <input v-model="form.current_password" type="password" required />
      </div>
      <div>
        <label>Contraseña nueva</label>
        <input v-model="form.new_password" type="password" minlength="8" required />
      </div>
      <div>
        <label>Confirmar contraseña nueva</label>
        <input v-model="form.confirm" type="password" minlength="8" required />
      </div>
    </div>
    <div class="btn-row">
      <button class="btn" type="submit" :disabled="saving">{{ saving ? "Guardando..." : "Cambiar contraseña" }}</button>
    </div>
  </form>
</template>
