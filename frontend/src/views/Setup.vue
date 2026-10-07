<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { apiFetch, setToken } from "../api.js";

const router = useRouter();
const username = ref("admin");
const password = ref("");
const confirm = ref("");
const error = ref("");
const loading = ref(false);

onMounted(async () => {
  try {
    const { needs_setup } = await apiFetch("/auth/needs-setup", { auth: false });
    if (!needs_setup) router.replace({ name: "login" });
  } catch {
    /* si falla la comprobación, dejamos el formulario visible */
  }
});

async function submit() {
  error.value = "";
  if (password.value !== confirm.value) {
    error.value = "Las contraseñas no coinciden";
    return;
  }
  loading.value = true;
  try {
    const data = await apiFetch("/auth/setup", {
      method: "POST",
      auth: false,
      body: { username: username.value, password: password.value },
    });
    setToken(data.access_token);
    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-screen">
    <form class="auth-card" @submit.prevent="submit">
      <h1>Primer arranque</h1>
      <p class="subtitle">Crea el usuario administrador de nftguard.</p>
      <div v-if="error" class="banner error">{{ error }}</div>
      <div class="field">
        <label>Usuario</label>
        <input v-model="username" required minlength="3" maxlength="32" />
      </div>
      <div class="field">
        <label>Contraseña</label>
        <input v-model="password" type="password" required minlength="8" />
      </div>
      <div class="field">
        <label>Confirmar contraseña</label>
        <input v-model="confirm" type="password" required minlength="8" />
      </div>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? "Creando..." : "Crear administrador" }}
      </button>
    </form>
  </div>
</template>
