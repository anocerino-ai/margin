import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import '@fontsource-variable/inter'
import './style.css'
import App from './App.vue'
import LiveWorkspace from './pages/LiveWorkspace.vue'
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: LiveWorkspace },
    { path: '/articles/:id?', component: LiveWorkspace },
    { path: '/discovery/:id?', component: LiveWorkspace },
    { path: '/generations/:id?', component: LiveWorkspace },
    { path: '/topics', component: LiveWorkspace, props: { kind: 'topics' } },
    { path: '/sources', component: LiveWorkspace, props: { kind: 'sources' } },
    { path: '/settings', component: LiveWorkspace },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
createApp(App).use(router).mount('#app')
