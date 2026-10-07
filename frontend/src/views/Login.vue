<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { apiFetch, login } from "../api.js";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

onMounted(async () => {
  try {
    const { needs_setup } = await apiFetch("/auth/needs-setup", { auth: false });
    if (needs_setup) router.replace({ name: "setup" });
  } catch {
    /* backend no disponible: dejamos el formulario, el submit mostrará el error */
  }
});

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    await login(username.value, password.value);
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
      <h1>nftguard</h1>
      <p class="subtitle">Inicia sesión para gestionar el firewall.</p>
      <div v-if="error" class="banner error">{{ error }}</div>
      <div class="field">
        <label>Usuario</label>
        <input v-model="username" required autofocus />
      </div>
      <div class="field">
        <label>Contraseña</label>
        <input v-model="password" type="password" required />
      </div>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? "Entrando..." : "Entrar" }}
      </button>
    </form>
  </div>
</template>
