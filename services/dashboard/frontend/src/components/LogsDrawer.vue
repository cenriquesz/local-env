<template>
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-300 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="modelValue && containers.length"
      class="fixed top-0 right-0 z-50 w-[600px] h-full bg-[#010409] border-l border-gh-border flex flex-col shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gh-border flex-shrink-0">
        <div class="flex items-center gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gh-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-gh-text text-sm font-semibold">Logs</span>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="clearLogs"
            class="px-2.5 py-1 text-xs text-gh-muted hover:text-gh-text border border-gh-border hover:border-gh-text rounded transition-colors"
          >
            Limpiar
          </button>
          <button
            @click="close"
            class="p-1.5 text-gh-muted hover:text-gh-text transition-colors rounded hover:bg-gh-border"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Tabs de contenedores -->
      <div v-if="containers.length > 1" class="flex border-b border-gh-border flex-shrink-0 overflow-x-auto">
        <button
          v-for="c in containers"
          :key="c"
          @click="selectContainer(c)"
          :class="[
            'px-4 py-2 text-xs font-mono whitespace-nowrap flex-shrink-0 border-b-2 transition-colors',
            activeContainer === c
              ? 'border-gh-orange text-gh-orange'
              : 'border-transparent text-gh-muted hover:text-gh-text'
          ]"
        >
          {{ c }}
        </button>
      </div>
      <div v-else class="px-4 py-2 border-b border-gh-border flex-shrink-0">
        <span class="text-xs font-mono text-gh-muted">{{ containers[0] }}</span>
      </div>

      <!-- Area de logs -->
      <div
        ref="logsArea"
        class="flex-1 overflow-y-auto p-4 bg-black"
      >
        <div v-if="lines.length === 0" class="text-gh-muted text-xs font-mono">
          Esperando logs...
        </div>
        <div
          v-for="(line, i) in lines"
          :key="i"
          class="text-[#7ee787] text-xs font-mono leading-5 whitespace-pre-wrap break-all"
        >{{ line }}</div>
        <div ref="logsBottom"></div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { streamLogs } from '../api.js'

const props = defineProps({
  containers: {
    type: Array,
    default: () => []
  },
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const lines          = ref([])
const activeContainer = ref(null)
const logsBottom     = ref(null)
const logsArea       = ref(null)
let   eventSource    = null

function close() {
  emit('update:modelValue', false)
}

function clearLogs() {
  lines.value = []
}

function disconnectSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

function connectSSE(container) {
  disconnectSSE()
  lines.value = []
  eventSource = streamLogs(
    container,
    (line) => {
      lines.value.push(line)
      scrollToBottom()
    },
    () => {
      // error de SSE: no hacemos nada, el EventSource reintenta solo
    }
  )
}

function selectContainer(container) {
  activeContainer.value = container
  connectSSE(container)
}

async function scrollToBottom() {
  await nextTick()
  logsBottom.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

// Cuando se abre el drawer o cambian los contenedores, conectar al primero
watch(
  () => [props.modelValue, props.containers],
  ([open, ctrs]) => {
    if (open && ctrs && ctrs.length) {
      activeContainer.value = ctrs[0]
      connectSSE(ctrs[0])
    } else if (!open) {
      disconnectSSE()
      lines.value = []
      activeContainer.value = null
    }
  },
  { deep: true, immediate: true }
)

onUnmounted(() => {
  disconnectSSE()
})
</script>
