<template>
  <span class="inline-flex items-center gap-1.5 text-xs font-medium">
    <span :class="dotClass" class="inline-block w-2 h-2 rounded-full flex-shrink-0"></span>
    <span :class="textClass">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'unknown'
  }
})

const config = {
  running:   { dot: 'bg-gh-green',   text: 'text-gh-green',  label: 'running' },
  idle:      { dot: 'bg-gh-blue',    text: 'text-gh-blue',   label: 'idle' },
  stopped:   { dot: 'bg-gh-muted',   text: 'text-gh-muted',  label: 'stopped' },
  partial:   { dot: 'bg-gh-yellow',  text: 'text-gh-yellow', label: 'partial' },
  error:     { dot: 'bg-gh-red',     text: 'text-gh-red',    label: 'error' },
  not_found: { dot: 'bg-gh-red',     text: 'text-gh-red',    label: 'not found' },
  unknown:   { dot: 'bg-gh-muted',   text: 'text-gh-muted',  label: 'unknown' },
}

const current = computed(() => config[props.status] ?? config.unknown)
const dotClass  = computed(() => current.value.dot)
const textClass = computed(() => current.value.text)
const label     = computed(() => current.value.label)
</script>
