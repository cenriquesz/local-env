<template>
  <div v-if="visibleIds.length" class="space-y-4 mt-4">
    <DetailPanel
      v-if="visibleIds.includes('postgres')"
      title="PostgreSQL - tablas"
      :fetcher="getPostgresTables"
    >
      <template #default="{ data }">
        <p v-if="!data.tables.length" class="text-gh-muted text-xs opacity-50">Sin tablas creadas en «{{ data.database }}»</p>
        <table v-else class="w-full text-xs">
          <thead>
            <tr class="text-gh-muted uppercase tracking-wide text-left">
              <th class="font-medium pb-2">Tabla</th>
              <th class="font-medium pb-2 text-right">Filas</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in data.tables" :key="t.name" class="border-t border-gh-border">
              <td class="py-1.5 text-gh-text font-mono">{{ t.name }}</td>
              <td class="py-1.5 text-gh-muted font-mono text-right">{{ t.rows ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </DetailPanel>

    <DetailPanel
      v-if="visibleIds.includes('opensearch')"
      title="OpenSearch - indices"
      :fetcher="getOpensearchIndices"
    >
      <template #default="{ data }">
        <p v-if="!data.indices.length" class="text-gh-muted text-xs opacity-50">Sin indices creados</p>
        <table v-else class="w-full text-xs">
          <thead>
            <tr class="text-gh-muted uppercase tracking-wide text-left">
              <th class="font-medium pb-2">Indice</th>
              <th class="font-medium pb-2 text-right">Documentos</th>
              <th class="font-medium pb-2 text-right">Tamano</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="idx in data.indices" :key="idx.name" class="border-t border-gh-border">
              <td class="py-1.5 text-gh-text font-mono flex items-center gap-1.5">
                <span
                  :class="idx.health === 'green' ? 'bg-gh-green' : idx.health === 'yellow' ? 'bg-gh-yellow' : 'bg-gh-red'"
                  class="w-1.5 h-1.5 rounded-full inline-block flex-shrink-0"
                ></span>
                {{ idx.name }}
              </td>
              <td class="py-1.5 text-gh-muted font-mono text-right">{{ idx.docs ?? '-' }}</td>
              <td class="py-1.5 text-gh-muted font-mono text-right">{{ idx.size ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </DetailPanel>

    <DetailPanel
      v-if="visibleIds.includes('kafka')"
      title="Kafka - topics"
      :fetcher="getKafkaTopics"
    >
      <template #default="{ data }">
        <p v-if="!data.topics.length" class="text-gh-muted text-xs opacity-50">Sin topics creados</p>
        <ul v-else class="space-y-1">
          <li v-for="t in data.topics" :key="t" class="text-gh-text text-xs font-mono flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-gh-green inline-block flex-shrink-0"></span>{{ t }}
          </li>
        </ul>
      </template>
    </DetailPanel>

    <DetailPanel
      v-if="visibleIds.includes('activemq')"
      title="ActiveMQ - colas y topics"
      :fetcher="getActivemqQueues"
    >
      <template #default="{ data }">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-2">Colas ({{ data.queues.length }})</p>
            <ul v-if="data.queues.length" class="space-y-1">
              <li v-for="q in data.queues" :key="q" class="text-gh-text text-xs font-mono flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-gh-green inline-block flex-shrink-0"></span>{{ q }}
              </li>
            </ul>
            <p v-else class="text-gh-muted text-xs opacity-50">Sin colas creadas</p>
          </div>
          <div>
            <p class="text-gh-muted text-xs font-medium uppercase tracking-wide mb-2">Topics ({{ data.topics.length }})</p>
            <ul v-if="data.topics.length" class="space-y-1">
              <li v-for="t in data.topics" :key="t" class="text-gh-text text-xs font-mono flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-gh-green inline-block flex-shrink-0"></span>{{ t }}
              </li>
            </ul>
            <p v-else class="text-gh-muted text-xs opacity-50">Sin topics creados</p>
          </div>
        </div>
      </template>
    </DetailPanel>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import DetailPanel from './DetailPanel.vue'
import {
  getPostgresTables,
  getKafkaTopics,
  getActivemqQueues,
  getOpensearchIndices,
} from '../api.js'

const props = defineProps({
  category: { type: String, required: true },
  runningIds: { type: Array, default: () => [] },
})

const CATEGORY_OF = {
  postgres: 'db',
  kafka: 'mensajeria',
  activemq: 'mensajeria',
  opensearch: 'db',
}

const visibleIds = computed(() =>
  props.runningIds.filter(id => CATEGORY_OF[id] === props.category)
)
</script>
