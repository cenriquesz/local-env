<template>
  <div class="bg-gh-card border border-gh-border rounded-lg flex flex-col">
    <div class="flex items-center justify-between px-4 py-3 border-b border-gh-border">
      <h3 class="text-gh-text font-semibold text-sm tracking-wide uppercase">{{ service.label }}</h3>
      <span class="inline-flex items-center gap-1.5 text-xs font-medium">
        <span :class="active ? 'bg-gh-green' : 'bg-gh-muted'" class="w-2 h-2 rounded-full inline-block flex-shrink-0"></span>
        <span :class="active ? 'text-gh-green' : 'text-gh-muted'">{{ active ? 'activo' : 'disponible' }}</span>
      </span>
    </div>

    <div class="px-4 py-3 border-b border-gh-border">
      <a
        :href="service.endpoint"
        target="_blank"
        rel="noopener noreferrer"
        class="text-gh-blue text-xs font-mono hover:underline"
      >{{ service.endpoint }}</a>
    </div>

    <div v-if="service.resources !== null" class="px-4 py-3 space-y-1.5 flex-1">
      <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-1">Recursos ({{ service.resources.length }})</p>
      <div v-if="service.resources.length" class="space-y-2 max-h-48 overflow-y-auto">
        <div v-for="r in service.resources" :key="r.arn || r.name">
          <p class="text-gh-text text-xs font-mono truncate">{{ r.name }}</p>
          <p class="text-gh-muted text-xs font-mono opacity-50 truncate" :title="r.arn || ''">{{ r.arn || 'sin ARN' }}</p>
        </div>
      </div>
      <p v-else class="text-gh-muted text-xs opacity-50">Sin recursos creados</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  service: { type: Object, required: true },
})

const active = computed(() => props.service.state === 'running')
</script>
