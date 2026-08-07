<template>
  <div class="flex h-screen overflow-hidden bg-gh-bg">

    <!-- Sidebar -->
    <aside class="w-60 flex-shrink-0 bg-[#010409] border-r border-gh-border flex flex-col">
      <!-- Logo -->
      <div class="px-4 pt-5 pb-4 border-b border-gh-border">
        <div class="flex items-center gap-2.5">
          <div class="w-7 h-7 bg-gh-orange rounded flex items-center justify-center flex-shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
          <div>
            <p class="text-gh-orange font-bold text-sm leading-tight">local-env</p>
            <p class="text-gh-muted text-xs leading-tight">dashboard</p>
          </div>
        </div>
      </div>

      <!-- Salud del entorno -->
      <EnvironmentHealth />

      <!-- Navegacion -->
      <nav class="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        <template v-for="item in navItems" :key="item.id">
          <button
            @click="selectView(item.id)"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2 rounded text-sm text-left transition-colors',
              currentView === item.id
                ? 'bg-gh-border text-gh-text font-medium'
                : 'text-gh-muted hover:text-gh-text hover:bg-gh-border hover:bg-opacity-50'
            ]"
          >
            <span class="flex-shrink-0 w-4 h-4" v-html="item.icon"></span>
            {{ item.label }}
          </button>

          <!-- Sub-navegacion por categoria, solo bajo Servicios -->
          <div v-if="item.id === 'services' && currentView === 'services'" class="pl-6 pb-1 space-y-0.5">
            <button
              v-for="cat in serviceCategories"
              :key="cat.id"
              @click="serviceCategory = cat.id"
              :class="[
                'w-full flex items-center px-3 py-1.5 rounded text-xs text-left transition-colors',
                serviceCategory === cat.id
                  ? 'text-gh-orange font-medium'
                  : 'text-gh-muted hover:text-gh-text'
              ]"
            >
              {{ cat.label }}
            </button>
          </div>
        </template>
      </nav>

      <!-- QuickActionsBar al fondo del sidebar -->
      <QuickActionsBar />
    </aside>

    <!-- Contenido principal -->
    <main class="flex-1 overflow-hidden flex flex-col">
      <ServicesView
        v-show="currentView === 'services'"
        :category="serviceCategory"
      />
      <AppsView
        v-show="currentView === 'apps'"
        @open-api="openApi"
      />
      <CertsView
        v-show="currentView === 'certs'"
      />
      <ApiView
        v-show="currentView === 'api'"
      />
    </main>

    <!-- ApiModal global (spec de apps externas) -->
    <ApiModal
      :domain="apiModalDomain"
      v-model="apiModalOpen"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ServicesView from './views/ServicesView.vue'
import AppsView from './views/AppsView.vue'
import CertsView from './views/CertsView.vue'
import ApiView from './views/ApiView.vue'
import ApiModal from './components/ApiModal.vue'
import QuickActionsBar from './components/QuickActionsBar.vue'
import EnvironmentHealth from './components/EnvironmentHealth.vue'

const currentView     = ref('services')
const serviceCategory = ref('all')
const apiModalOpen    = ref(false)
const apiModalDomain  = ref(null)

function selectView(id) {
  currentView.value = id
  if (id === 'services') serviceCategory.value = 'all'
}

const serviceCategories = [
  { id: 'core',       label: 'Core' },
  { id: 'aws',        label: 'AWS' },
  { id: 'db',         label: 'Base de datos' },
  { id: 'mensajeria', label: 'Mensajeria' },
]

function openApi(domain) {
  apiModalDomain.value = domain
  apiModalOpen.value   = true
}

const iconServices = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M5 6h14M5 18h14" />
</svg>`

const iconApps = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
</svg>`

const iconCerts = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
</svg>`

const iconApi = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 8l-4 4 4 4" />
</svg>`

const navItems = [
  { id: 'services', label: 'Servicios',      icon: iconServices },
  { id: 'apps',     label: 'Apps',            icon: iconApps },
  { id: 'certs',    label: 'Certificados',    icon: iconCerts },
  { id: 'api',      label: 'API',             icon: iconApi },
]
</script>
