<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import 'monaco-editor/esm/vs/editor/contrib/find/browser/findController'
import 'monaco-editor/min/vs/editor/editor.main.css'
// 只注册需要的语言的 Monarch 语法高亮(只读查看无需语言服务 worker,避免 tsMode/htmlMode 等大 chunk)
import 'monaco-editor/esm/vs/basic-languages/java/java.contribution'
import 'monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution'
import 'monaco-editor/esm/vs/basic-languages/typescript/typescript.contribution'
import 'monaco-editor/esm/vs/basic-languages/xml/xml.contribution'
import 'monaco-editor/esm/vs/basic-languages/html/html.contribution'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import { useApp } from '../stores/app'

;(self as any).MonacoEnvironment = { getWorker: () => new editorWorker() }

const props = defineProps<{
  content: string
  language?: string | null
  path: string
  highlight?: [number, number] | null
}>()
const app = useApp()
const el = ref<HTMLElement | null>(null)
const editor = shallowRef<monaco.editor.IStandaloneCodeEditor | null>(null)

const LANG_MAP: Record<string, string> = {
  java: 'java',
  javascript: 'javascript',
  typescript: 'typescript',
  tsx: 'typescript',
  vue: 'html',
  xml: 'xml',
}

function monacoLang(l?: string | null) {
  return l ? (LANG_MAP[l] ?? 'plaintext') : 'plaintext'
}

function applyHighlight() {
  const ed = editor.value
  const h = props.highlight
  if (!ed || !h) return
  const model = ed.getModel()
  if (!model) return
  const last = model.getLineCount()
  const start = Math.min(h[0], last)
  const end = Math.min(h[1], last)
  const range = new monaco.Range(start, 1, end, model.getLineMaxColumn(end))
  ed.setSelection(range)
  ed.revealRangeInCenter(range)
}

onMounted(() => {
  if (!el.value) return
  editor.value = monaco.editor.create(el.value, {
    value: props.content,
    language: monacoLang(props.language),
    theme: 'vs-dark',
    readOnly: true,
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: 'JetBrains Mono, monospace',
    scrollBeyondLastLine: false,
  })
  editor.value.onDidChangeCursorSelection(() => {
    const ed = editor.value!
    const sel = ed.getSelection()
    const text = sel ? ed.getModel()?.getValueInRange(sel) ?? '' : ''
    if (text.trim()) {
      app.setSelection({ code: text, file: props.path, range: [sel!.startLineNumber, sel!.endLineNumber] })
    } else {
      app.setSelection(null)
    }
  })
  applyHighlight()
})

watch(
  () => [props.content, props.path],
  () => {
    const ed = editor.value
    if (!ed) return
    ed.setValue(props.content)
    monaco.editor.setModelLanguage(ed.getModel()!, monacoLang(props.language))
    applyHighlight()
  },
)

// 同一文件内点击不同检索结果:仅 highlight 变化也要重新选中
watch(
  () => props.highlight,
  () => applyHighlight(),
)

// Ctrl/Cmd+F:仅当焦点在编辑器内时用 Monaco 内置查找;其他位置保持浏览器查找
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
    const ed = editor.value
    if (ed && el.value && el.value.contains(document.activeElement)) {
      e.preventDefault()
      e.stopPropagation()
      ed.getAction('actions.find')?.run()
    }
  }
}
window.addEventListener('keydown', onKeydown, true)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown, true)
  editor.value?.dispose()
})
</script>

<template>
  <div ref="el" class="h-full w-full" />
</template>
