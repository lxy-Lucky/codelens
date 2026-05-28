<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import type { GraphNode } from '../api/types'
import { useApp } from '../stores/app'

const app = useApp()
const container = ref<HTMLElement | null>(null)
const loading = ref(false)
const building = ref(false)
const status = ref('')
const errorMsg = ref('')
const nodeCount = ref(0)

function esc(s: string): string {
  return s.replace(/["[\]{}|<>]/g, ' ').slice(0, 40)
}

function buildMermaid(nodes: GraphNode[], edges: { src: string; dst: string; type?: string | null; confidence?: number | null }[], centerKey: string): { text: string; byId: Record<string, GraphNode> } {
  const idOf = new Map<string, string>()
  const byId: Record<string, GraphNode> = {}
  nodes.forEach((n, i) => {
    const nid = 'n' + i
    idOf.set(n.key, nid)
    byId[nid] = n
  })
  const lines = ['graph LR']
  lines.push('classDef center fill:#d4a574,stroke:#d4a574,color:#0e0f11;')
  for (const n of nodes) {
    const nid = idOf.get(n.key)!
    const label = esc(n.name || n.key)
    lines.push(`${nid}["${label}"]`)
  }
  for (const e of edges) {
    const a = idOf.get(e.src)
    const b = idOf.get(e.dst)
    if (!a || !b) continue
    const weak = (e.confidence ?? 1) < 0.8
    const lbl = e.type && e.type !== 'CALLS' ? e.type : ''
    if (weak) lines.push(lbl ? `${a} -. ${lbl} .-> ${b}` : `${a} -.-> ${b}`)
    else lines.push(lbl ? `${a} -->|${lbl}| ${b}` : `${a} --> ${b}`)
  }
  const centerId = idOf.get(centerKey)
  if (centerId) lines.push(`class ${centerId} center;`)
  return { text: lines.join('\n'), byId }
}

async function render() {
  errorMsg.value = ''
  status.value = ''
  if (!app.currentRepoId || !app.graphTarget) {
    if (container.value) container.value.innerHTML = ''
    return
  }
  loading.value = true
  try {
    const g = await api.subgraph(app.currentRepoId, app.graphTarget.symbolKey, app.graphHops)
    nodeCount.value = g.nodes.length
    if (!g.nodes.length) {
      if (container.value) container.value.innerHTML = ''
      status.value = '该符号没有调用关系数据。若还没构建图谱,请先点「构建图谱」。'
      return
    }
    const { text, byId } = buildMermaid(g.nodes, g.edges, app.graphTarget.symbolKey)
    const mermaid = (await import('mermaid')).default
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose', flowchart: { useMaxWidth: true } })
    const { svg } = await mermaid.render('cl-graph-' + Date.now(), text)
    if (!container.value) return
    container.value.innerHTML = svg
    // 绑定节点点击 → 跳源码
    container.value.querySelectorAll('g.node').forEach((el) => {
      const mm = el.id.match(/flowchart-(n\d+)-/)
      if (!mm) return
      const node = byId[mm[1]]
      if (!node?.file) return
      ;(el as HTMLElement).style.cursor = 'pointer'
      el.addEventListener('click', () => {
        app.openFileByPath(node.file!, node.line ? [node.line, node.line] : null)
      })
    })
  } catch (e: any) {
    errorMsg.value = '渲染失败:' + (e?.message ?? e)
  } finally {
    loading.value = false
  }
}

async function doBuild() {
  if (!app.currentRepoId) return
  building.value = true
  status.value = ''
  errorMsg.value = ''
  try {
    const r = await app.buildGraph()
    status.value = `构建完成:${r.symbols} 符号 / ${r.edges} 边`
    await render()
  } catch (e: any) {
    errorMsg.value = '构建失败(Neo4j 是否启动?):' + (e?.response?.data?.detail ?? e?.message ?? e)
  } finally {
    building.value = false
  }
}

onMounted(render)
watch(() => [app.graphTarget?.symbolKey, app.graphHops], render)
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- toolbar -->
    <div class="flex items-center gap-3 px-6 py-2 border-b border-border-subtle text-[0.74rem]">
      <button
        class="px-3 py-1 rounded bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
        :disabled="building || !app.currentRepoId"
        @click="doBuild"
      >
        {{ building ? '构建中…' : '构建图谱' }}
      </button>
      <div class="flex items-center gap-1.5 text-txt-tertiary">
        <span>跳数</span>
        <select v-model.number="app.graphHops" class="bg-bg-tertiary border border-border-subtle rounded px-1.5 py-0.5 outline-none">
          <option :value="1">1</option>
          <option :value="2">2</option>
          <option :value="3">3</option>
        </select>
      </div>
      <span v-if="app.graphTarget" class="text-txt-secondary font-mono truncate">
        中心:{{ app.graphTarget.label }}
      </span>
      <span class="ml-auto text-txt-tertiary">{{ nodeCount ? nodeCount + ' 节点' : '' }}</span>
    </div>

    <!-- canvas -->
    <div class="flex-1 overflow-auto p-4">
      <div v-if="!app.graphTarget" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        在检索结果或代码里右键某个函数 →「查看调用图」
      </div>
      <div v-else-if="loading" class="flex flex-col items-center justify-center py-20 gap-3 text-txt-tertiary">
        <div class="w-7 h-7 border-2 border-border-medium border-t-accent rounded-full animate-spin" />
        <div class="text-[0.78rem]">加载调用图…</div>
      </div>
      <div v-if="errorMsg" class="text-[0.76rem] text-err mb-3">{{ errorMsg }}</div>
      <div v-if="status" class="text-[0.76rem] text-txt-secondary mb-3">{{ status }}</div>
      <div ref="container" class="cl-graph" />
    </div>
  </div>
</template>

<style scoped>
.cl-graph :deep(svg) {
  max-width: 100%;
  height: auto;
}
</style>
