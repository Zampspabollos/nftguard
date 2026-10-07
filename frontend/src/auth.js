import { reactive } from "vue";
import { apiFetch } from "./api.js";

export const authUser = reactive({ username: null, is_admin: false, loaded: false });

export async function loadAuthUser() {
  try {
    const me = await apiFetch("/auth/me");
    Object.assign(authUser, me, { loaded: true });
  } catch {
    authUser.loaded = false;
  }
}
