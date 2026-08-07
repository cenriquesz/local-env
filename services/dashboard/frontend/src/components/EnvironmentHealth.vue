<template>
  <div class="px-4 py-3 border-b border-gh-border">
    <div v-if="loading" class="text-gh-muted text-xs">Comprobando entorno...</div>
    <div v-else-if="error" class="flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-gh-red flex-shrink-0"></span>
      <span class="text-gh-red text-xs font-medium">Dashboard no disponible</span>
    </div>
    <template v-else>
      <div class="flex items-center gap-2">
        <span :class="dotClass" class="w-2 h-2 rounded-full flex-shrink-0"></span>
        <span :class="textClass" class="text-xs font-medium">{{ label }}</span>
      </div>
      <ul v-if="unhealthyCore.length" class="mt-1.5 space-y-1 pl-4">
        <li v-for="c in unhealthyCore" :key="c.id" class="flex items-center justify-between gap-2">
          <span class="text-gh-muted text-xs truncate">{{ c.label }}</span>
          <StatusBadge :status="c.status" />
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getHealth } from '../api.js'
import StatusBadge from './StatusBadge.vue'

const loading = ref(true)
const error   = ref(false)
const status  = ref('unknown')
const core    = ref([])

let timer = null

async function fetchHealth() {
  try {
    const data = await getHealth()
    status.value = data.status
    core.value = data.core ?? []
    error.value = false
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHealth()
  timer = setInterval(fetchHealth, 15000)
})

onUnmounted(() => clearInterval(timer))

const unhealthyCore = computed(() => core.value.filter(c => !['running', 'idle'].includes(c.status)))

const label = computed(() => status.value === 'healthy' ? 'Entorno OK' : 'Entorno degradado')
const dotClass = computed(() => status.value === 'healthy' ? 'bg-gh-green' : 'bg-gh-yellow')
const textClass = computed(() => status.value === 'healthy' ? 'text-gh-green' : 'text-gh-yellow')
</script>
