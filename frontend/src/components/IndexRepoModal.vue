<script setup lang="ts">
import { ref } from 'vue'
import { api, streamGetSSE } from '../api/client'
import { useApp } from '../stores/app'

const emit = defineEmits<{ close: [] }>()
const app = useApp()

const path = ref('')
const name = ref('')
const indexing = ref(false)
const progress = ref({ current: 0, total: 0, stage: '', file: '' })
const done = ref(false)

async function start() {
  if (!path.value.trim()) return
  indexing.value = true
  try {
    const repo = await api.createRepo(path.value.trim(), name.value.trim() || undefined)
    await streamGetSSE(`/api/repos/${repo.id}/index`, (ev) => {
      progress.value = {
        current: ev.current ?? progress.value.current,
        total: ev.total ?? progress.value.total,
        stage: ev.stage ?? progress.value.stage,
        file: ev.file ?? '',
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
    <div class="bg-bg-secondary border border-border-medium rounded-xl shadow-2xl w-[min(520px,90vw)]">
      <div class="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
        <div class="font-display text-[1.05rem]">＋ 索引新仓库</div>
        <button class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:bg-bg-hover" @click="emit('close')">✕</button>
      </div>
      <div class="p-5 space-y-4">
        <div>
          <label class="block text-[0.74rem] text-txt-secondary mb-1.5">本地仓库路径</label>
          <input
            v-model="path"
            placeholder="E:\\code\\my-project"
            spellcheck="false"
            class="w-full px-3 py-2 bg-bg-tertiary border border-border-subtle rounded text-[0.82rem] outline-none focus:border-accent"
          />
        </div>
        <div>
          <label class="block text-[0.74rem] text-txt-secondary mb-1.5">名称(可选)</label>
          <input
            v-model="name"
            spellcheck="false"
            class="w-full px-3 py-2 bg-bg-tertiary border border-border-subtle rounded text-[0.82rem] outline-none focus:border-accent"
          />
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
      </div>
      <div class="px-5 py-3.5 border-t border-border-subtle flex justify-end gap-2">
        <button class="px-4 py-1.5 rounded text-[0.78rem] border border-border-subtle text-txt-secondary hover:text-txt-primary" @click="emit('close')">
          {{ done ? '关闭' : '取消' }}
        </button>
        <button
          class="px-4 py-1.5 rounded text-[0.78rem] bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
          :disabled="indexing || !path"
          @click="start"
        >
          {{ indexing ? '索引中…' : '开始索引' }}
        </button>
      </div>
    </div>
  </div>
</template>
