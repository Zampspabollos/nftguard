<script setup>
import { computed, watch } from "vue";
import { useRoute } from "vue-router";
import NavBar from "./components/NavBar.vue";
import { loadAuthUser } from "./auth.js";

const route = useRoute();
const isPublic = computed(() => route.meta.public === true);

watch(
  isPublic,
  (pub) => {
    if (!pub) loadAuthUser();
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="isPublic">
    <router-view />
  </div>
  <div v-else class="layout">
    <NavBar />
    <div class="content">
      <router-view />
    </div>
  </div>
</template>
