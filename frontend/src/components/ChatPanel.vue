<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamSSE } from '../api/client'
import type { ChatRef } from '../api/types'
import { useApp } from '../stores/app'

interface Msg {
  role: 'user' | 'assistant'
  content: string
  refs?: ChatRef[]
}

const app = useApp()
const input = ref('')
const messages = ref<Msg[]>([])
const streaming = ref(false)
const listEl = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

function render(md: string): string {
  return DOMPurify.sanitize(marked.parse(md, { async: false }) as string)
}

async function scrollDown() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value || !app.currentRepoId) return
  input.value = ''

  const history = messages.value.map((m) => ({ role: m.role, content: m.content }))
  messages.value.push({ role: 'user', content: text })
  const ai: Msg = { role: 'assistant', content: '', refs: [] }
  messages.value.push(ai)
  streaming.value = true
  scrollDown()

  abort = new AbortController()
  const sel = app.selection
  try {
    await streamSSE(
      '/api/chat',
      {
        repo_id: app.currentRepoId,
        message: text,
        history,
        selected_code: sel?.code ?? null,
        selected_file: sel?.file ?? null,
        selected_range: sel?.range ?? null,
      },
      (ev) => {
        if (ev.type === 'refs') ai.refs = ev.refs
        else if (ev.type === 'token') {
          ai.content += ev.text
          scrollDown()
        } else if (ev.type === 'error') ai.content += `\n\n_出错: ${ev.message}_`
      },
      abort.signal,
    )
  } catch (e: any) {
    if (e?.name !== 'AbortError') ai.content += `\n\n_请求失败: ${e}_`
  } finally {
    streaming.value = false
    abort = null
  }
}

function stop() {
  abort?.abort()
}

function clearChat() {
  messages.value = []
}

function openRef(r: ChatRef) {
  app.openFileByPath(r.file)
}
</script>

<template>
  <aside class="h-full flex flex-col bg-bg-secondary border-l border-border-subtle overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
      <div class="font-semibold text-[0.84rem] flex items-center gap-2">💬 代码助手</div>
      <button class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:bg-bg-hover" title="清空" @click="clearChat">🗑</button>
    </div>

    <div ref="listEl" class="flex-1 overflow-y-auto p-4 space-y-3.5">
      <div v-if="!messages.length" class="text-[0.78rem] text-txt-secondary leading-relaxed">
        用自然语言提问。<strong class="text-txt-primary">在编辑器里选中代码</strong>后提问,会针对选中片段;不选则基于整个代码库。
      </div>
      <div v-for="(m, i) in messages" :key="i" class="flex gap-2.5" :class="m.role === 'user' ? 'flex-row-reverse' : ''">
        <div
          class="w-7 h-7 rounded-md grid place-items-center text-[0.7rem] font-semibold shrink-0"
          :class="m.role === 'user' ? 'bg-info/15 text-info' : 'bg-accent/10 text-accent border border-accent/20'"
        >
          {{ m.role === 'user' ? 'U' : 'CL' }}
        </div>
        <div class="min-w-0 max-w-[85%]">
          <div
            class="px-3.5 py-2.5 rounded-lg text-[0.78rem] leading-relaxed"
            :class="m.role === 'user' ? 'bg-accent/10 text-txt-primary' : 'bg-bg-tertiary border border-border-subtle text-txt-secondary'"
          >
            <div v-if="m.role === 'assistant'" class="md" v-html="render(m.content || '…')" />
            <template v-else>{{ m.content }}</template>
          </div>
          <div v-if="m.refs && m.refs.length" class="mt-1.5 space-y-1">
            <div
              v-for="(r, j) in m.refs"
              :key="j"
              class="flex items-center gap-2 px-2.5 py-1.5 bg-bg-tertiary border border-border-subtle rounded cursor-pointer hover:border-accent"
              @click="openRef(r)"
            >
              <span class="text-[0.7rem]">📄</span>
              <span class="font-mono text-[0.68rem] text-txt-primary truncate">{{ r.file }}:{{ r.start_line }}</span>
              <span v-if="r.symbol" class="text-[0.62rem] text-txt-tertiary ml-auto">{{ r.symbol }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- selection context banner -->
    <div v-if="app.selection" class="mx-4 mb-1.5 px-3 py-1.5 bg-accent/10 border border-accent/20 rounded text-[0.68rem] text-accent flex items-center gap-2">
      <span class="truncate">已选中 {{ app.selection.file.split('/').pop() }}:{{ app.selection.range[0] }}-{{ app.selection.range[1] }},提问将基于此片段</span>
      <button class="ml-auto hover:text-txt-primary" @click="app.setSelection(null)">✕</button>
    </div>

    <div class="p-4 border-t border-border-subtle">
      <div class="flex gap-2 items-end">
        <textarea
          v-model="input"
          rows="1"
          placeholder="输入问题…"
          class="flex-1 px-3.5 py-2.5 bg-bg-tertiary border border-border-subtle rounded-lg text-[0.82rem] outline-none focus:border-accent resize-none max-h-32"
          @keydown.enter.exact.prevent="send"
        />
        <button
          v-if="!streaming"
          class="w-10 h-10 bg-accent rounded-lg text-bg-primary grid place-items-center hover:bg-accent-dim disabled:opacity-40"
          :disabled="!app.currentRepoId"
          @click="send"
        >
          ↑
        </button>
        <button v-else class="w-10 h-10 bg-err/80 rounded-lg text-white grid place-items-center" @click="stop">■</button>
      </div>
      <div class="text-[0.6rem] text-txt-tertiary mt-1.5">Enter 发送 · Shift+Enter 换行</div>
    </div>
  </aside>
</template>
