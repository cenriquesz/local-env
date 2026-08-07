const BASE = ''

export async function getHealth() {
  const res = await fetch(`${BASE}/api/health`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getServices() {
  const res = await fetch(`${BASE}/api/services`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getCoreServices() {
  const data = await getHealth()
  return data.core ?? []
}

export async function restartCoreService(id) {
  const res = await fetch(`${BASE}/api/core/${id}/restart`, { method: 'POST' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function startService(id) {
  const res = await fetch(`${BASE}/api/services/${id}/start`, { method: 'POST' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function stopService(id) {
  const res = await fetch(`${BASE}/api/services/${id}/stop`, { method: 'POST' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getApps() {
  const res = await fetch(`${BASE}/api/apps`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getDashboardOpenapi() {
  const res = await fetch(`${BASE}/openapi.json`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getAppOpenapi(domain) {
  const res = await fetch(`${BASE}/api/apps/${encodeURIComponent(domain)}/openapi`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Error ${res.status}`)
  }
  return res.json()
}

export async function getCerts() {
  const res = await fetch(`${BASE}/api/certs`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getCertStores() {
  const res = await fetch(`${BASE}/api/certs/stores`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export function downloadCertStoreUrl(filename) {
  return `${BASE}/api/certs/stores/${encodeURIComponent(filename)}`
}

export async function reloadNginx() {
  const res = await fetch(`${BASE}/api/nginx/reload`, { method: 'POST' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function restartMinica() {
  const res = await fetch(`${BASE}/api/minica/restart`, { method: 'POST' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getServiceCategories() {
  const res = await fetch(`${BASE}/api/service-categories`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getLocalstackServices() {
  const res = await fetch(`${BASE}/api/localstack/services`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getPostgresTables() {
  const res = await fetch(`${BASE}/api/postgres/tables`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getKafkaTopics() {
  const res = await fetch(`${BASE}/api/kafka/topics`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getActivemqQueues() {
  const res = await fetch(`${BASE}/api/activemq/queues`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function getOpensearchIndices() {
  const res = await fetch(`${BASE}/api/opensearch/indices`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export function streamLogs(containerName, onLine, onError) {
  const es = new EventSource(`${BASE}/api/logs/${encodeURIComponent(containerName)}`)
  es.onmessage = (evt) => onLine(evt.data)
  es.onerror = (err) => onError(err)
  return es
}
