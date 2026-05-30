<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, streamGetSSE } from '../api/client'
import type { FsEntry } from '../api/types'
import { useApp } from '../stores/app'

const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const app = useApp()

const path = ref('')
const name = ref('')
// 默认 excludes(每行一条 glob);与后端 schemas.IndexRepoRequest 默认值保持一致
const excludesText = ref('node_modules\n.git\ndist\nbuild\ntarget\nvendor')

const indexing = ref(false)
const progress = ref({ current: 0, total: 0, stage: '', file: '' })
const done = ref(false)
const errorLog = ref<string[]>([])

// ─── 路径自动补全 ───
const suggestions = ref<FsEntry[]>([])
const showSug = ref(false)
const inputEl = ref<HTMLInputElement | null>(null)
let debounceTimer: number | undefined

async function fetchSug(p: string) {
  try {
    const r = await api.fsList(p)
    suggestions.value = r.entries
  } catch {
    suggestions.value = []
  }
}

watch(path, (v) => {
  // 输入变化时,300ms 防抖拉子目录列表
  clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    if (!v.trim()) {
      suggestions.value = []
      return
    }
    fetchSug(v)
  }, 250)
})

function onFocus() {
  showSug.value = true
  if (!suggestions.value.length && path.value.trim()) fetchSug(path.value)
}

function onBlur() {
  // 给点击补全项留时间
  setTimeout(() => (showSug.value = false), 150)
}

function pickSug(s: FsEntry) {
  path.value = s.path
  suggestions.value = []
  inputEl.value?.focus()
  // 用户选了后,继续拉它的子目录(便于继续往下钻)
  fetchSug(s.path)
}

async function start() {
  if (!path.value.trim()) return
  indexing.value = true
  errorLog.value = []
  const excludes = excludesText.value
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
  try {
    const repo = await api.createRepo(path.value.trim(), name.value.trim() || undefined, excludes)
    await streamGetSSE(`/api/repos/${repo.id}/index`, (ev) => {
      progress.value = {
        current: ev.current ?? progress.value.current,
        total: ev.total ?? progress.value.total,
        stage: ev.stage ?? progress.value.stage,
        file: ev.file ?? '',
      }
      if ((ev.stage === 'file_error' || ev.stage === 'error') && ev.message) {
        errorLog.value.push(`${ev.file ?? ''}: ${ev.message}`)
      }
      if (ev.stage === 'done' || ev.stage === 'error') done.value = true
    })
    await app.loadRepos()
    await app.selectRepo(repo.id)
  } catch (e) {
    progress.value.stage = 'error: ' + e
  } finally {
    indexing.value = false
  }
}

const pct = () =>
  progress.value.total ? Math.round((progress.value.current / progress.value.total) * 100) : 0
</script>

<template>
  <div class="fixed inset-0 bg-black/60 backdrop-blur-sm grid place-items-center z-[500]" @click.self="emit('close')">
    <div class="bg-bg-secondary border border-border-medium rounded-xl shadow-2xl w-[min(560px,92vw)]">
      <div class="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
        <div class="font-display text-[1.05rem]">{{ t('indexModal.title') }}</div>
        <button class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:bg-bg-hover" @click="emit('close')">✕</button>
      </div>
      <div class="p-5 space-y-4">
        <!-- 路径 + 自动补全 -->
        <div class="relative">
          <label class="block text-[0.74rem] text-txt-secondary mb-1.5">{{ t('indexModal.pathLabel') }}</label>
          <input
            ref="inputEl"
            v-model="path"
            :placeholder="t('indexModal.pathPlaceholder')"
            spellcheck="false"
            autocomplete="off"
            class="w-full px-3 py-2 bg-bg-tertiary border border-border-subtle rounded text-[0.82rem] outline-none focus:border-accent font-mono"
            @focus="onFocus"
            @blur="onBlur"
          />
          <div
            v-if="showSug && suggestions.length"
            class="absolute left-0 right-0 mt-1 max-h-64 overflow-y-auto bg-bg-elevated border border-border-medium rounded-md shadow-lg z-20"
          >
            <div class="px-3 py-1.5 text-[0.62rem] uppercase tracking-wider text-txt-tertiary border-b border-border-subtle">
              {{ t('indexModal.suggestPath') }}
            </div>
            <button
              v-for="s in suggestions"
              :key="s.path"
              type="button"
              class="block w-full text-left px-3 py-1.5 text-[0.74rem] font-mono text-txt-secondary hover:bg-bg-hover hover:text-accent truncate"
              :title="s.path"
              @mousedown.prevent="pickSug(s)"
            >
              📁 {{ s.name }}
            </button>
          </div>
        </div>

        <div>
          <label class="block text-[0.74rem] text-txt-secondary mb-1.5">{{ t('indexModal.nameLabel') }}</label>
          <input
            v-model="name"
            spellcheck="false"
            class="w-full px-3 py-2 bg-bg-tertiary border border-border-subtle rounded text-[0.82rem] outline-none focus:border-accent"
          />
        </div>

        <!-- excludes 多行 glob -->
        <div>
          <label class="block text-[0.74rem] text-txt-secondary mb-1.5">{{ t('indexModal.excludesLabel') }}</label>
          <textarea
            v-model="excludesText"
            rows="5"
            spellcheck="false"
            class="w-full px-3 py-2 bg-bg-tertiary border border-border-subtle rounded text-[0.78rem] outline-none focus:border-accent font-mono resize-y"
          />
          <div class="text-[0.62rem] text-txt-tertiary mt-1">{{ t('indexModal.excludesHint') }}</div>
        </div>

        <div v-if="indexing || done" class="bg-bg-tertiary border border-border-subtle rounded p-3">
          <div class="flex justify-between text-[0.7rem] text-txt-secondary mb-1.5">
            <span>{{ progress.stage }}</span>
            <span>{{ progress.current }}/{{ progress.total }} ({{ pct() }}%)</span>
          </div>
          <div class="h-1.5 bg-bg-elevated rounded overflow-hidden">
            <div class="h-full bg-accent transition-all" :style="{ width: pct() + '%' }" />
          </div>
          <div class="text-[0.62rem] text-txt-tertiary mt-1.5 truncate font-mono">{{ progress.file }}</div>
        </div>

        <div v-if="errorLog.length" class="bg-err/10 border border-err/30 rounded p-3 max-h-40 overflow-y-auto">
          <div class="text-[0.7rem] font-semibold text-err mb-1.5">{{ t('indexModal.errors', { count: errorLog.length }) }}</div>
          <div v-for="(msg, i) in errorLog" :key="i" class="text-[0.64rem] text-err/90 font-mono break-all mb-1">
            {{ msg }}
          </div>
        </div>
      </div>
      <div class="px-5 py-3.5 border-t border-border-subtle flex justify-end gap-2">
        <button class="px-4 py-1.5 rounded text-[0.78rem] border border-border-subtle text-txt-secondary hover:text-txt-primary" @click="emit('close')">
          {{ done ? t('indexModal.close') : t('indexModal.cancel') }}
        </button>
        <button
          class="px-4 py-1.5 rounded text-[0.78rem] bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
          :disabled="indexing || !path"
          @click="start"
        >
          {{ indexing ? t('indexModal.indexing') : t('indexModal.start') }}
        </button>
      </div>
    </div>
  </div>
</template>
