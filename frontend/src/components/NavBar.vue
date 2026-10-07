<script setup>
import { useRouter } from "vue-router";
import { clearToken } from "../api.js";
import { authUser } from "../auth.js";

const router = useRouter();

function logout() {
  clearToken();
  router.push({ name: "login" });
}
</script>

<template>
  <nav class="navbar">
    <div class="brand">nftguard</div>
    <router-link :to="{ name: 'dashboard' }">Dashboard</router-link>
    <router-link :to="{ name: 'rules' }">Reglas</router-link>
    <router-link :to="{ name: 'nat' }">NAT / Port-forward</router-link>
    <router-link :to="{ name: 'suricata' }">Suricata (L7)</router-link>
    <router-link :to="{ name: 'wireguard' }">WireGuard (VPN)</router-link>
    <router-link v-if="authUser.is_admin" :to="{ name: 'users' }">Usuarios</router-link>
    <router-link v-if="authUser.is_admin" :to="{ name: 'audit' }">Auditoría</router-link>
    <router-link v-if="authUser.is_admin" :to="{ name: 'backup' }">Backup</router-link>
    <router-link :to="{ name: 'account' }">Mi cuenta</router-link>
    <div class="spacer"></div>
    <button class="btn secondary" @click="logout">Cerrar sesión</button>
  </nav>
</template>
