<script setup lang="ts">
import { ref } from 'vue'
import type { TreeNode } from '../api/types'
import { useApp } from '../stores/app'

defineProps<{ nodes: TreeNode[]; depth?: number }>()
const app = useApp()
const expanded = ref<Record<string, boolean>>({})

function toggle(path: string) {
  expanded.value[path] = !expanded.value[path]
}
</script>

<template>
  <div>
    <template v-for="node in nodes" :key="node.path">
      <div
        class="flex items-center gap-1.5 py-1 rounded cursor-pointer text-[0.74rem] text-txt-secondary hover:bg-bg-hover hover:text-txt-primary"
        :class="{ 'text-accent bg-accent/10': app.openFile?.path === node.path }"
        :style="{ paddingLeft: 8 + (depth ?? 0) * 12 + 'px' }"
        @click="node.type === 'dir' ? toggle(node.path) : app.openFileByPath(node.path)"
      >
        <span class="text-[0.7rem] w-3 text-txt-tertiary">
          {{ node.type === 'dir' ? (expanded[node.path] ? '▾' : '▸') : '' }}
        </span>
        <span>{{ node.type === 'dir' ? '📁' : '📄' }}</span>
        <span class="truncate">{{ node.name }}</span>
      </div>
      <FileTree
        v-if="node.type === 'dir' && expanded[node.path] && node.children"
        :nodes="node.children"
        :depth="(depth ?? 0) + 1"
      />
    </template>
  </div>
</template>
