<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import { useApp } from '../stores/app'

;(self as any).MonacoEnvironment = { getWorker: () => new editorWorker() }

const props = defineProps<{ content: string; language?: string | null; path: string }>()
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
})

watch(
  () => [props.content, props.path],
  () => {
    const ed = editor.value
    if (!ed) return
    ed.setValue(props.content)
    monaco.editor.setModelLanguage(ed.getModel()!, monacoLang(props.language))
  },
)

onBeforeUnmount(() => editor.value?.dispose())
</script>

<template>
  <div ref="el" class="h-full w-full" />
</template>
