<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  api,
  ApiError,
  type Article,
  type Topic,
  type Source,
  type Run,
  type Generation,
  type Model,
  type Settings,
  type SystemStatus,
  type Page,
  type Output,
} from '../data/live'
const connectionFields = [
  { key: 'openrouter_api_key', label: 'OpenRouter API key', secret: true },
  { key: 'firecrawl_api_key', label: 'Firecrawl API key', secret: true },
  { key: 'resend_api_key', label: 'Resend API key', secret: true },
  { key: 'email_from', label: 'Sender email', secret: false },
  { key: 'email_recipient', label: 'Recipient email', secret: false },
]
const connectionStatus = ref<Record<string, boolean>>({})
const editingConnection = ref('')
const connectionValues = ref<Record<string, string>>({})
const connectionErrors = ref<Record<string, string>>({})
function editConnection(key: string) {
  if (editingConnection.value) connectionValues.value[editingConnection.value] = ''
  editingConnection.value = key
  if (key) {
    connectionValues.value[key] = ''
    connectionErrors.value[key] = ''
  }
}
async function saveConnection(key: string) {
  const value = connectionValues.value[key]?.trim()
  if (busy.value || !value) return
  busy.value = true
  connectionErrors.value[key] = ''
  try {
    await api('/settings/providers', 'PUT', { [key]: value })
    connectionStatus.value[key] = true
    editingConnection.value = ''
    connectionValues.value[key] = ''
    message.value = 'Connection updated. New jobs will use the saved value.'
    status.value = await api<SystemStatus>('/system/status')
  } catch (e) {
    connectionErrors.value[key] = e instanceof Error ? e.message : 'Could not save this connection.'
  } finally {
    busy.value = false
  }
}
const route = useRoute(),
  router = useRouter()
const section = computed(() => route.path.split('/')[1] || 'overview')
const id = computed(() => route.params.id as string | undefined)
const loading = ref(false),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  needsAuth = ref(false)
const status = ref<SystemStatus>(),
  topics = ref<Topic[]>([]),
  sources = ref<Source[]>([]),
  articles = ref<Article[]>([]),
  runs = ref<Run[]>([]),
  generations = ref<Generation[]>([]),
  models = ref<Model[]>([])
const article = ref<Article>(),
  run = ref<Run>(),
  generation = ref<Generation>(),
  settings = ref<Settings>()
const summary = ref<{
  articles: number
  sources: number
  active_topics: number
  generations: number
  drafts: number
}>()
const search = ref(''),
  source = ref(''),
  classification = ref(''),
  topic = ref(''),
  from = ref(''),
  to = ref(''),
  runFilter = ref(''),
  page = ref(1),
  pages = ref(0),
  total = ref(0)
const selected = ref<string[]>([]),
  wizard = ref(false),
  outputs = ref(['BLOG', 'LINKEDIN']),
  refresh = ref(false),
  tab = ref('BLOG'),
  versionId = ref(''),
  raw = ref(false),
  instructions = ref(''),
  regenerate = ref(false),
  dependency = ref('')
const catalog = ref(false),
  editId = ref(''),
  name = ref(''),
  description = ref(''),
  website = ref(''),
  feed = ref(''),
  modelName = ref('')
const currentOutput = computed(() =>
  generation.value?.outputs?.find((o) => o.output_type === tab.value),
)
const currentVersion = computed(
  () =>
    currentOutput.value?.versions.find((v) => v.id === versionId.value) ||
    currentOutput.value?.versions.at(-1),
)
const rendered = computed(() =>
  DOMPurify.sanitize(marked.parse(currentVersion.value?.content_markdown || '') as string),
)
const pending = (s?: string) =>
  !!s && ['PENDING', 'RUNNING', 'CRAWLING', 'PREPARING_CONTEXT', 'GENERATING'].includes(s)
const date = (s?: string | null) =>
  s ? new Date(s).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
