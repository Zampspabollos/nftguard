<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
  initial: { type: Object, default: null },
});
const emit = defineEmits(["save", "cancel"]);

function blank() {
  return {
    priority: 100,
    enabled: true,
    chain: "forward",
    action: "accept",
    protocol: "any",
    src_iface: "",
    dst_iface: "",
    src_ip: "",
    dst_ip: "",
    src_port: "",
    dst_port: "",
    rate_limit: "",
    log: false,
    inspect_l7: false,
    comment: "",
  };
}

const form = reactive(blank());

watch(
  () => props.initial,
  (val) => {
    Object.assign(form, blank(), val || {});
  },
  { immediate: true },
);

function emptyToNull(value) {
  return value === "" ? null : value;
}

function submit() {
  emit("save", {
    priority: Number(form.priority),
    enabled: form.enabled,
    chain: form.chain,
    action: form.action,
    protocol: form.protocol,
    src_iface: emptyToNull(form.src_iface),
    dst_iface: emptyToNull(form.dst_iface),
    src_ip: emptyToNull(form.src_ip),
    dst_ip: emptyToNull(form.dst_ip),
    src_port: emptyToNull(form.src_port),
    dst_port: emptyToNull(form.dst_port),
    rate_limit: emptyToNull(form.rate_limit),
    log: form.log,
    inspect_l7: form.inspect_l7,
    comment: emptyToNull(form.comment),
  });
}
</script>

<template>
  <form class="card" @submit.prevent="submit">
    <h2>{{ initial ? "Editar regla" : "Nueva regla" }}</h2>

    <div class="form-grid">
      <div>
        <label>Cadena</label>
        <select v-model="form.chain">
          <option value="forward">forward (tráfico enrutado)</option>
          <option value="input">input (hacia el propio firewall)</option>
        </select>
      </div>
      <div>
        <label>Acción</label>
        <select v-model="form.action" :disabled="form.inspect_l7">
          <option value="accept">accept</option>
          <option value="drop">drop</option>
          <option value="reject">reject</option>
        </select>
      </div>
      <div>
        <label>Protocolo</label>
        <select v-model="form.protocol">
          <option value="any">any</option>
          <option value="tcp">tcp</option>
          <option value="udp">udp</option>
          <option value="icmp">icmp</option>
        </select>
      </div>
      <div>
        <label>Prioridad (orden)</label>
        <input v-model="form.priority" type="number" required />
      </div>
    </div>

    <div class="form-grid">
      <div>
        <label>Interfaz origen</label>
        <input v-model="form.src_iface" placeholder="ej. eth1" />
      </div>
      <div>
        <label>Interfaz destino</label>
        <input v-model="form.dst_iface" placeholder="ej. eth0" />
      </div>
      <div>
        <label>IP/CIDR origen</label>
        <input v-model="form.src_ip" placeholder="ej. 192.168.10.0/24" />
      </div>
      <div>
        <label>IP/CIDR destino</label>
        <input v-model="form.dst_ip" placeholder="ej. 10.0.0.5" />
      </div>
    </div>

    <div class="form-grid">
      <div>
        <label>Puerto origen</label>
        <input v-model="form.src_port" placeholder="solo con tcp/udp" :disabled="form.protocol === 'any'" />
      </div>
      <div>
        <label>Puerto destino</label>
        <input v-model="form.dst_port" placeholder="ej. 443 o 1000-2000" :disabled="form.protocol === 'any'" />
      </div>
      <div>
        <label>Límite de tasa</label>
        <input v-model="form.rate_limit" placeholder="ej. 10/minute" />
      </div>
      <div>
        <label>Comentario</label>
        <input v-model="form.comment" maxlength="120" />
      </div>
    </div>

    <div class="form-grid">
      <div class="checkbox-row">
        <input id="enabled" v-model="form.enabled" type="checkbox" />
        <label for="enabled" style="margin: 0">Activa</label>
      </div>
      <div class="checkbox-row">
        <input id="log" v-model="form.log" type="checkbox" />
        <label for="log" style="margin: 0">Registrar en log</label>
      </div>
      <div class="checkbox-row">
        <input id="inspect_l7" v-model="form.inspect_l7" type="checkbox" :disabled="form.protocol === 'any'" />
        <label for="inspect_l7" style="margin: 0">Inspeccionar con Suricata (L7)</label>
      </div>
    </div>
    <p v-if="form.inspect_l7" style="color: var(--text-dim); font-size: 12px; margin: -8px 0 14px">
      El tráfico nuevo que coincida se desvía a Suricata; es Suricata quien decide aceptar o
      bloquear según sus firmas, no la acción de arriba. Si Suricata está deshabilitado
      globalmente, esta regla usa su acción normal como respaldo.
    </p>

    <div class="btn-row">
      <button class="btn" type="submit">Guardar</button>
      <button class="btn secondary" type="button" @click="emit('cancel')">Cancelar</button>
    </div>
  </form>
</template>
