<template>
  <div
    :class="[
      'bg-gh-card border rounded-lg px-4 py-3 flex flex-col gap-2',
      isExpiringSoon ? 'border-gh-yellow' : 'border-gh-border'
    ]"
  >
    <!-- Dominio -->
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="text-gh-text text-sm font-mono font-semibold">{{ cert.domain }}</p>
        <p v-if="cert.wildcard" class="text-gh-muted text-xs font-mono mt-0.5">*.{{ cert.domain }}</p>
      </div>
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gh-muted flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    </div>

    <!-- Expiracion -->
    <div class="flex items-center gap-1.5">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        :class="['w-3.5 h-3.5 flex-shrink-0', isExpiringSoon ? 'text-gh-yellow' : 'text-gh-muted']"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
      <span
        v-if="cert.expires"
        :class="['text-xs', isExpiringSoon ? 'text-gh-yellow font-medium' : 'text-gh-muted']"
      >
        {{ isExpiringSoon ? 'Expira pronto: ' : 'Expira: ' }}{{ formatDate(cert.expires) }}
      </span>
      <span v-else class="text-xs text-gh-muted">Expiracion no disponible</span>
    </div>

    <!-- Descarga de keystore -->
    <a
      v-if="cert.keystore"
      :href="downloadCertStoreUrl(cert.keystore)"
      download
      class="flex items-center gap-1.5 text-xs text-gh-blue hover:underline w-fit mt-1"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Descargar {{ cert.keystore }}
    </a>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { downloadCertStoreUrl } from '../api.js'

const props = defineProps({
  cert: {
    type: Object,
    required: true
  }
})

const isExpiringSoon = computed(() => {
  if (!props.cert.expires) return false
  const exp  = new Date(props.cert.expires)
  const now  = new Date()
  const diff = (exp - now) / (1000 * 60 * 60 * 24)
  return diff < 30 && diff > 0
})

function formatDate(dateStr) {
  if (!dateStr) return 'no disponible'
  try {
    return new Date(dateStr).toLocaleDateString('es-ES', {
      year: 'numeric', month: 'short', day: 'numeric'
    })
  } catch {
    return dateStr
  }
}
</script>