let epoch = 0
async function load(background = false) {
  const request = ++epoch
  if (!background) loading.value = true
  error.value = ''
  try {
    const [health, ts, ss] = await Promise.all([
      api<SystemStatus>('/system/status'),
      api<Page<Topic>>('/topics?page_size=100'),
      api<Page<Source>>('/sources?page_size=100'),
    ])
    if (request !== epoch) return
    status.value = health
    topics.value = ts.items
    sources.value = ss.items
    const s = section.value
    if (s === 'overview') {
      const [a, r, g, sm] = await Promise.all([
        api<Page<Article>>('/articles?page_size=4'),
        api<Page<Run>>('/classification-runs?page_size=3'),
        api<Page<Generation>>('/generations?page_size=3'),
        api<typeof summary.value>('/dashboard/summary'),
      ])
      if (request !== epoch) return
      articles.value = a.items
      runs.value = r.items
      generations.value = g.items
      summary.value = sm
    } else if (s === 'articles') {
      if (id.value) {
        const a = await api<Article>('/articles/' + id.value)
        if (request === epoch) article.value = a
      } else {
        const params = new URLSearchParams({
          page: String(page.value),
          page_size: '25',
          search: search.value,
        })
        for (const [key, value] of Object.entries({
          source: source.value,
          classification: classification.value,
          topic: topic.value,
          date_from: from.value,
          date_to: to.value,
          run_id: runFilter.value,
        }))
          if (value) params.set(key, value)
        const data = await api<Page<Article>>('/articles?' + params)
        if (request !== epoch) return
        articles.value = data.items
        pages.value = data.pagination.pages
        total.value = data.pagination.total
      }
    } else if (s === 'discovery') {
      if (id.value) {
        const data = await api<Run>('/classification-runs/' + id.value)
        if (request === epoch) run.value = data
      } else {
        const data = await api<Page<Run>>('/classification-runs?page=' + page.value)
        if (request !== epoch) return
        runs.value = data.items
        pages.value = data.pagination.pages
        total.value = data.pagination.total
      }
    } else if (s === 'generations') {
      if (id.value) {
        const data = await api<Generation>('/generations/' + id.value)
        if (request !== epoch) return
        generation.value = data
        if (
          !data.outputs.some((o) => o.output_type === tab.value) &&
          !['Sources', 'Processing'].includes(tab.value)
        )
          tab.value = data.outputs[0]?.output_type || 'BLOG'
      } else {
        const data = await api<Page<Generation>>('/generations?page=' + page.value)
        if (request !== epoch) return
        generations.value = data.items
        pages.value = data.pagination.pages
        total.value = data.pagination.total
      }
    } else if (s === 'settings') {
      const [config, ms] = await Promise.all([
        api<Settings>('/settings'),
        api<Page<Model>>('/settings/llm-models?page_size=100'),
      ])
      if (request !== epoch) return
      connectionStatus.value = await api<Record<string, boolean>>('/settings/providers')
      settings.value = config
      models.value = ms.items.sort((a, b) => a.position - b.position)
    }
    needsAuth.value = false
  } catch (e) {
    if (request !== epoch) return
    error.value = e instanceof Error ? e.message : 'Unexpected error'
    needsAuth.value = e instanceof ApiError && e.status === 401
  } finally {
    if (request === epoch) loading.value = false
  }
}
async function action(fn: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Operation failed'
  } finally {
    busy.value = false
  }
}
async function discover() {
  await action(async () => {
    const job = await api<{ id: string }>('/classification-runs', 'POST')
    await router.push('/discovery/' + job.id)
  })
}
function toggle(id: string) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value, id]
}
function startGeneration() {
  if (article.value && id.value) selected.value = [article.value.id]
  wizard.value = true
}
async function createGeneration() {
  await action(async () => {
    const g = await api<{ id: string }>('/generations', 'POST', {
      article_ids: selected.value,
      outputs: outputs.value,
      force_refresh_sources: refresh.value,
    })
    wizard.value = false
    selected.value = []
    await router.push('/generations/' + g.id)
  })
}
async function retryArticle() {
  await action(async () => {
    const result = await api<{ id: string }>(`/articles/${id.value}/classification/retry`, 'POST')
    await router.push('/discovery/' + result.id)
  })
}
async function approve() {
  await action(async () => {
    if (!currentOutput.value || !currentVersion.value) return
    await api(
      `/generation-outputs/${currentOutput.value.id}/versions/${currentVersion.value.version}/approve`,
      'POST',
    )
    message.value = 'Version approved. Nothing is published automatically.'
    await load(true)
  })
}
async function regenerateVersion() {
  await action(async () => {
    if (!currentOutput.value) return
    await api(`/generation-outputs/${currentOutput.value.id}/versions`, 'POST', {
      additional_instructions: instructions.value,
      depends_on_version_id: dependency.value || null,
    })
    regenerate.value = false
    message.value = 'New version queued.'
    await load(true)
  })
}
async function copy() {
  try {
    await navigator.clipboard.writeText(currentVersion.value?.content_markdown || '')
    message.value = 'Content copied.'
  } catch {
    raw.value = true
    error.value = 'Clipboard unavailable: copy the Markdown manually.'
  }
}
function edit(item?: Topic | Source) {
  editId.value = item?.id || ''
  name.value = item?.name || ''
  description.value = item && 'description' in item ? item.description : ''
  website.value = item && 'website_url' in item ? item.website_url : ''
  feed.value = item && 'feed_url' in item ? item.feed_url || '' : ''
  catalog.value = true
}
async function saveCatalog() {
  await action(async () => {
    const kind = section.value
    const body =
      kind === 'topics'
        ? { name: name.value, description: description.value }
        : { name: name.value, website_url: website.value, feed_url: feed.value || null }
    await api(
      '/' + kind + (editId.value ? '/' + editId.value : ''),
      editId.value ? 'PATCH' : 'POST',
      body,
    )
    catalog.value = false
    await load(true)
  })
}
async function activate(item: Topic | Source) {
  await action(async () => {
    await api('/' + section.value + '/' + item.id, 'PATCH', { is_active: !item.is_active })
    await load(true)
  })
}
async function promote(name: string) {
  await action(async () => {
    await api('/topics', 'POST', {
      name,
      description: 'Topic promoted from the library',
      is_active: true,
    })
    message.value = 'Topic added for future classifications.'
    await load(true)
  })
}
async function testFeed() {
  await action(async () => {
    const result = await api<{ sample_count: number }>('/sources/test', 'POST', {
      feed_url: feed.value,
    })
    message.value = `Valid feed: ${result.sample_count} sample articles.`
  })
}
async function saveSettings() {
  await action(async () => {
    await api('/settings', 'PUT', settings.value)
    message.value = 'Settings saved.'
  })
}
async function addModel() {
  await action(async () => {
    await api('/settings/llm-models', 'POST', {
      model: modelName.value,
      position: models.value.length ? Math.max(...models.value.map((m) => m.position)) + 1 : 0,
      enabled: true,
    })
    modelName.value = ''
    await load(true)
  })
}
async function moveModel(index: number) {
  await action(async () => {
    const ids = models.value.map((m) => m.id)
    ;[ids[index - 1], ids[index]] = [ids[index]!, ids[index - 1]!]
    await api('/settings/llm-models/reorder', 'POST', { ids })
    await load(true)
  })
}
async function toggleModel(model: Model) {
  await action(async () => {
    await api('/settings/llm-models/' + model.id, 'PATCH', { enabled: !model.enabled })
    await load(true)
  })
}
async function retryEmail(email: string) {
  await action(async () => {
    await api('/emails/' + email + '/retry', 'POST')
    await load(true)
  })
}
function changePage(delta: number) {
  page.value += delta
  void load()
}
function filter() {
  page.value = 1
  void load()
}
function login() {
  window.location.reload()
}
watch(
  () => route.fullPath,
  () => {
    page.value = 1
    tab.value = 'BLOG'
    versionId.value = ''
    article.value = undefined
    run.value = undefined
    generation.value = undefined
    void load()
  },
  { immediate: true },
)
const timer = setInterval(() => {
  if (
    !busy.value &&
    !loading.value &&
    (pending(run.value?.status) ||
      pending(generation.value?.status) ||
      generation.value?.jobs?.some((j) => pending(j.status)))
  )
    void load(true)
}, 3000)
onUnmounted(() => {
  epoch++
  clearInterval(timer)
})
</script>
<template>
  <div v-if="error" class="notice" role="alert">
    {{ error }} <button @click="load()">Retry</button>
  </div>
  <div v-if="message" class="notice" role="status">
    {{ message }}<button @click="message = ''">×</button>
  </div>
  <div v-if="needsAuth" class="page-heading narrow">
    <h1>Session expired.</h1>
    <button @click="login">Back to login</button>
  </div>
  <p v-if="loading" role="status" class="caption-note">Loading workspace…</p>
  <template v-if="!needsAuth">
    <p v-if="status?.quota_pause" class="caption-note">OpenRouter quota reached. Work is saved. <span v-if="status.quota_pause.auto_resume">Automatic resume after {{ date(new Date(status.quota_pause.until * 1000).toISOString()) }}.</span><span v-else>Automatic resume is disabled. Enable it in Settings when you want to continue; quota reset time: {{ date(new Date(status.quota_pause.until * 1000).toISOString()) }}.</span> {{ status.quota_pause.reason }}</p>
    <div v-if="status && !status.worker_online" class="caption-note">
      Worker offline: new requests will stay queued until it starts.
    </div>
    <template v-if="section === 'overview'">
      <section class="hero">
        <div>
          <p class="eyebrow">YOUR ENGINEERING OBSERVATORY</p>
          <h1>Good sources.<br /><span class="accent">Better thinking.</span></h1>
          <p class="lede">
            From meaningful signals to ideas worth sharing.<br />Your space to discover, explore and
            write.
          </p>
          <RouterLink to="/articles" class="button primary">Explore articles ↗</RouterLink>
        </div>
        <aside class="edition">
          <p class="eyebrow">TODAY</p>
          <strong
            >{{ new Date().getDate() }}<span> / {{ new Date().getMonth() + 1 }}</span></strong
          >
          <div class="rule"></div>
          <p>{{ status?.worker_online ? 'Worker online' : 'Worker offline' }}</p>
          <p>{{ status?.active_sources || 0 }} active sources · {{ status?.models || 0 }} models</p>
          <RouterLink to="/settings" class="text-link">Configure workspace ↗</RouterLink>
        </aside>
      </section>
      <section class="metrics">
        <div>
          <span class="eyebrow">ARTICLES IN LIBRARY</span
          ><strong>{{ summary?.articles || 0 }}</strong>
        </div>
        <div>
          <span class="eyebrow">ACTIVE TOPICS</span
          ><strong>{{ summary?.active_topics || 0 }}</strong>
        </div>
        <div>
          <span class="eyebrow">DRAFTS TO REVIEW</span><strong>{{ summary?.drafts || 0 }}</strong>
        </div>
      </section>
      <div class="overview-grid">
        <section>
          <div class="section-heading">
            <h2>Worth a closer look.</h2>
            <RouterLink to="/articles" class="text-link">All articles ↗</RouterLink>
          </div>
          <article v-for="a in articles" :key="a.id" class="article-row">
            <div>
              <p class="eyebrow">{{ a.source_name }} / {{ date(a.published_at) }}</p>
              <RouterLink class="article-title" :to="'/articles/' + a.id">{{ a.title }}</RouterLink>
              <div class="badges">
                <span v-for="t in a.classification?.topics" :key="t.topic_name" class="badge"
                  >{{ t.topic_name }} · {{ Math.round(t.confidence * 100) }}%</span
                >
              </div>
            </div>
          </article>
          <p v-if="!articles.length" class="empty">
            Your library is ready. Configure sources and start your first discovery.
          </p>
        </section>
        <aside class="side-note">
          <p class="eyebrow">DISCOVERY</p>
          <h3>A fresh starting point.</h3>
          <p v-for="r in runs" :key="r.id">
            <RouterLink :to="'/discovery/' + r.id">{{ date(r.created_at) }} →</RouterLink
            ><br /><span class="badge">{{ r.status }}</span>
          </p>
          <button :disabled="busy" @click="discover">Run discovery ↗</button>
        </aside>
      </div>
    </template>
    <template v-else-if="section === 'articles'">
      <template v-if="!id"
        ><div class="page-heading">
          <p class="eyebrow">DISCOVER / LIBRARY</p>
          <h1>The reading room<span class="accent">.</span></h1>
          <p class="lede">Find connections. Select sources. Start writing.</p>
        </div>
        <form @submit.prevent="filter">
          <div class="filters">
            <label
              >Search<input v-model="search" type="search" placeholder="Title or keyword" /></label
            ><label
              >Source<select v-model="source">
                <option value="">All</option>
                <option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select></label
            ><label
              >Status<select v-model="classification">
                <option value="">All</option>
                <option value="target">Target</option>
                <option value="non-target">Non-target</option>
                <option value="failed">Failed</option>
              </select></label
            ><label
              >Topic<select v-model="topic">
                <option value="">All</option>
                <option v-for="t in topics" :key="t.id">{{ t.name }}</option>
              </select></label
            >
          </div>
          <div class="filter-secondary">
            <label>From<input v-model="from" type="date" /></label
            ><label>To<input v-model="to" type="date" /></label><button>Apply filters</button
            ><span>{{ total }} articles</span>
          </div>
        </form>
        <article v-for="a in articles" :key="a.id" class="article-row">
          <input
            type="checkbox"
            :checked="selected.includes(a.id)"
            @change="toggle(a.id)"
            :aria-label="'Select ' + a.title"
          />
          <div class="article-main">
            <p class="eyebrow">{{ a.source_name }} / {{ date(a.published_at) }}</p>
            <RouterLink :to="'/articles/' + a.id" class="article-title">{{ a.title }}</RouterLink>
            <div class="badges">
              <span v-if="a.classification?.status === 'FAILED'" class="badge warning"
                >Classification failed</span
              ><span v-for="t in a.classification?.topics" :key="t.topic_name" class="badge"
                >{{ t.topic_type === 'NON_TARGET' ? 'Non-target · ' : '' }}{{ t.topic_name }} ·
                {{ Math.round(t.confidence * 100) }}%</span
              >
            </div>
          </div>
        </article>
        <p v-if="!loading && !articles.length" class="empty">
          No articles yet. Adjust your filters or run discovery.
        </p>
        <div v-if="selected.length" class="selection-bar">
          <span>{{ selected.length }} selected sources</span
          ><button @click="selected = []">Clear selection</button
          ><button class="primary" @click="startGeneration">Create content ↗</button>
        </div></template
      >
      <template v-else-if="article"
        ><RouterLink to="/articles" class="back">← Library</RouterLink>
        <div class="page-heading">
          <p class="eyebrow">{{ article.source_name }}</p>
          <h1 class="detail-title">{{ article.title }}</h1>
          <a class="button" :href="article.url" target="_blank" rel="noreferrer">Open original ↗</a>
        </div>
        <div class="two-column">
          <section>
            <h2>Classification from the RSS title.</h2>
            <div class="badges">
              <span v-for="t in article.classification?.topics" :key="t.topic_name" class="badge"
                >{{ t.topic_name }} · {{ Math.round(t.confidence * 100) }}%
                <button
                  v-if="t.topic_type === 'NON_TARGET'"
                  @click="promote(t.topic_name)"
                  :aria-label="'Promote ' + t.topic_name"
                >
                  +
                </button></span
              >
            </div>
            <p class="muted">{{ article.classification?.status || 'Not classified' }}</p>
            <details v-if="article.classification?.attempts?.length" style="margin: 20px 0">
              <summary>Classification attempts</summary>
              <p v-for="attempt in article.classification.attempts" :key="attempt.attempt_number" class="caption-note">
                #{{ attempt.attempt_number }} · {{ attempt.model }} · {{ attempt.status }}
                <br />{{ attempt.error_code || 'Valid response' }} · {{ date(attempt.started_at) }}
              </p>
            </details>
            <button class="primary" @click="startGeneration">Generate from this source</button
            ><button :disabled="busy" @click="retryArticle">Reclassify</button>
          </section>
          <aside class="side-note">
            <p class="eyebrow">PROVENANCE</p>
            <dl>
              <div>
                <dt>Model</dt>
                <dd>{{ article.classification?.model_used || '—' }}</dd>
              </div>
              <div>
                <dt>Prompt</dt>
                <dd>{{ article.classification?.prompt_version || '—' }}</dd>
              </div>
              <div>
                <dt>Discovery</dt>
                <dd>{{ date(article.discovered_at) }}</dd>
              </div>
            </dl>
          </aside>
        </div></template
      >
    </template>
    <template v-else-if="section === 'discovery'">
      <div class="page-heading heading-actions">
        <div>
          <p class="eyebrow">DISCOVER / RUN HISTORY</p>
          <h1>Keep your curiosity<br /><span class="accent">in motion.</span></h1>
        </div>
        <button :disabled="busy" @click="discover">Run discovery ↗</button>
      </div>
      <div v-if="!id" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Discovery</th>
              <th>Status</th>
              <th>Articles</th>
              <th>Target</th>
              <th>Failed</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id">
              <td>
                <RouterLink :to="'/discovery/' + r.id">{{ date(r.created_at) }} ↗</RouterLink>
              </td>
              <td>{{ r.status }}</td>
              <td>{{ r.new_articles }}</td>
              <td>{{ r.target_count }}</td>
              <td>{{ r.failed_count }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!runs.length" class="empty">No discovery runs yet.</p>
      </div>
      <template v-else-if="run"
        ><RouterLink to="/discovery" class="back">← All runs</RouterLink>
        <p>
          <span class="badge">{{ run.status }}</span> · {{ date(run.created_at) }}
        </p>
        <div class="metrics">
          <div>
            <span>Articles</span><strong>{{ run.new_articles }}</strong>
          </div>
          <div>
            <span>Target</span><strong>{{ run.target_count }}</strong>
          </div>
          <div>
            <span>Failed</span><strong>{{ run.failed_count }}</strong>
          </div>
        </div>
        <h2 style="margin-top: 35px">Articles in this run</h2>
        <article v-for="a in run.articles" :key="a.id" class="article-row">
          <RouterLink :to="'/articles/' + a.id">{{ a.title }} ↗</RouterLink
          ><span class="badge">{{ a.classification?.status }}</span>
        </article>
        <h2 style="margin-top: 35px">Events & digest</h2>
        <p v-for="e in run.events" :key="e.id" class="caption-note">
          {{ date(e.created_at) }} · {{ e.stage }} · {{ e.status }} · {{ e.error_code }}
        </p>
        <div v-for="e in run.emails" :key="e.id" class="catalog-row">
          <div>
            {{ e.subject }}
            <p class="muted">{{ e.recipient }} · {{ e.status }}</p>
          </div>
          <button v-if="e.status === 'FAILED'" :disabled="busy" @click="retryEmail(e.id)">
            Retry delivery
          </button>
        </div>
        <p v-if="!run.emails.length" class="muted">
          No digest recorded. Check whether email delivery is enabled in Settings.
        </p></template
      >
    </template>
    <template v-else-if="section === 'generations'">
      <div class="page-heading">
        <p class="eyebrow">WRITE / GENERATIONS</p>
        <h1>Ideas, in the making<span class="accent">.</span></h1>
      </div>
      <template v-if="!id"
        ><RouterLink class="button primary" to="/articles">New generation ↗</RouterLink>
        <article v-for="g in generations" :key="g.id" class="generation-row">
          <p class="eyebrow">{{ date(g.created_at) }}</p>
          <RouterLink class="article-title" :to="'/generations/' + g.id"
            >{{ g.generate_blog ? 'Blog' : ''
            }}{{ g.generate_blog && g.generate_linkedin ? ' + ' : ''
            }}{{ g.generate_linkedin ? 'LinkedIn' : '' }} ↗</RouterLink
          ><span class="badge">{{ g.status }}</span>
        </article>
        <p v-if="!generations.length" class="empty">
          Select one or more library sources to create your first draft.
        </p></template
      >
      <template v-else-if="generation"
        ><RouterLink to="/generations" class="back">← Generations</RouterLink>
        <p>
          <span class="badge">{{ generation.status }}</span> ·
          {{ generation.sources.length }} sources
        </p>
        <div class="tabs">
          <button
            v-for="t in [...generation.outputs.map((o) => o.output_type), 'Sources', 'Processing']"
            :key="t"
            :class="{ active: tab === t }"
            @click="tab = t"
          >
            {{ t }}
          </button>
        </div>
        <div v-if="currentOutput" class="writing-layout">
          <section v-if="currentVersion">
            <div class="preview-toolbar">
              <button @click="raw = !raw">{{ raw ? 'Preview' : 'Markdown' }}</button
              ><button @click="copy">Copy content ↗</button>
            </div>
            <pre v-if="raw" class="markdown-source">{{ currentVersion.content_markdown }}</pre>
            <article v-else class="prose" v-html="rendered"></article>
          </section>
          <p v-else class="empty">
            {{
              pending(generation.status)
                ? 'Generation in progress. This page refreshes automatically.'
                : 'No output available. Check Processing for errors.'
            }}
          </p>
          <aside v-if="currentVersion" class="version-panel">
            <p class="eyebrow">VERSION & PROVENANCE</p>
            <label
              >Version<select v-model="versionId">
                <option value="">Latest version</option>
                <option v-for="v in currentOutput.versions" :key="v.id" :value="v.id">
                  v{{ v.version }} · {{ v.status }}
                </option>
              </select></label
            >
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{{ currentVersion.status }}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{{ currentVersion.model_used }}</dd>
              </div>
              <div>
                <dt>Prompt</dt>
                <dd>{{ currentVersion.prompt_version }}</dd>
              </div>
              <div v-for="d in currentVersion.dependencies" :key="d.depends_on_version_id">
                <dt>Based on</dt>
                <dd>{{ d.output_type }} v{{ d.version }}</dd>
              </div>
            </dl>
            <button
              class="primary"
              :disabled="busy || currentVersion.status === 'APPROVED'"
              @click="approve"
            >
              Approve version</button
            ><button :disabled="busy || pending(generation.status)" @click="regenerate = true">
              Regenerate
            </button>
            <p class="small muted">Nothing is published automatically.</p>
          </aside>
        </div>
        <section v-if="tab === 'Sources'">
          <h2>Every idea has a source.</h2>
          <article v-for="s in generation.sources" :key="s.id" class="catalog-row">
            <div class="grow">
              <h3>{{ s.article_title }}</h3>
              <a :href="s.original_url" target="_blank" rel="noreferrer">Open original ↗</a>
              <p class="muted">{{ s.crawl_status }}</p>
              <p v-for="c in s.crawls" :key="c.crawled_at" class="small">
                {{ date(c.crawled_at) }} · {{ c.status }} {{ c.error_code }}
              </p>
            </div>
          </article>
        </section>
        <section v-if="tab === 'Processing'">
          <h2>The story behind this draft.</h2>
          <ol class="timeline">
            <li v-for="j in generation.jobs" :key="j.id">
              {{ j.kind }} · {{ j.status }} · {{ j.error_code }}
            </li>
            <li v-for="e in generation.events" :key="e.id">
              <span>{{ date(e.created_at) }}</span
              >{{ e.stage }} · {{ e.status }} · {{ e.error_code }}
            </li>
          </ol>
        </section>
      </template>
    </template>
    <template v-else-if="section === 'topics' || section === 'sources'">
      <div class="page-heading heading-actions">
        <div>
          <p class="eyebrow">CURATE / {{ section }}</p>
          <h1>
            {{ section === 'topics' ? 'Follow what matters' : 'Start with good sources'
            }}<span class="accent">.</span>
          </h1>
        </div>
        <button class="primary" @click="edit()">
          Add {{ section === 'topics' ? 'topic' : 'source' }}
        </button>
      </div>
      <p class="caption-note">Changes apply to future runs. History retains the original data.</p>
      <article
        v-for="item in section === 'topics' ? topics : sources"
        :key="item.id"
        class="catalog-row"
      >
        <div class="grow">
          <h2>{{ item.name }}</h2>
          <p class="muted">
            {{
              'description' in item ? item.description : item.feed_url || 'RSS feed not configured'
            }}
          </p>
        </div>
        <button :disabled="busy" @click="edit(item)">Edit</button
        ><button
          class="toggle"
          :class="{ on: item.is_active }"
          :disabled="busy"
          @click="activate(item)"
        >
          {{ item.is_active ? 'Active' : 'Inactive' }} ●
        </button>
      </article>
    </template>
    <template v-else-if="section === 'settings'"
      ><div class="page-heading">
        <p class="eyebrow">CONFIGURE / WORKSPACE</p>
        <h1>Your rhythm.<br /><span class="accent">Your rules.</span></h1>
      </div>
      <section class="connections">
        <h2>Connections.</h2>
        <p class="muted">
          Edit and save each connection separately. Saved keys are never displayed. Configured
          indicates a saved value, not a successful provider test.
        </p>
        <article v-for="field in connectionFields" :key="field.key" class="connection-row">
          <div>
            <h3>{{ field.label }}</h3>
            <p class="muted">{{ connectionStatus[field.key] ? 'Configured' : 'Not configured' }}</p>
          </div>
          <div
            v-if="connectionStatus[field.key] && editingConnection !== field.key"
            class="connection-editor connection-locked"
          >
            <input
              type="password"
              value="configured-value"
              disabled
              :aria-label="field.label + ': configured'"
              autocomplete="off"
            />
            <button :disabled="busy" @click="editConnection(field.key)">Edit</button>
          </div>
          <form v-else @submit.prevent="saveConnection(field.key)" class="connection-editor">
            <label :for="field.key" class="sr-only">{{ field.label }}</label>
            <input
              :id="field.key"
              v-model="connectionValues[field.key]"
              :type="field.secret ? 'password' : field.key === 'email_recipient' ? 'email' : 'text'"
              :placeholder="field.secret ? 'Type your API key' : 'Type your email address'"
              autocomplete="off"
              required
            />
            <p v-if="connectionErrors[field.key]" role="alert">{{ connectionErrors[field.key] }}</p>
            <div class="actions">
              <button class="primary" :disabled="busy || !connectionValues[field.key]?.trim()">
                Save</button
              ><button
                v-if="connectionStatus[field.key]"
                type="button"
                :disabled="busy"
                @click="editConnection('')"
              >
                Cancel
              </button>
            </div>
          </form>
        </article>
        <p class="caption-note">
          Worker: {{ status?.worker_online ? 'Online' : 'Offline' }} · Storage:
          {{ status?.storage }}
        </p>
      </section>
      <form v-if="settings" @submit.prevent="saveSettings">
        <section class="settings-section">
          <div>
            <h2>Keep listening.</h2>
            <p class="muted">
              Schedules are saved here. Automatic execution requires D1 and GitHub Actions.
            </p>
            <p class="muted">
              Run discovery manually to populate your library. It uses your saved settings and does
              not require a schedule.
            </p>
            <button type="button" :disabled="busy || !status?.worker_online" @click="discover">
              Run discovery now ↗
            </button>
          </div>
          <div class="form-grid">
            <label class="check"
              ><input type="checkbox" v-model="settings.discovery.enabled" />Scheduled
              discovery</label
            ><label
              >Frequency<select v-model="settings.discovery.frequency">
                <option>WEEKLY</option>
                <option>DAILY</option>
              </select></label
            ><label
              >Day<select v-model="settings.discovery.day_of_week">
                <option
                  v-for="(day, index) in [
                    'Monday',
                    'Tuesday',
                    'Wednesday',
                    'Thursday',
                    'Friday',
                    'Saturday',
                    'Sunday',
                  ]"
                  :key="day"
                  :value="index"
                >
                  {{ day }}
                </option>
              </select></label
            ><label
              >Hour<input
                type="number"
                min="0"
                max="23"
                v-model.number="settings.discovery.hour" /></label
            ><label
              >Minute<input
                type="number"
                min="0"
                max="59"
                v-model.number="settings.discovery.minute" /></label
            ><label>Timezone<input v-model="settings.discovery.timezone" /></label
            ><label
              >Threshold (0–1)<input
                type="number"
                min="0"
                max="1"
                step="0.05"
                v-model.number="settings.classification_threshold" /></label
            ><label class="check"><input type="checkbox" v-model="settings.openrouter_auto_resume" />Automatically resume queued work after the daily quota resets</label
            ><label>OpenRouter requests per minute (RPM)<input type="number" min="1" max="10000" v-model.number="settings.openrouter_requests_per_minute" /></label
            ><label>OpenRouter requests per day<input type="number" min="1" max="1000000" v-model.number="settings.openrouter_requests_per_day" /></label
            ><label
              >Source cache (days)<input
                type="number"
                min="0"
                max="365"
                v-model.number="settings.crawl_cache_days" /></label
            ><label class="check"
              ><input type="checkbox" v-model="settings.email_enabled" />Send a digest after
              discovery</label
            >
          </div>
        </section>
        <div class="actions">
          <button class="primary" :disabled="busy">Save settings</button>
        </div>
      </form>
      <section class="settings-section">
        <div>
          <h2>One model, then the next.</h2>
          <p class="muted">
            Add OpenRouter model IDs with structured output support. Every attempt is recorded.
          </p>
        </div>
        <div>
          <div v-for="(m, index) in models" :key="m.id" class="model-row">
            <code>{{ m.model }}</code
            ><button
              :disabled="busy || !index"
              @click="moveModel(index)"
              :aria-label="'Move up ' + m.model"
            >
              ↑</button
            ><button :disabled="busy" @click="toggleModel(m)">
              {{ m.enabled ? 'On' : 'Off' }}
            </button>
          </div>
          <form @submit.prevent="addModel">
            <label
              >Model<input v-model="modelName" required placeholder="provider/model-id" /></label
            ><button :disabled="busy">Add</button>
          </form>
        </div>
      </section></template
    >
    <div
      v-if="!id && pages > 1 && ['articles', 'discovery', 'generations'].includes(section)"
      class="actions"
    >
      <button :disabled="page <= 1 || loading" @click="changePage(-1)">← Previous</button
      ><span>{{ page }} / {{ pages }}</span
      ><button :disabled="page >= pages || loading" @click="changePage(1)">Next →</button>
    </div>
  </template>
  <div v-if="wizard" class="modal-overlay" @click.self="wizard = false">
    <form
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-label="Create content"
      @submit.prevent="createGeneration"
    >
      <p class="eyebrow">CREATE / NEW DRAFT</p>
      <h2>From sources to ideas.</h2>
      <p>{{ selected.length }} selected sources.</p>
      <label class="check"><input type="checkbox" value="BLOG" v-model="outputs" />Blog post</label
      ><label class="check"
        ><input type="checkbox" value="LINKEDIN" v-model="outputs" />LinkedIn post</label
      ><label class="check"
        ><input type="checkbox" v-model="refresh" />Refresh sources (new crawl)</label
      >
      <p class="small muted">This action uses Firecrawl and OpenRouter with your credentials.</p>
      <div class="actions">
        <button type="button" @click="wizard = false">Cancel</button
        ><button class="primary" :disabled="busy || !outputs.length">Generate ↗</button>
      </div>
    </form>
  </div>
  <div v-if="regenerate" class="modal-overlay" @click.self="regenerate = false">
    <form
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-label="Regenerate versione"
      @submit.prevent="regenerateVersion"
    >
      <h2>A new perspective.</h2>
      <label>Instructions<textarea v-model="instructions" rows="5"></textarea></label
      ><label v-if="tab === 'LINKEDIN'"
        >Blog version<select v-model="dependency">
          <option value="">Keep the previous dependency</option>
          <option
            v-for="v in generation?.outputs.find((o) => o.output_type === 'BLOG')?.versions"
            :key="v.id"
            :value="v.id"
          >
            Blog v{{ v.version }}
          </option>
        </select></label
      >
      <p class="small muted">Previous versions and snapshots are preserved.</p>
      <div class="actions">
        <button type="button" @click="regenerate = false">Cancel</button
        ><button class="primary" :disabled="busy">Regenerate ↗</button>
      </div>
    </form>
  </div>
  <div v-if="catalog" class="modal-overlay" @click.self="catalog = false">
    <form
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-label="Edit catalog"
      @submit.prevent="saveCatalog"
    >
      <h2>{{ editId ? 'Edit' : 'Add' }} {{ section === 'topics' ? 'topic' : 'source' }}</h2>
      <label>Name<input v-model="name" required /></label
      ><label v-if="section === 'topics'"
        >Description<textarea v-model="description" rows="4"></textarea></label
      ><template v-else
        ><label>Website<input type="url" v-model="website" required /></label
        ><label>RSS feed<input type="url" v-model="feed" /></label
        ><button type="button" :disabled="busy || !feed" @click="testFeed">
          Test feed
        </button></template
      >
      <div class="actions">
        <button type="button" @click="catalog = false">Cancel</button
        ><button class="primary" :disabled="busy">Save</button>
      </div>
    </form>
  </div>
</template>
