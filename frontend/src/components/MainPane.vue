<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useApp } from '../stores/app'
import type { CodeChunkHit } from '../api/types'

// 懒加载 Monaco / Mermaid:用到时才拉取,不拖累首屏
const CodeViewer = defineAsyncComponent(() => import('./CodeViewer.vue'))
const GraphView = defineAsyncComponent(() => import('./GraphView.vue'))
const DocsView = defineAsyncComponent(() => import('./DocsView.vue'))
const AnalysisView = defineAsyncComponent(() => import('./AnalysisView.vue'))

const app = useApp()
const query = ref(app.searchQuery)

// 右键「查看调用图」上下文菜单
const ctx = ref<{ show: boolean; x: number; y: number; hit: CodeChunkHit | null }>({
  show: false,
  x: 0,
  y: 0,
  hit: null,
})
function onCtx(e: MouseEvent, hit: CodeChunkHit) {
  if (!hit.symbol) return // 无符号名(整块/配置)无法定位调用图
  ctx.value = { show: true, x: e.clientX, y: e.clientY, hit }
}
function viewGraph() {
  const h = ctx.value.hit
  if (h?.symbol) app.openCallGraph(`${h.file_path}::${h.symbol}`, h.symbol)
  ctx.value.show = false
}

watch(
  () => app.searchQuery,
  (v) => {
    query.value = v
  },
)

const LANG_LABEL: Record<string, string> = {
  java: 'Java',
  javascript: 'JS',
  typescript: 'TS',
  tsx: 'TSX',
  vue: 'Vue',
  xml: 'XML',
}

const langs = computed(() => app.repoLanguages)

function onSearch() {
  app.runSearch(query.value)
}

function openHit(hit: CodeChunkHit) {
  app.openFileByPath(hit.file_path, [hit.start_line, hit.end_line])
}
</script>

<template>
  <main class="h-full flex flex-col bg-bg-primary overflow-hidden">
    <!-- search bar -->
    <div class="px-6 py-2.5 border-b border-border-subtle">
      <div class="flex items-center gap-2">
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
      <!-- language filter: 不选=全部 -->
      <div v-if="langs.length" class="flex items-center gap-1.5 mt-2 flex-wrap">
        <span class="text-[0.62rem] text-txt-tertiary mr-0.5">语言</span>
        <button
          v-for="l in langs"
          :key="l"
          class="px-2 py-0.5 rounded-full text-[0.65rem] border transition-colors"
          :class="app.searchLanguages.includes(l)
            ? 'border-accent text-accent bg-accent/10'
            : 'border-border-subtle text-txt-tertiary hover:text-txt-secondary'"
          @click="app.toggleLanguage(l)"
        >
          {{ LANG_LABEL[l] ?? l }}
        </button>
      </div>
    </div>

    <!-- tabs -->
    <div class="flex px-6 border-b border-border-subtle">
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'results' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'results'"
      >
        语义检索 <span class="text-[0.62rem]">{{ app.searchHits.length }}</span>
      </div>
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'deps' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'deps'"
      >
        代码分析
      </div>
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'graph' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'graph'"
      >
        逻辑地图<span v-if="app.graphTarget" class="font-mono text-[0.62rem]">· {{ app.graphTarget.label }}</span>
      </div>
      <div
        class="px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2"
        :class="app.mainTab === 'docs' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'docs'"
      >
        文档生成
      </div>
      <div
        class="group px-4 py-2 text-[0.76rem] font-medium cursor-pointer border-b-2 flex items-center gap-1.5"
        :class="app.mainTab === 'code' ? 'text-accent border-accent' : 'text-txt-tertiary border-transparent hover:text-txt-secondary'"
        @click="app.mainTab = 'code'"
      >
        代码
        <span v-if="app.openFile" class="font-mono text-[0.62rem]">· {{ app.openFile.path.split('/').pop() }}</span>
        <button
          v-if="app.openFile"
          class="opacity-0 group-hover:opacity-100 w-4 h-4 grid place-items-center rounded text-txt-tertiary hover:text-err hover:bg-err/10 text-[0.7rem] leading-none"
          title="关闭文件"
          @click.stop="app.closeFile()"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- results -->
    <div v-show="app.mainTab === 'results'" class="flex-1 overflow-y-auto">
      <!-- loading -->
      <div v-if="app.searching" class="flex flex-col items-center justify-center py-20 gap-3 text-txt-tertiary">
        <div class="w-7 h-7 border-2 border-border-medium border-t-accent rounded-full animate-spin" />
        <div class="text-[0.78rem]">正在检索 “{{ app.searchQuery }}” …</div>
      </div>
      <div v-else-if="!app.searchHits.length" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        输入问题开始语义检索
      </div>
      <template v-else>
        <div
          v-for="hit in app.searchHits"
          :key="hit.chunk_id"
          class="px-6 py-3.5 border-b border-border-subtle cursor-pointer hover:bg-accent/[0.04]"
          @click="openHit(hit)"
          @contextmenu.prevent="onCtx($event, hit)"
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
      </template>
    </div>

    <!-- code -->
    <div v-show="app.mainTab === 'code'" class="flex-1 min-h-0">
      <CodeViewer
        v-if="app.openFile"
        :content="app.openFile.content"
        :language="app.openFile.language"
        :path="app.openFile.path"
        :highlight="app.openFile.highlight ?? null"
      />
      <div v-else class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        从左侧仓库结构点击文件查看代码
      </div>
    </div>

    <!-- graph -->
    <div v-show="app.mainTab === 'graph'" class="flex-1 min-h-0">
      <GraphView />
    </div>

    <!-- deps -->
    <div v-show="app.mainTab === 'deps'" class="flex-1 min-h-0">
      <AnalysisView />
    </div>

    <!-- docs -->
    <div v-show="app.mainTab === 'docs'" class="flex-1 min-h-0">
      <DocsView />
    </div>

    <!-- 右键菜单 -->
    <template v-if="ctx.show">
      <div class="fixed inset-0 z-40" @click="ctx.show = false" @contextmenu.prevent="ctx.show = false" />
      <div
        class="fixed z-50 bg-bg-elevated border border-border-medium rounded-md shadow-lg py-1 text-[0.74rem]"
        :style="{ left: ctx.x + 'px', top: ctx.y + 'px' }"
      >
        <button class="block w-full text-left px-3 py-1.5 hover:bg-bg-hover text-txt-secondary hover:text-txt-primary" @click="viewGraph">
          🗺️ 查看调用图
        </button>
      </div>
    </template>
  </main>
</template>
