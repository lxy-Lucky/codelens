<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamSSE } from '../api/client'
import { useApp } from '../stores/app'

const { t, locale } = useI18n()
const app = useApp()
const generating = ref(false)
const markdown = ref('')
const genPath = ref<string | null>(null)
const errorMsg = ref('')
let abort: AbortController | null = null

const rendered = computed(() => DOMPurify.sanitize(marked.parse(markdown.value, { async: false }) as string))
const staleFile = computed(() => !!genPath.value && genPath.value !== app.openFile?.path)

async function generate() {
  if (!app.currentRepoId || !app.openFile || generating.value) return
  const path = app.openFile.path
  markdown.value = ''
  errorMsg.value = ''
  genPath.value = path
  generating.value = true
  abort = new AbortController()
  try {
    await streamSSE(
      '/api/docs',
      { repo_id: app.currentRepoId, path, locale: locale.value },
      (ev) => {
        if (ev.type === 'token') markdown.value += ev.text
        else if (ev.type === 'error') errorMsg.value = ev.message
      },
      abort.signal,
    )
  } catch (e: any) {
    if (e?.name !== 'AbortError') errorMsg.value = String(e)
  } finally {
    generating.value = false
    abort = null
  }
}

function stop() {
  abort?.abort()
}

function copy() {
  navigator.clipboard.writeText(markdown.value)
}

function exportMd() {
  const name = (genPath.value?.split('/').pop() ?? 'docs') + '.md'
  const blob = new Blob([markdown.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex items-center gap-3 px-6 py-2 border-b border-border-subtle text-[0.74rem]">
      <button
        v-if="!generating"
        class="px-3 py-1 rounded bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
        :disabled="!app.openFile"
        @click="generate"
      >
        {{ markdown ? t('docs.regenerate') : t('docs.generate') }}
      </button>
      <button v-else class="px-3 py-1 rounded bg-err/80 text-white" @click="stop">{{ t('common.stop') }}</button>

      <span v-if="app.openFile" class="text-txt-secondary font-mono truncate">
        {{ app.openFile.path }}
      </span>

      <div class="ml-auto flex items-center gap-2">
        <button v-if="markdown" class="px-2 py-1 rounded border border-border-subtle text-txt-tertiary hover:text-accent hover:border-accent" @click="copy">{{ t('common.copy') }}</button>
        <button v-if="markdown" class="px-2 py-1 rounded border border-border-subtle text-txt-tertiary hover:text-accent hover:border-accent" @click="exportMd">{{ t('docs.export') }}</button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-8 py-6">
      <div v-if="!app.openFile" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        {{ t('docs.emptyHint') }}
      </div>
      <template v-else>
        <div v-if="staleFile" class="mb-4 px-3 py-2 rounded bg-warn/10 border border-warn/20 text-warn text-[0.72rem]">
          {{ t('docs.staleHint', { name: genPath?.split('/').pop() }) }}
        </div>
        <div v-if="errorMsg" class="mb-4 text-err text-[0.76rem]">{{ errorMsg }}</div>
        <div v-if="!markdown && !generating" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
          {{ t('docs.clickHint', { name: app.openFile.path.split('/').pop() }) }}
        </div>
        <div v-if="generating && !markdown" class="flex items-center gap-2 text-txt-tertiary text-[0.78rem]">
          <div class="w-5 h-5 border-2 border-border-medium border-t-accent rounded-full animate-spin" />
          {{ t('docs.generating') }}
        </div>
        <div v-if="markdown" class="md max-w-3xl" v-html="rendered" />
      </template>
    </div>
  </div>
</template>
