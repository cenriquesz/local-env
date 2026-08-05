<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gh-border flex-shrink-0">
      <div>
        <h1 class="text-gh-text text-lg font-semibold">Apps</h1>
        <p class="text-gh-muted text-xs mt-0.5">Aplicaciones externas detectadas en nginx</p>
      </div>
      <button
        @click="fetchApps"
        class="flex items-center gap-2 px-3 py-1.5 text-xs border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text rounded transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Actualizar
      </button>
    </div>

    <!-- Contenido -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Spinner -->
      <div v-if="loading" class="flex items-center justify-center h-48">
        <svg class="animate-spin w-8 h-8 text-gh-orange" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center h-48 gap-3">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-gh-red" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="text-gh-red text-sm">{{ error }}</p>
        <button @click="fetchApps" class="text-xs text-gh-blue hover:underline">Reintentar</button>
      </div>

      <!-- Estado vacio -->
      <div v-else-if="!apps.length" class="flex flex-col items-center justify-center h-48 gap-3 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-gh-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
        <p class="text-gh-text text-sm font-medium">No se detectaron apps externas</p>
        <p class="text-gh-muted text-xs max-w-xs">
          Añade un fichero .conf en
          <code class="font-mono text-gh-blue">services/nginx/etc/nginx/conf.d/http/</code>
          desde tu app.
        </p>
      </div>

      <!-- Grid de apps -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <AppCard
          v-for="app in apps"
          :key="app.name"
          :app="app"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppCard from '../components/AppCard.vue'
import { getApps } from '../api.js'

const apps    = ref([])
const loading = ref(false)
const error   = ref(null)

async function fetchApps() {
  loading.value = true
  error.value   = null
  try {
    apps.value = await getApps()
  } catch (e) {
    error.value = e.message || 'Error al obtener apps'
  } finally {
    loading.value = false
  }
}

onMounted(fetchApps)
</script>
