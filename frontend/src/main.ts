import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'
import { useApp } from './stores/app'
import { i18n } from './i18n'

const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(i18n)

// 刷新恢复:先从 localStorage 还原,再订阅变更做防抖持久化
const store = useApp(pinia)
store.hydrate()
let saveTimer: number | undefined
store.$subscribe(() => {
  clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => store.persist(), 400)
})

app.mount('#app')
