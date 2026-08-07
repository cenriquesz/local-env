<template>
  <div class="bg-gh-card border border-gh-border rounded-lg px-3 py-2.5 flex items-center gap-3">
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1">
        <h3 class="text-gh-text font-semibold text-xs tracking-wide uppercase truncate">{{ service.label }}</h3>
        <StatusBadge :status="service.status" />
      </div>
      <div v-if="service.containers && service.containers.length" class="flex flex-wrap gap-x-3 gap-y-0.5">
        <span
          v-for="c in service.containers"
          :key="c.name"
          class="flex items-center gap-1 text-gh-muted text-xs font-mono truncate"
          :title="c.image || c.name"
        >
          <span :class="dotClass(c.status)" class="w-1.5 h-1.5 rounded-full inline-block flex-shrink-0"></span>
          {{ c.name }}
        </span>
      </div>
    </div>

    <div class="flex items-center gap-1 flex-shrink-0">
      <button
        @click="handleRestart"
        :disabled="loading"
        :title="loading ? 'Reiniciando...' : 'Reiniciar'"
        class="p-1.5 rounded border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
      <button
        @click="openLogs"
        title="Logs"
        class="p-1.5 rounded border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { restartCoreService } from '../api.js'

const props = defineProps({
  service: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['open-logs', 'refresh'])

const loading = ref(false)

const DOT_COLORS = {
  running: 'bg-gh-green',
  idle: 'bg-gh-blue',
  stopped: 'bg-gh-muted',
  partial: 'bg-gh-yellow',
  error: 'bg-gh-red',
  not_found: 'bg-gh-red',
  unknown: 'bg-gh-muted',
}

function normalizeContainerStatus(raw) {
  if (!raw) return 'unknown'
  if (raw === 'idle' || raw === 'error') return raw
  const s = raw.toLowerCase()
  if (s.includes('up') || s.includes('running')) return 'running'
  if (s.includes('exit') || s.includes('stopped')) return 'stopped'
  return 'unknown'
}

function dotClass(rawStatus) {
  return DOT_COLORS[normalizeContainerStatus(rawStatus)]
}

async function handleRestart() {
  loading.value = true
  try {
    await restartCoreService(props.service.id)
  } finally {
    loading.value = false
    emit('refresh')
  }
}

function openLogs() {
  const containers = (props.service.containers || []).map(c => c.name)
  emit('open-logs', containers)
}
</script>
