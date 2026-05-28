<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import { useApp } from '../stores/app'

// 懒加载 Monaco:仅在打开文件时才拉取这部分代码,不拖累首屏
const CodeViewer = defineAsyncComponent(() => import('./CodeViewer.vue'))

const app = useApp()
const query = ref('')

function onSearch() {
  app.runSearch(query.value)
}

function openHit(filePath: string) {
  app.openFileByPath(filePath)
}
</script>

<template>
  <main class="h-full flex flex-col bg-bg-primary overflow-hidden">
    <!-- search bar -->
    <div class="flex items-center gap-2 px-6 py-2.5 border-b border-border-subtle">
      <input
        v-model="query"
        placeholder="语义检索,如「用户登录在哪实现」…"
        class="flex-1 px-3 py-1.5 bg-bg-tertiary border border-border-subtle rounded text-[0.8rem] outline-none focus:border-accent"
        @keydown.enter="onSearch"
      />
      <button
        class="px-3 py-1.5 rounded text-[0.74rem] bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
        :disabled="app.searching || !app.currentRepoId"
        @click="onSearch"
      >
        {{ app.searching ? '检索中…' : '检索' }}
      </button>
    </div>

    <!-- tabs -->
    <div class="flex px-6 border-b border-border-subtle">
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'results' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'results'"
      >
        检索结果 <span class="text-[0.62rem]">{{ app.searchHits.length }}</span>
      </div>
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'code' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'code'"
      >
        代码 <span v-if="app.openFile" class="font-mono text-[0.62rem]">· {{ app.openFile.path.split('/').pop() }}</span>
      </div>
    </div>

    <!-- results -->
    <div v-show="app.mainTab === 'results'" class="flex-1 overflow-y-auto">
      <div v-if="!app.searchHits.length" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        输入问题开始语义检索
      </div>
      <div
        v-for="hit in app.searchHits"
        :key="hit.chunk_id"
        class="px-6 py-3.5 border-b border-border-subtle cursor-pointer hover:bg-accent/[0.04]"
        @click="openHit(hit.file_path)"
      >
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[0.65rem] font-semibold uppercase px-1.5 py-0.5 rounded bg-info/15 text-info">
            {{ hit.kind ?? 'block' }}
          </span>
          <span class="font-mono text-[0.78rem] font-medium">{{ hit.symbol ?? hit.file_path.split('/').pop() }}</span>
          <span class="text-[0.67rem] text-txt-tertiary ml-auto">
            {{ hit.file_path }}:{{ hit.start_line }}-{{ hit.end_line }}
          </span>
        </div>
        <pre class="bg-[#131416] border border-border-subtle rounded p-2.5 font-mono text-[0.72rem] text-txt-secondary overflow-x-auto max-h-40">{{ hit.snippet }}</pre>
      </div>
    </div>

    <!-- code -->
    <div v-show="app.mainTab === 'code'" class="flex-1 min-h-0">
      <CodeViewer
        v-if="app.openFile"
        :content="app.openFile.content"
        :language="app.openFile.language"
        :path="app.openFile.path"
      />
      <div v-else class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        从左侧仓库结构点击文件查看代码
      </div>
    </div>
  </main>
</template>
