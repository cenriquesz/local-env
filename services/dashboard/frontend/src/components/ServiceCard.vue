<template>
  <div class="bg-gh-card border border-gh-border rounded-lg flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gh-border">
      <h3 class="text-gh-text font-semibold text-sm tracking-wide uppercase">{{ service.label }}</h3>
      <StatusBadge :status="service.status" />
    </div>

    <!-- URLs -->
    <div v-if="service.urls && service.urls.length" class="px-4 py-3 border-b border-gh-border space-y-1.5">
      <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-2">URLs</p>
      <div v-for="u in service.urls" :key="u.url" class="flex items-center gap-2 group">
        <a
          :href="u.url"
          target="_blank"
          rel="noopener noreferrer"
          class="text-gh-blue text-xs font-mono hover:underline flex-1 truncate"
          :title="u.url"
        >{{ u.url }}</a>
        <button
          @click="copyUrl(u.url)"
          :title="'Copiar ' + u.url"
          class="flex-shrink-0 text-gh-muted hover:text-gh-text transition-colors opacity-0 group-hover:opacity-100"
        >
          <span v-if="copiedUrl === u.url" class="text-gh-green text-xs">Copiado</span>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Containers -->
    <div v-if="service.containers && service.containers.length" class="px-4 py-3 border-b border-gh-border space-y-2">
      <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-2">Contenedores</p>
      <div v-for="c in service.containers" :key="c.name" class="space-y-0.5">
        <div class="flex items-center justify-between">
          <span class="text-gh-muted text-xs font-mono truncate flex-1 mr-2">{{ c.name }}</span>
          <StatusBadge :status="normalizeContainerStatus(c.status)" />
        </div>
        <div v-if="c.image || c.expected_image" class="flex items-center gap-1.5 pl-0">
          <span class="text-gh-muted text-xs font-mono opacity-60 truncate">{{ shortImage(c.image || c.expected_image) }}</span>
          <span
            v-if="c.up_to_date === true"
            class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gh-green bg-opacity-15 text-gh-green"
          >al dia</span>
          <span
            v-else-if="c.up_to_date === false"
            class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gh-yellow bg-opacity-15 text-gh-yellow"
            :title="'Esperado: ' + c.expected_image"
          >desactualizado</span>
        </div>
      </div>
    </div>

    <!-- Footer actions -->
    <div class="px-4 py-3 flex items-center gap-2 mt-auto">
      <button
        v-if="canStart"
        @click="handleStart"
        :disabled="loading"
        class="flex-1 px-3 py-1.5 text-xs font-medium rounded border border-gh-green text-gh-green hover:bg-gh-green hover:text-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ loading === 'start' ? 'Iniciando...' : 'Iniciar' }}
      </button>
      <button
        v-if="canStop"
        @click="handleStop"
        :disabled="loading"
        class="flex-1 px-3 py-1.5 text-xs font-medium rounded border border-gh-red text-gh-red hover:bg-gh-red hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ loading === 'stop' ? 'Deteniendo...' : 'Detener' }}
      </button>
      <button
        @click="openLogs"
        class="flex-1 px-3 py-1.5 text-xs font-medium rounded border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text transition-colors flex items-center justify-center gap-1.5"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Logs
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { startService, stopService } from '../api.js'

const props = defineProps({
  service: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['open-logs', 'refresh'])

const loading   = ref(null)
const copiedUrl = ref(null)

const canStart = computed(() => ['stopped', 'not_found'].includes(props.service.status))
const canStop  = computed(() => ['running', 'partial'].includes(props.service.status))

function normalizeContainerStatus(raw) {
  if (!raw) return 'unknown'
  const s = raw.toLowerCase()
  if (s.includes('up') || s.includes('running')) return 'running'
  if (s.includes('exit') || s.includes('stopped')) return 'stopped'
  return 'unknown'
}

function shortImage(image) {
  if (!image) return ''
  // "confluentinc/cp-kafka:8.2.2" -> "cp-kafka:8.2.2"
  const parts = image.split('/')
  return parts[parts.length - 1]
}

async function handleStart() {
  loading.value = 'start'
  try {
    await startService(props.service.id)
    emit('refresh')
  } finally {
    loading.value = null
  }
}

async function handleStop() {
  loading.value = 'stop'
  try {
    await stopService(props.service.id)
    emit('refresh')
  } finally {
    loading.value = null
  }
}

function openLogs() {
  const containers = (props.service.containers || []).map(c => c.name)
  emit('open-logs', containers)
}

async function copyUrl(url) {
  try {
    await navigator.clipboard.writeText(url)
    copiedUrl.value = url
    setTimeout(() => { copiedUrl.value = null }, 2000)
  } catch {
    // fallback silencioso
  }
}
</script>
