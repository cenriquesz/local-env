<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gh-border flex-shrink-0">
      <div>
        <h1 class="text-gh-text text-lg font-semibold">Certificados</h1>
        <p class="text-gh-muted text-xs mt-0.5">Certificados TLS gestionados por minica</p>
      </div>
      <button
        @click="handleRegenerate"
        :disabled="regenerating"
        class="flex items-center gap-2 px-3 py-1.5 text-xs border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text rounded transition-colors disabled:opacity-50"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        {{ regenerating ? 'Regenerando...' : 'Regenerar certs' }}
      </button>
    </div>

    <!-- Banner de confirmacion -->
    <Transition
      enter-active-class="transition-all duration-300"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-300"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="confirmMsg"
        :class="[
          'mx-6 mt-4 px-4 py-2 rounded border text-sm',
          confirmMsg.type === 'ok'
            ? 'bg-gh-green bg-opacity-10 border-gh-green text-gh-green'
            : 'bg-gh-red bg-opacity-10 border-gh-red text-gh-red'
        ]"
      >
        {{ confirmMsg.text }}
      </div>
    </Transition>

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
        <button @click="fetchCerts" class="text-xs text-gh-blue hover:underline">Reintentar</button>
      </div>

      <!-- Grid de certs -->
      <div v-else-if="certs.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <CertCard
          v-for="cert in certs"
          :key="cert.domain"
          :cert="cert"
        />
      </div>

      <!-- Sin certs -->
      <div v-else class="flex flex-col items-center justify-center h-48 gap-3 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-gh-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        <p class="text-gh-text text-sm font-medium">No hay certificados</p>
        <p class="text-gh-muted text-xs">minica generara los certs al iniciar los servicios</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CertCard from '../components/CertCard.vue'
import { getCerts, restartMinica } from '../api.js'

const certs       = ref([])
const loading     = ref(false)
const error       = ref(null)
const regenerating = ref(false)
const confirmMsg  = ref(null)

async function fetchCerts() {
  loading.value = true
  error.value   = null
  try {
    certs.value = await getCerts()
  } catch (e) {
    error.value = e.message || 'Error al obtener certificados'
  } finally {
    loading.value = false
  }
}

async function handleRegenerate() {
  regenerating.value = true
  try {
    await restartMinica()
    confirmMsg.value = { type: 'ok', text: 'minica reiniciado correctamente. Los certificados se regeneraran en breve.' }
    setTimeout(fetchCerts, 3000)
  } catch (e) {
    confirmMsg.value = { type: 'error', text: 'Error al reiniciar minica: ' + (e.message || 'error desconocido') }
  } finally {
    regenerating.value = false
    setTimeout(() => { confirmMsg.value = null }, 5000)
  }
}

onMounted(fetchCerts)
</script>
