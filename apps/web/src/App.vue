<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionExpired, resetSession } from './data/live'
const router = useRouter()
watch(sessionExpired, (expired) => {
  if (!expired) return
  authenticated.value = false
  password.value = ''
  loginError.value = 'Your session has expired. Please sign in again.'
  void router.replace('/login')
})
const authenticated = ref(false),
  checked = ref(false),
  configured = ref(true)
const email = ref(''),
  password = ref(''),
  loginError = ref(''),
  pending = ref(false)
onMounted(async () => {
  try {
    const r = await fetch('/api/auth/session')
    const data = await r.json()
    authenticated.value = data.authenticated
    configured.value = data.configured
    if (!data.authenticated) void router.replace('/login')
    else if (router.currentRoute.value.path === '/login') void router.replace('/')
  } catch {
    loginError.value = 'Backend unavailable'
  } finally {
    checked.value = true
  }
})
async function login() {
  pending.value = true
  loginError.value = ''
  try {
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    if (!r.ok) throw new Error('Login failed. Check your credentials or try again in a minute.')
    resetSession()
    authenticated.value = true
    await router.replace('/')
    password.value = ''
  } catch (e) {
    loginError.value = String(e)
  } finally {
    pending.value = false
  }
}
async function logout() {
  await fetch('/api/auth/logout', { method: 'POST', headers: { 'X-Requested-With': 'Margin' } })
  resetSession()
  authenticated.value = false
  loginError.value = ''
  await router.replace('/login')
}
const links = [
  ['/', 'Overview'],
  ['/discovery', 'Discovery'],
  ['/articles', 'Articles'],
  ['/generations', 'Generations'],
  ['/topics', 'Topics'],
  ['/sources', 'Sources'],
  ['/settings', 'Settings'],
]
</script>
<template>
  <main v-if="!authenticated" class="login-page">
    <p class="eyebrow">MARGIN / EDITORIAL WORKSPACE</p>
    <h1>Welcome.</h1>
    <p v-if="!checked">Connecting…</p>
    <p v-else-if="!configured">
      Configure your administrator with the server admin script, then restart the backend.
    </p>
    <form v-else @submit.prevent="login" class="login-form">
      <label>Email<input v-model="email" type="email" autocomplete="username" required /></label>
      <label
        >Password<input v-model="password" type="password" autocomplete="current-password" required
      /></label>
      <button class="primary" :disabled="pending">{{ pending ? 'Signing in…' : 'Sign in' }}</button>
    </form>
    <p role="alert">{{ loginError }}</p>
  </main>
  <template v-else>
    <button class="logout-button" @click="logout">Sign out</button>
    <div class="demo-strip">
      MARGIN CONTENT STUDIO · Live workspace · Nothing is published automatically
    </div>
    <header class="site-header">
      <RouterLink to="/" class="brand" aria-label="Margin home"
        >Margin<span class="brand-mark">◉</span></RouterLink
      ><span class="workspace-label">EDITORIAL WORKSPACE</span>
    </header>
    <nav class="main-nav" aria-label="Main navigation">
      <RouterLink
        v-for="[path, label] in links"
        :key="path"
        :to="path"
        :class="{
          selected: path === '/' ? $route.path === '/' : $route.path.startsWith(path!),
        }"
        >{{ label }}</RouterLink
      ><span class="nav-caption">Discover. Think. Write.</span>
    </nav>
    <main id="main"><RouterView /></main>
    <footer>
      <span>Margin <span class="muted">/ Content Studio</span></span
      ><span>Built for thoughtful engineering.</span><span>MVP · v0.2</span>
    </footer>
  </template>
</template>
