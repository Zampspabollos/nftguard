<script setup>
import { reactive } from "vue";

const emit = defineEmits(["save", "cancel"]);

const form = reactive({
  enabled: true,
  protocol: "tcp",
  wan_port: "",
  dst_ip: "",
  dst_port: "",
  comment: "",
});

function submit() {
  emit("save", {
    enabled: form.enabled,
    protocol: form.protocol,
    wan_port: form.wan_port,
    dst_ip: form.dst_ip,
    dst_port: form.dst_port,
    comment: form.comment || null,
  });
}
</script>

<template>
  <form class="card" @submit.prevent="submit">
    <h2>Nueva redirección de puerto</h2>
    <div class="form-grid">
      <div>
        <label>Protocolo</label>
        <select v-model="form.protocol">
          <option value="tcp">tcp</option>
          <option value="udp">udp</option>
        </select>
      </div>
      <div>
        <label>Puerto en WAN</label>
        <input v-model="form.wan_port" placeholder="ej. 8080" required />
      </div>
      <div>
        <label>IP destino (LAN)</label>
        <input v-model="form.dst_ip" placeholder="ej. 192.168.10.50" required />
      </div>
      <div>
        <label>Puerto destino</label>
        <input v-model="form.dst_port" placeholder="ej. 80" required />
      </div>
    </div>
    <div class="form-grid">
      <div>
        <label>Comentario</label>
        <input v-model="form.comment" maxlength="120" />
      </div>
      <div class="checkbox-row">
        <input id="pf-enabled" v-model="form.enabled" type="checkbox" />
        <label for="pf-enabled" style="margin: 0">Activa</label>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn" type="submit">Guardar</button>
      <button class="btn secondary" type="button" @click="emit('cancel')">Cancelar</button>
    </div>
  </form>
</template>
