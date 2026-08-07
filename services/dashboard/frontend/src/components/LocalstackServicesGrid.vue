<template>
  <template v-for="svc in services" :key="svc.id">
    <LocalstackServiceCard :service="svc" />
  </template>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import LocalstackServiceCard from './LocalstackServiceCard.vue'
import { getLocalstackServices } from '../api.js'

const services = ref([])
let timer = null

async function load() {
  try {
    services.value = (await getLocalstackServices()).services
  } catch {
    services.value = []
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 15000)
})

onUnmounted(() => clearInterval(timer))
</script>
