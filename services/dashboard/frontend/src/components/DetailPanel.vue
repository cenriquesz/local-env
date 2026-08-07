<template>
  <div class="bg-gh-card border border-gh-border rounded-lg">
    <div class="flex items-center justify-between px-4 py-3 border-b border-gh-border">
      <h4 class="text-gh-text font-semibold text-xs uppercase tracking-wide">{{ title }}</h4>
      <span v-if="subtitle" class="text-gh-muted text-xs font-mono opacity-50">{{ subtitle }}</span>
    </div>
    <div class="px-4 py-3">
      <div v-if="loading" class="text-gh-muted text-xs">Cargando...</div>
      <div v-else-if="error" class="text-gh-red text-xs">No disponible</div>
      <slot v-else :data="data" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: null },
  fetcher: { type: Function, required: true },
  pollMs: { type: Number, default: 15000 },
})

const loading = ref(true)
const error = ref(false)
const data = ref(null)
let timer = null

async function load() {
  try {
    data.value = await props.fetcher()
    error.value = false
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, props.pollMs)
})

onUnmounted(() => clearInterval(timer))

defineExpose({ reload: load })
</script>
