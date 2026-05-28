<script setup lang="ts">
import { onMounted, ref } from 'vue'
import TopBar from './components/TopBar.vue'
import Sidebar from './components/Sidebar.vue'
import MainPane from './components/MainPane.vue'
import ChatPanel from './components/ChatPanel.vue'
import IndexRepoModal from './components/IndexRepoModal.vue'
import { useApp } from './stores/app'

const app = useApp()

const leftWidth = ref(248)
const rightWidth = ref(384)
const leftCollapsed = ref(false)
const showIndexModal = ref(false)

function startDrag(side: 'left' | 'right', e: MouseEvent) {
  e.preventDefault()
  const startX = e.clientX
  const startLeft = leftWidth.value
  const startRight = rightWidth.value
  const move = (ev: MouseEvent) => {
    const dx = ev.clientX - startX
    if (side === 'left') leftWidth.value = Math.min(480, Math.max(180, startLeft + dx))
    else rightWidth.value = Math.min(640, Math.max(280, startRight - dx))
  }
  const up = () => {
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

onMounted(() => app.loadRepos())
</script>

<template>
  <div class="flex flex-col h-screen">
    <TopBar @collapse="leftCollapsed = !leftCollapsed" @index="showIndexModal = true" />
    <div class="flex flex-1 min-h-0">
      <div
        v-if="!leftCollapsed"
        :style="{ width: leftWidth + 'px' }"
        class="shrink-0 min-w-0"
      >
        <Sidebar />
      </div>
      <div
        v-if="!leftCollapsed"
        class="w-1 cursor-col-resize hover:bg-accent/40 shrink-0"
        @mousedown="startDrag('left', $event)"
      />
      <div class="flex-1 min-w-0">
        <MainPane />
      </div>
      <div
        class="w-1 cursor-col-resize hover:bg-accent/40 shrink-0"
        @mousedown="startDrag('right', $event)"
      />
      <div :style="{ width: rightWidth + 'px' }" class="shrink-0 min-w-0">
        <ChatPanel />
      </div>
    </div>
    <IndexRepoModal v-if="showIndexModal" @close="showIndexModal = false" />
  </div>
</template>
