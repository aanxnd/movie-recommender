import { readFileSync } from 'node:fs'

export function readTargets(path) {
  try {
    const raw = readFileSync(path, 'utf8')
    if (raw.length > 8192) throw new Error()
    const t = JSON.parse(raw), keys = ['approved', 'branch_name', 'branch_id', 'azure_app', 'supabase_url',
      'frontend_origin', 'backend_origin', 'database_host', 'protected_database_hosts']
    if (Object.keys(t).some(k => !keys.includes(k)) || t.approved !== true ||
        t.branch_name !== 'private-stage23' || !/^br-[a-z0-9-]+$/.test(t.branch_id) ||
        t.branch_id === 'br-tiny-bonus-b4ec6f9z' || t.azure_app !== 'movie-recommender-api-private' ||
        t.supabase_url !== 'https://jsbulnrcxtvslvvxjizq.supabase.co' ||
        !/^https:\/\/[a-z0-9-]+\.vercel\.app$/.test(t.frontend_origin) ||
        !/^https:\/\/[a-z0-9]+(?:[.-][a-z0-9]+)*\.azurecontainerapps\.io$/.test(t.backend_origin) ||
        t.backend_origin === 'https://movie-recommender-api.nicetree-0929c2a3.canadacentral.azurecontainerapps.io' ||
        !/^ep-[a-z0-9-]+(?:\.[a-z0-9-]+)+\.neon\.tech$/.test(t.database_host) ||
        !Array.isArray(t.protected_database_hosts) || !t.protected_database_hosts.length ||
        !t.protected_database_hosts.every(h => typeof h === 'string' && h) || t.protected_database_hosts.some(h => h.toLowerCase() === t.database_host)) throw new Error()
    return t
  } catch { throw new Error('Approved private targets required') }
}
