<script setup>
import { onMounted, reactive, ref } from "vue";
import { apiFetch } from "../api.js";
import { authUser } from "../auth.js";

const users = ref([]);
const loading = ref(true);
const banner = ref(null);
const newUser = reactive({ username: "", password: "", is_admin: false });
const creating = ref(false);

async function load() {
  loading.value = true;
  try {
    users.value = await apiFetch("/users");
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function createUser() {
  creating.value = true;
  banner.value = null;
  try {
    await apiFetch("/users", { method: "POST", body: { ...newUser } });
    newUser.username = "";
    newUser.password = "";
    newUser.is_admin = false;
    await load();
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  } finally {
    creating.value = false;
  }
}

async function removeUser(user) {
  if (!confirm(`¿Eliminar el usuario "${user.username}"?`)) return;
  banner.value = null;
  try {
    await apiFetch(`/users/${user.id}`, { method: "DELETE" });
    await load();
  } catch (e) {
    banner.value = { type: "error", message: e.message };
  }
}
</script>

<template>
  <h1 class="page-title">Usuarios</h1>
  <div v-if="banner" :class="['banner', banner.type]">{{ banner.message }}</div>

  <div class="card">
    <h2>Cuentas ({{ users.length }})</h2>
    <p v-if="loading">Cargando...</p>
    <table v-else>
      <thead>
        <tr>
          <th>Usuario</th>
          <th>Rol</th>
          <th>Creado</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.username }}</td>
          <td>{{ u.is_admin ? "administrador" : "solo lectura" }}</td>
          <td>{{ new Date(u.created_at).toLocaleString() }}</td>
          <td>
            <button
              v-if="authUser.is_admin && u.username !== authUser.username"
              class="btn danger"
              @click="removeUser(u)"
            >
              Eliminar
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-if="authUser.is_admin" class="card">
    <h2>Nuevo usuario</h2>
    <div class="form-grid">
      <div>
        <label>Usuario</label>
        <input v-model="newUser.username" minlength="3" maxlength="32" />
      </div>
      <div>
        <label>Contraseña</label>
        <input v-model="newUser.password" type="password" minlength="8" />
      </div>
      <div class="checkbox-row" style="align-items: flex-end; padding-bottom: 8px">
        <input id="new-is-admin" v-model="newUser.is_admin" type="checkbox" />
        <label for="new-is-admin" style="margin: 0">Administrador (puede modificar todo)</label>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn" :disabled="creating || !newUser.username || !newUser.password" @click="createUser">
        + Crear usuario
      </button>
    </div>
  </div>
</template>
