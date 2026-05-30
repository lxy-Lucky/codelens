<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamSSE } from '../api/client'
import type { ChatMsg, ChatRef } from '../api/types'
import { useApp } from '../stores/app'

const { t, locale } = useI18n()
const app = useApp()
const input = ref('')
const streaming = ref(false)
const listEl = ref<HTMLElement | null>(null)
const showHistory = ref(false)
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

  const history = app.chatMessages.map((m) => ({ role: m.role, content: m.content }))
  app.chatMessages.push({ role: 'user', content: text })
  const ai: ChatMsg = { role: 'assistant', content: '', refs: [] }
  app.chatMessages.push(ai)
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
        languages: app.searchLanguages,
        locale: locale.value,
      },
      (ev) => {
        if (ev.type === 'refs') ai.refs = ev.refs
        else if (ev.type === 'token') {
          ai.content += ev.text
          scrollDown()
        } else if (ev.type === 'error') ai.content += t('chat.chatErr', { msg: ev.message })
      },
      abort.signal,
    )
  } catch (e: any) {
    if (e?.name !== 'AbortError') ai.content += t('chat.reqFail', { msg: String(e) })
  } finally {
    streaming.value = false
    abort = null
  }
}

function stop() {
  abort?.abort()
}

function clearChat() {
  app.chatMessages = []
}

function openRef(r: ChatRef) {
  app.openFileByPath(r.file, [r.start_line, r.end_line])
}

function rerunSearch(q: string) {
  showHistory.value = false
  app.runSearch(q)
}

function removeHistory(q: string, e: MouseEvent) {
  e.stopPropagation()
  app.removeSearchHistory(q)
}

function isTyping(m: ChatMsg, idx: number): boolean {
  return streaming.value && idx === app.chatMessages.length - 1 && m.role === 'assistant' && !m.content
}
</script>

<template>
  <aside class="h-full flex flex-col bg-bg-secondary border-l border-border-subtle overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
      <div class="font-semibold text-[0.84rem] flex items-center gap-2">{{ t('chat.title') }}</div>
      <div class="flex items-center gap-1 relative">
        <button
          class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:bg-bg-hover"
          :title="t('chat.history')"
          @click="showHistory = !showHistory"
        >
          🕘
        </button>
        <button class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:bg-bg-hover" :title="t('chat.clearChat')" @click="clearChat">🗑</button>

        <!-- 检索历史下拉 -->
        <div
          v-if="showHistory"
          class="absolute right-0 top-9 w-72 max-h-72 overflow-y-auto bg-bg-elevated border border-border-medium rounded-lg shadow-lg z-50 py-1"
        >
          <div class="px-3 py-1.5 text-[0.62rem] uppercase tracking-wider text-txt-tertiary">{{ t('chat.historyTitle') }}</div>
          <div v-if="!app.searchHistory.length" class="px-3 py-2 text-[0.72rem] text-txt-tertiary">{{ t('chat.noHistory') }}</div>
          <div
            v-for="(q, i) in app.searchHistory"
            :key="i"
            class="group flex items-center gap-1.5 px-3 py-1.5 hover:bg-bg-hover cursor-pointer"
            :title="q"
            @click="rerunSearch(q)"
          >
            <span class="flex-1 truncate text-[0.74rem] text-txt-secondary group-hover:text-txt-primary">{{ q }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 text-[0.64rem] px-1.5 py-0.5 rounded border border-border-subtle text-accent hover:bg-accent/10 whitespace-nowrap"
              @click.stop="rerunSearch(q)"
            >
              {{ t('chat.rerun') }}
            </button>
            <button
              class="opacity-0 group-hover:opacity-100 w-5 h-5 grid place-items-center rounded text-txt-tertiary hover:text-err hover:bg-err/10"
              :title="t('chat.deleteHistory')"
              @click="removeHistory(q, $event)"
            >
              ✕
            </button>
          </div>
        </div>
      </div>
    </div>

    <div ref="listEl" class="flex-1 overflow-y-auto p-4 space-y-3.5">
      <div v-if="!app.chatMessages.length" class="text-[0.78rem] text-txt-secondary leading-relaxed" v-html="render(t('chat.emptyHint'))" />
      <div v-for="(m, i) in app.chatMessages" :key="i" class="flex gap-2.5" :class="m.role === 'user' ? 'flex-row-reverse' : ''">
        <div
          class="w-7 h-7 rounded-md grid place-items-center text-[0.7rem] font-semibold shrink-0"
          :class="m.role === 'user' ? 'bg-info/15 text-info' : 'bg-accent/10 text-accent border border-accent/20'"
        >
          {{ m.role === 'user' ? 'U' : 'CL' }}
        </div>
        <div class="min-w-0 max-w-[85%]">
          <div
            class="px-3.5 py-2.5 rounded-lg text-[0.78rem] leading-relaxed break-words overflow-hidden"
            :class="m.role === 'user' ? 'bg-accent/10 text-txt-primary' : 'bg-bg-tertiary border border-border-subtle text-txt-secondary'"
          >
            <div v-if="isTyping(m, i)" class="flex gap-1 py-1">
              <span class="w-1.5 h-1.5 rounded-full bg-txt-tertiary animate-bounce" style="animation-delay:0ms" />
              <span class="w-1.5 h-1.5 rounded-full bg-txt-tertiary animate-bounce" style="animation-delay:150ms" />
              <span class="w-1.5 h-1.5 rounded-full bg-txt-tertiary animate-bounce" style="animation-delay:300ms" />
            </div>
            <div v-else-if="m.role === 'assistant'" class="md" v-html="render(m.content)" />
            <template v-else>{{ m.content }}</template>
          </div>
          <div v-if="m.refs && m.refs.length" class="mt-1.5 space-y-1">
            <div
              v-for="(r, j) in m.refs"
              :key="j"
              class="flex items-center gap-2 px-2.5 py-1.5 bg-bg-tertiary border border-border-subtle rounded cursor-pointer hover:border-accent min-w-0"
              :title="`${r.file}:${r.start_line}`"
              @click="openRef(r)"
            >
              <span class="text-[0.7rem] shrink-0">📄</span>
              <span class="font-mono text-[0.68rem] text-txt-primary truncate flex-1 min-w-0">{{ r.file }}:{{ r.start_line }}</span>
              <span v-if="r.symbol" class="text-[0.62rem] text-txt-tertiary shrink-0 max-w-[35%] truncate">{{ r.symbol }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="app.selection" class="mx-4 mb-1.5 px-3 py-1.5 bg-accent/10 border border-accent/20 rounded text-[0.68rem] text-accent flex items-center gap-2">
      <span class="truncate">
        {{ t('chat.selectionTip', { file: app.selection.file.split('/').pop(), a: app.selection.range[0], b: app.selection.range[1] }) }}
      </span>
      <button class="ml-auto hover:text-txt-primary" @click="app.setSelection(null)">✕</button>
    </div>

    <div class="p-4 border-t border-border-subtle">
      <div class="flex gap-2 items-end">
        <textarea
          v-model="input"
          rows="1"
          :placeholder="t('chat.inputPlaceholder')"
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
      <div class="text-[0.6rem] text-txt-tertiary mt-1.5">{{ t('chat.enterTip') }}</div>
    </div>
  </aside>
</template>
