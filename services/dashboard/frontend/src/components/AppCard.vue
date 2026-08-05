<template>
  <div class="bg-gh-card border border-gh-border rounded-lg flex flex-col">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-gh-border">
      <h3
        :class="[
          'text-sm font-semibold',
          isSinIdentificar ? 'text-gh-muted italic' : 'text-gh-text'
        ]"
      >
        {{ app.name }}
      </h3>
    </div>

    <!-- Servicios -->
    <div class="px-4 py-3 space-y-2">
      <div
        v-for="svc in app.services"
        :key="svc.domain"
        class="flex items-center gap-2"
      >
        <div class="flex-1 min-w-0">
          <p class="text-gh-muted text-xs truncate">{{ svc.domain }}</p>
          <a
            :href="svc.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-gh-blue text-xs font-mono hover:underline truncate block"
            :title="svc.url"
          >{{ svc.url }}</a>
        </div>
        <button
          @click="$emit('open-api', svc.domain)"
          class="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs text-gh-muted hover:text-gh-text border border-gh-border hover:border-gh-text rounded transition-colors"
          title="Buscar y ver el spec OpenAPI/Swagger de esta app"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 8l-4 4 4 4" />
          </svg>
          API
        </button>
        <StatusBadge :status="svc.status" />
      </div>

      <p v-if="!app.services || app.services.length === 0" class="text-gh-muted text-xs italic">
        Sin servicios detectados
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  app: {
    type: Object,
    required: true
  }
})

defineEmits(['open-api'])

const isSinIdentificar = computed(() => props.app.name === 'Sin identificar')
</script>
