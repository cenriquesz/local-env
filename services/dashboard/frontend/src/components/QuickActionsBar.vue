<template>
  <div class="border-t border-gh-border px-3 py-3 space-y-2">
    <p class="text-gh-muted text-xs font-medium uppercase tracking-wide px-1 mb-1">Acciones rapidas</p>

    <!-- Recargar nginx -->
    <button
      @click="handleNginx"
      :disabled="nginxState === 'loading'"
      class="w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs text-gh-muted hover:text-gh-text hover:bg-gh-border transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      <span :class="nginxLabelClass">{{ nginxLabel }}</span>
    </button>

    <!-- Reiniciar minica -->
    <button
      @click="handleMinica"
      :disabled="minicaState === 'loading'"
      class="w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs text-gh-muted hover:text-gh-text hover:bg-gh-border transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
      <span :class="minicaLabelClass">{{ minicaLabel }}</span>
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { reloadNginx, restartMinica } from '../api.js'

const nginxState  = ref('idle')   // idle | loading | ok | error
const minicaState = ref('idle')

const nginxLabel = computed(() => {
  if (nginxState.value === 'loading') return '...'
  if (nginxState.value === 'ok')      return 'OK'
  if (nginxState.value === 'error')   return 'Error'
  return 'Recargar nginx'
})

const minicaLabel = computed(() => {
  if (minicaState.value === 'loading') return '...'
  if (minicaState.value === 'ok')      return 'OK'
  if (minicaState.value === 'error')   return 'Error'
  return 'Reiniciar minica'
})

const nginxLabelClass = computed(() => {
  if (nginxState.value === 'ok')    return 'text-gh-green'
  if (nginxState.value === 'error') return 'text-gh-red'
  return ''
})

const minicaLabelClass = computed(() => {
  if (minicaState.value === 'ok')    return 'text-gh-green'
  if (minicaState.value === 'error') return 'text-gh-red'
  return ''
})

async function runAction(stateRef, apiFn) {
  stateRef.value = 'loading'
  try {
    await apiFn()
    stateRef.value = 'ok'
  } catch {
    stateRef.value = 'error'
  }
  setTimeout(() => { stateRef.value = 'idle' }, 2000)
}

function handleNginx()  { runAction(nginxState,  reloadNginx) }
function handleMinica() { runAction(minicaState, restartMinica) }
</script>
