<script setup lang="ts">
import { computed, ref } from 'vue'
import FileTree from './FileTree.vue'
import { useApp } from '../stores/app'
import type { TreeNode, WorkMode } from '../api/types'

const app = useApp()
const dropdownOpen = ref(false)
const treeFilter = ref('')

// 扁平化所有文件,供过滤定位
const flatFiles = computed(() => {
  const out: { name: string; path: string }[] = []
  const walk = (nodes: TreeNode[]) => {
    for (const n of nodes) {
      if (n.type === 'file') out.push({ name: n.name, path: n.path })
      else if (n.children) walk(n.children)
    }
  }
  walk(app.tree)
  return out
})

const filteredFiles = computed(() => {
  const q = treeFilter.value.trim().toLowerCase()
  if (!q) return []
  return flatFiles.value.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 200)
})

const modes: { key: WorkMode; icon: string; label: string }[] = [
  { key: 'search', icon: '🔍', label: '语义检索' },
  { key: 'analysis', icon: '📊', label: '代码分析' },
  { key: 'flow', icon: '🗺️', label: '逻辑地图' },
  { key: 'docs', icon: '📖', label: '文档生成' },
]

async function pickRepo(id: string) {
  dropdownOpen.value = false
  await app.selectRepo(id)
}

async function removeRepo(id: string, e: MouseEvent) {
  e.stopPropagation()
  if (confirm('删除该仓库的索引?(向量与图数据一并清除)')) {
    await app.deleteRepo(id)
  }
}
</script>

<template>
  <aside class="h-full flex flex-col bg-bg-secondary border-r border-border-subtle overflow-hidden">
    <!-- Repo selector -->
    <div class="relative m-2.5">
      <div
        class="flex items-center gap-2.5 px-3 py-2.5 bg-bg-tertiary border rounded-lg cursor-pointer"
        :class="dropdownOpen ? 'border-accent' : 'border-border-subtle'"
        @click="dropdownOpen = !dropdownOpen"
      >
        <div class="w-[30px] h-[30px] bg-accent/10 border border-accent/20 rounded grid place-items-center">
          📦
        </div>
        <div class="min-w-0 flex-1">
          <div class="font-semibold text-[0.82rem] truncate">
            {{ app.currentRepo?.name ?? '未选择仓库' }}
          </div>
          <div class="text-[0.67rem] text-txt-tertiary">
            {{ app.currentRepo ? `${app.currentRepo.file_count} 文件 · ${app.currentRepo.chunk_count} 块` : '点击索引仓库' }}
          </div>
        </div>
        <span class="text-txt-tertiary text-[0.67rem]">▾</span>
      </div>
      <div
        v-if="dropdownOpen"
        class="absolute top-full left-0 right-0 mt-1 bg-bg-elevated border border-border-medium rounded-lg shadow-lg z-50 overflow-hidden"
      >
        <div
          v-for="r in app.repos"
          :key="r.id"
          class="group flex items-center gap-2 px-3 py-2 cursor-pointer text-[0.78rem] hover:bg-bg-hover"
          :class="r.id === app.currentRepoId ? 'text-accent' : 'text-txt-secondary'"
          @click="pickRepo(r.id)"
        >
          <span>📦</span>
          <div class="flex-1 min-w-0">
            <div class="truncate">{{ r.name }}</div>
            <div class="text-[0.62rem] text-txt-tertiary">{{ r.status }}</div>
          </div>
          <button
            class="opacity-0 group-hover:opacity-100 w-5 h-5 grid place-items-center rounded text-txt-tertiary hover:text-err hover:bg-err/10"
            title="删除仓库"
            @click="removeRepo(r.id, $event)"
          >
            ✕
          </button>
        </div>
        <div v-if="!app.repos.length" class="px-3 py-3 text-[0.72rem] text-txt-tertiary">
          还没有仓库,点右上角「索引仓库」
        </div>
      </div>
    </div>

    <!-- Work modes -->
    <div class="px-3.5 pt-2 pb-1.5">
      <div class="text-[0.65rem] font-semibold uppercase tracking-wider text-txt-tertiary mb-2">
        工作模式
      </div>
      <ul class="space-y-0.5">
        <li
          v-for="m in modes"
          :key="m.key"
          class="flex items-center gap-2.5 px-3 py-1.5 rounded cursor-pointer text-[0.78rem]"
          :class="app.workMode === m.key ? 'bg-accent/10 text-accent' : 'text-txt-secondary hover:bg-bg-hover hover:text-txt-primary'"
          @click="app.workMode = m.key"
        >
          <span>{{ m.icon }}</span><span>{{ m.label }}</span>
        </li>
      </ul>
    </div>

    <div class="h-px bg-border-subtle mx-3.5 my-1.5" />

    <!-- Repo tree -->
    <div class="px-3.5 pt-1.5 pb-1.5">
      <div class="text-[0.65rem] font-semibold uppercase tracking-wider text-txt-tertiary mb-1.5">
        仓库结构
      </div>
      <input
        v-model="treeFilter"
        placeholder="输入文件名定位…"
        class="w-full px-2.5 py-1.5 bg-bg-tertiary border border-border-subtle rounded text-[0.72rem] outline-none focus:border-accent"
      />
    </div>
    <div class="flex-1 overflow-y-auto px-2 pb-3">
      <!-- 过滤模式:扁平结果 -->
      <template v-if="treeFilter.trim()">
        <div
          v-for="f in filteredFiles"
          :key="f.path"
          class="flex items-center gap-1.5 py-1 px-2 rounded cursor-pointer text-[0.74rem] text-txt-secondary hover:bg-bg-hover hover:text-txt-primary"
          :class="{ 'text-accent bg-accent/10': app.openFile?.path === f.path }"
          :title="f.path"
          @click="app.openFileByPath(f.path)"
        >
          <span>📄</span>
          <span class="truncate">{{ f.name }}</span>
          <span class="ml-auto text-[0.6rem] text-txt-tertiary truncate max-w-[90px]">{{ f.path }}</span>
        </div>
        <div v-if="!filteredFiles.length" class="px-2 py-3 text-[0.72rem] text-txt-tertiary">无匹配文件</div>
      </template>
      <!-- 正常树 -->
      <template v-else>
        <FileTree v-if="app.tree.length" :nodes="app.tree" />
        <div v-else class="px-2 py-3 text-[0.72rem] text-txt-tertiary">
          {{ app.currentRepo?.status === 'ready' ? '空' : '仓库未就绪 / 未索引' }}
        </div>
      </template>
    </div>
  </aside>
</template>
