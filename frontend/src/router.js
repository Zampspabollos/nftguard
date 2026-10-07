import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "./api.js";

const routes = [
  { path: "/login", name: "login", component: () => import("./views/Login.vue"), meta: { public: true } },
  { path: "/setup", name: "setup", component: () => import("./views/Setup.vue"), meta: { public: true } },
  { path: "/", name: "dashboard", component: () => import("./views/Dashboard.vue") },
  { path: "/rules", name: "rules", component: () => import("./views/Rules.vue") },
  { path: "/nat", name: "nat", component: () => import("./views/PortForwards.vue") },
  { path: "/suricata", name: "suricata", component: () => import("./views/Suricata.vue") },
  { path: "/wireguard", name: "wireguard", component: () => import("./views/WireGuard.vue") },
  { path: "/users", name: "users", component: () => import("./views/Users.vue") },
  { path: "/audit", name: "audit", component: () => import("./views/Audit.vue") },
  { path: "/backup", name: "backup", component: () => import("./views/Backup.vue") },
  { path: "/account", name: "account", component: () => import("./views/Account.vue") },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
});

export default router;
