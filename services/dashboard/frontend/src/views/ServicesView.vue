<template>
  <div class="flex flex-col h-full">
    <!-- Header de seccion -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gh-border flex-shrink-0">
      <div>
        <h1 class="text-gh-text text-lg font-semibold">Servicios</h1>
        <p class="text-gh-muted text-xs mt-0.5">{{ headerSubtitle }}</p>
      </div>
      <button
        @click="fetchAll"
        :disabled="loading && !services.length && !core.length"
        class="flex items-center gap-2 px-3 py-1.5 text-xs border border-gh-border text-gh-muted hover:text-gh-text hover:border-gh-text rounded transition-colors disabled:opacity-50"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Actualizar
      </button>
    </div>

    <!-- Contenido -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Spinner inicial -->
      <div v-if="loading && !services.length && !core.length" class="flex items-center justify-center h-48">
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
        <button @click="fetchAll" class="text-xs text-gh-blue hover:underline">Reintentar</button>
      </div>

      <template v-else>
        <div v-for="group in visibleGroups" :key="group.id" class="mb-8 last:mb-0">
          <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-3">{{ group.label }}</p>

          <div
            v-if="group.items.length"
            :class="group.id === 'core'
              ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3'
              : 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4'"
          >
            <template v-for="svc in group.items" :key="svc.id">
              <CoreServiceCard
                v-if="svc.isCore"
                :service="svc"
                @open-logs="(containers) => openLogs(group.id, containers)"
                @refresh="fetchAll"
              />
              <ServiceCard
                v-else
                :service="svc"
                @open-logs="(containers) => openLogs(group.id, containers)"
                @refresh="fetchAll"
              />
            </template>
            <LocalstackServicesGrid v-if="group.id === 'aws' && runningOptionalIds.includes('localstack')" />
          </div>
          <p v-else class="text-gh-muted text-xs opacity-50">No hay servicios en esta categoria.</p>

          <LogsPanel
            v-if="logsGroupId === group.id"
            :containers="logsContainers"
            @close="logsGroupId = null"
          />

          <CategoryDetails :category="group.id" :running-ids="runningOptionalIds" />
        </div>

        <p v-if="!visibleGroups.length" class="text-gh-muted text-sm">No hay categorias que mostrar.</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ServiceCard from '../components/ServiceCard.vue'
import CoreServiceCard from '../components/CoreServiceCard.vue'
import CategoryDetails from '../components/CategoryDetails.vue'
import LocalstackServicesGrid from '../components/LocalstackServicesGrid.vue'
import LogsPanel from '../components/LogsPanel.vue'
import { getServices, getCoreServices, getServiceCategories } from '../api.js'

const props = defineProps({
  category: { type: String, default: 'all' },
})

const logsGroupId    = ref(null)
const logsContainers = ref([])

function openLogs(groupId, containers) {
  logsGroupId.value    = groupId
  logsContainers.value = containers
}

// Fallback por si /api/service-categories no responde: mismo orden y ids que el backend
const FALLBACK_CATEGORIES = [
  { id: 'core',       label: 'Core' },
  { id: 'aws',        label: 'AWS' },
  { id: 'db',         label: 'Base de datos' },
  { id: 'mensajeria', label: 'Mensajeria' },
]

const services   = ref([])
const core       = ref([])
const categories = ref([])
const loading    = ref(false)
const error      = ref(null)
let   pollTimer  = null

async function fetchAll() {
  loading.value = true
  error.value   = null
  try {
    const [svc, coreSvc, cats] = await Promise.all([
      getServices(),
      getCoreServices(),
      getServiceCategories().catch(() => FALLBACK_CATEGORIES),
    ])
    services.value   = svc
    core.value       = coreSvc
    categories.value = cats
  } catch (e) {
    error.value = e.message || 'Error al obtener servicios'
  } finally {
    loading.value = false
  }
}

const runningOptionalIds = computed(() =>
  services.value.filter(s => s.status === 'running').map(s => s.id)
)

const groups = computed(() => {
  const cats = categories.value.length ? categories.value : FALLBACK_CATEGORIES
  return cats.map(c => ({
    id: c.id,
    label: c.label,
    items: [
      ...core.value.filter(s => s.category === c.id).map(s => ({ ...s, isCore: true })),
      ...services.value.filter(s => s.category === c.id).map(s => ({ ...s, isCore: false })),
    ],
  }))
})

const visibleGroups = computed(() =>
  props.category === 'all' ? groups.value : groups.value.filter(g => g.id === props.category)
)

const headerSubtitle = computed(() =>
  props.category === 'all'
    ? 'Estado de los contenedores del entorno local'
    : `Categoria: ${(groups.value.find(g => g.id === props.category) || {}).label || props.category}`
)

onMounted(() => {
  fetchAll()
  pollTimer = setInterval(fetchAll, 5000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>
