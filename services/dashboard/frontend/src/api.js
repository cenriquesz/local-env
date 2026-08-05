const BASE = ''

export async function getServices() {
  const res = await fetch(`${BASE}/api/services`)
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

export async function getCerts() {
  const res = await fetch(`${BASE}/api/certs`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
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

export async function getLocalstackHealth() {
  const res = await fetch(`${BASE}/api/localstack/health`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export function streamLogs(containerName, onLine, onError) {
  const es = new EventSource(`${BASE}/api/logs/${encodeURIComponent(containerName)}`)
  es.onmessage = (evt) => onLine(evt.data)
  es.onerror = (err) => onError(err)
  return es
}
