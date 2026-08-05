<template>
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-200"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 bg-black bg-opacity-70 flex items-center justify-center p-6"
      @click.self="close"
    >
      <div class="bg-white w-full h-full max-w-6xl rounded-lg overflow-hidden flex flex-col shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gh-border bg-[#010409] flex-shrink-0">
          <span class="text-gh-text text-sm font-semibold font-mono">{{ domain }}</span>
          <button
            @click="close"
            class="p-1.5 text-gh-muted hover:text-gh-text transition-colors rounded hover:bg-gh-border"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Contenido -->
        <div class="flex-1 overflow-y-auto">
          <div v-if="loading" class="flex items-center justify-center h-full">
            <svg class="animate-spin w-8 h-8 text-gh-orange" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <div v-else-if="error" class="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-gh-red" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p class="text-gh-text text-sm font-medium">No se encontro API documentada</p>
            <p class="text-gh-muted text-xs max-w-sm">{{ error }}</p>
          </div>
          <SwaggerViewer v-else-if="spec" :spec="spec" />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, defineAsyncComponent } from 'vue'
import { getAppOpenapi } from '../api.js'

const SwaggerViewer = defineAsyncComponent(() => import('./SwaggerViewer.vue'))

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  domain: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

const spec    = ref(null)
const loading = ref(false)
const error   = ref(null)

function close() {
  emit('update:modelValue', false)
}

async function fetchSpec(domain) {
  spec.value    = null
  error.value   = null
  loading.value = true
  try {
    spec.value = await getAppOpenapi(domain)
  } catch (e) {
    error.value = e.message || 'Esta app no expone un spec OpenAPI/Swagger en las rutas habituales.'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.domain],
  ([open, domain]) => {
    if (open && domain) fetchSpec(domain)
  }
)
</script>
