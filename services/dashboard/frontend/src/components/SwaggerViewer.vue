<template>
  <div ref="container" class="swagger-viewer bg-white"></div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import SwaggerUIBundle from 'swagger-ui-dist/swagger-ui-es-bundle.js'
import 'swagger-ui-dist/swagger-ui.css'

const props = defineProps({
  spec: {
    type: Object,
    required: true
  }
})

const container = ref(null)

function render() {
  if (!container.value || !props.spec) return
  SwaggerUIBundle({
    spec: props.spec,
    domNode: container.value,
    presets: [SwaggerUIBundle.presets.apis],
    deepLinking: false,
  })
}

onMounted(render)
watch(() => props.spec, render)
</script>

<style scoped>
.swagger-viewer {
  min-height: 100%;
}
</style>
