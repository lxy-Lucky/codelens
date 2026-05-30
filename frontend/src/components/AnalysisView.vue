<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { FileRef } from '../api/types'
import { useApp } from '../stores/app'

const { t } = useI18n()
const app = useApp()
const loading = ref(false)
const building = ref(false)
const errorMsg = ref('')
const status = ref('')
const imports = ref<FileRef[]>([])
const importedBy = ref<FileRef[]>([])
const loadedPath = ref<string | null>(null)

async function load() {
  errorMsg.value = ''
  if (!app.currentRepoId || !app.openFile) {
    imports.value = []
    importedBy.value = []
    loadedPath.value = null
    return
  }
  loading.value = true
  loadedPath.value = app.openFile.path
  try {
    const d = await api.deps(app.currentRepoId, app.openFile.path)
    imports.value = d.imports
    importedBy.value = d.imported_by
  } catch (e: any) {
    errorMsg.value = t('deps.loadFail', { msg: e?.response?.data?.detail ?? e?.message ?? e })
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
    const r: any = await app.buildGraph()
    status.value = t('deps.buildDone', { symbols: r.symbols, edges: r.dep_edges ?? '?' })
    await load()
  } catch (e: any) {
    errorMsg.value = t('deps.buildFail', { msg: e?.response?.data?.detail ?? e?.message ?? e })
  } finally {
    building.value = false
  }
}

watch(() => [app.openFile?.path, app.currentRepoId], load, { immediate: true })
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex items-center gap-3 px-6 py-2 border-b border-border-subtle text-[0.74rem]">
      <button
        class="px-3 py-1 rounded bg-accent text-bg-primary font-medium hover:bg-accent-dim disabled:opacity-40"
        :disabled="building || !app.currentRepoId"
        @click="doBuild"
      >
        {{ building ? t('deps.building') : t('deps.build') }}
      </button>
      <span v-if="app.openFile" class="text-txt-secondary font-mono truncate">{{ app.openFile.path }}</span>
      <button v-if="app.openFile" class="ml-auto text-txt-tertiary hover:text-accent" :title="t('common.refresh')" @click="load">↻</button>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-5">
      <div v-if="!app.openFile" class="p-16 text-center text-txt-tertiary text-[0.8rem]">
        {{ t('deps.emptyHint') }}
      </div>
      <template v-else>
        <div v-if="errorMsg" class="mb-3 text-err text-[0.76rem]">{{ errorMsg }}</div>
        <div v-if="status" class="mb-3 text-txt-secondary text-[0.76rem]">{{ status }}</div>
        <div v-if="loading" class="flex items-center gap-2 text-txt-tertiary text-[0.78rem]">
          <div class="w-5 h-5 border-2 border-border-medium border-t-accent rounded-full animate-spin" />{{ t('common.loading') }}
        </div>
        <template v-else>
          <div v-if="!imports.length && !importedBy.length" class="p-12 text-center text-txt-tertiary text-[0.78rem]">
            {{ t('deps.noData') }}
          </div>

          <section v-if="imports.length" class="mb-6">
            <div class="text-[0.72rem] font-semibold uppercase tracking-wider text-txt-tertiary mb-2">
              {{ t('deps.imports', { n: imports.length }) }}
            </div>
            <div class="grid grid-cols-1 gap-2">
              <div
                v-for="d in imports"
                :key="d.key"
                class="flex items-center gap-2.5 px-3 py-2 bg-bg-secondary border border-border-subtle rounded-lg cursor-pointer hover:border-accent"
                @click="app.openFileByPath(d.file)"
              >
                <span>📄</span>
                <div class="min-w-0">
                  <div class="text-[0.78rem] text-txt-primary truncate">{{ d.name }}</div>
                  <div class="text-[0.62rem] text-txt-tertiary truncate">{{ d.file }}</div>
                </div>
              </div>
            </div>
          </section>

          <section v-if="importedBy.length">
            <div class="text-[0.72rem] font-semibold uppercase tracking-wider text-txt-tertiary mb-2">
              {{ t('deps.importedBy', { n: importedBy.length }) }}
            </div>
            <div class="grid grid-cols-1 gap-2">
              <div
                v-for="d in importedBy"
                :key="d.key"
                class="flex items-center gap-2.5 px-3 py-2 bg-bg-secondary border border-border-subtle rounded-lg cursor-pointer hover:border-accent"
                @click="app.openFileByPath(d.file)"
              >
                <span>📄</span>
                <div class="min-w-0">
                  <div class="text-[0.78rem] text-txt-primary truncate">{{ d.name }}</div>
                  <div class="text-[0.62rem] text-txt-tertiary truncate">{{ d.file }}</div>
                </div>
              </div>
            </div>
          </section>
        </template>
      </template>
    </div>
  </div>
</template>
