<template>
  <div class="px-4 py-3 border-b border-gh-border">
    <div class="flex items-center justify-between mb-2">
      <p class="text-gh-muted text-xs font-medium uppercase tracking-wide">Servicios AWS</p>
      <span v-if="version" class="text-gh-muted text-xs font-mono opacity-50">v{{ version }}</span>
    </div>

    <div v-if="loading" class="text-gh-muted text-xs">Cargando...</div>
    <div v-else-if="error" class="text-gh-red text-xs">No disponible</div>
    <template v-else>
      <!-- Servicios activos -->
      <div class="flex flex-wrap gap-1.5 mb-2">
        <span
          v-for="svc in running"
          :key="svc"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono bg-gh-green bg-opacity-10 text-gh-green"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-gh-green inline-block"></span>
          {{ svc }}
        </span>
      </div>
      <!-- Contador de disponibles -->
      <p class="text-gh-muted text-xs opacity-50">+ {{ available.length }} disponibles bajo demanda</p>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getLocalstackHealth } from '../api.js'

const loading = ref(true)
const error   = ref(false)
const running = ref([])
const available = ref([])
const version = ref(null)

let timer = null

async function fetch() {
  try {
    const data = await getLocalstackHealth()
    version.value = data.version ?? null
    const svcs = data.services ?? {}
    running.value   = Object.keys(svcs).filter(k => svcs[k] === 'running').map(k => k.toUpperCase())
    available.value = Object.keys(svcs).filter(k => svcs[k] === 'available')
    error.value = false
  } catch {
    error.value = true
    running.value = []
    available.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetch()
  timer = setInterval(fetch, 15000)
})

onUnmounted(() => clearInterval(timer))
</script>
