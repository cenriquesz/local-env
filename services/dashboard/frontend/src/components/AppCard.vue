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

const isSinIdentificar = computed(() => props.app.name === 'Sin identificar')
</script>
