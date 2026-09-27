interface Env { DB: D1Database; BRIDGE_TOKEN: string }
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
    const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers })
    if (!env.BRIDGE_TOKEN || env.BRIDGE_TOKEN.length < 32) return reply({ error: 'NOT_CONFIGURED' }, 503)
    const expected = new TextEncoder().encode('Bearer ' + env.BRIDGE_TOKEN)
    const supplied = new TextEncoder().encode(request.headers.get('Authorization') || '')
    // Constant-time comparison for equal-length tokens; never log credentials or SQL.
    let difference = expected.length ^ supplied.length
    for (let i = 0; i < expected.length; i++) difference |= expected[i] ^ (supplied[i] || 0)
    if (difference) return reply({ error: 'UNAUTHORIZED' }, 401)
    if (request.method !== 'POST' || new URL(request.url).pathname !== '/batch') return reply({ error: 'NOT_FOUND' }, 404)
    const raw = await request.text()
    if (raw.length > 2_000_000) return reply({ error: 'TOO_LARGE' }, 413)
    try {
      const body = JSON.parse(raw) as { statements: { sql: string; params: (string | number | null)[] }[] }
      if (!Array.isArray(body.statements) || !body.statements.length || body.statements.length > 100) return reply({error:'INVALID_BATCH'},422)
      if (body.statements.some(s => typeof s.sql !== 'string' || !Array.isArray(s.params))) return reply({error:'INVALID_STATEMENT'},422)
      const results = await env.DB.batch(body.statements.map(s => env.DB.prepare(s.sql).bind(...s.params)))
      return reply({ success: true, results })
    } catch { return reply({ success: false, error: 'BATCH_REJECTED' },409) }
  }
}
