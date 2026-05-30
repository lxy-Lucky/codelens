<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, type Locale } from '../i18n'

defineEmits<{ collapse: []; index: [] }>()

const { t, locale } = useI18n()
const open = ref(false)

const opts: { value: Locale; label: string }[] = [
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日本語' },
  { value: 'en', label: 'English' },
]

function pick(v: Locale) {
  setLocale(v)
  open.value = false
}
</script>

<template>
  <header
    class="h-[52px] shrink-0 flex items-center justify-between px-5 bg-bg-secondary border-b border-border-subtle"
  >
    <div class="flex items-center gap-2.5">
      <button
        class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:text-txt-primary hover:bg-bg-tertiary"
        :title="t('topbar.toggleSidebar')"
        @click="$emit('collapse')"
      >
        ☰
      </button>
      <div class="w-[26px] h-[26px] bg-accent rounded grid place-items-center font-mono text-xs font-semibold text-bg-primary">
        CL
      </div>
      <span class="font-display text-[1.08rem]">{{ t('app.title') }}</span>
      <span class="text-[0.7rem] text-txt-tertiary ml-2 pl-2 border-l border-border-subtle">
        {{ t('app.subtitle') }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <button
        class="px-3 py-1.5 rounded text-[0.74rem] bg-accent text-bg-primary font-medium hover:bg-accent-dim"
        @click="$emit('index')"
      >
        {{ t('topbar.indexRepo') }}
      </button>

      <!-- language switcher -->
      <div class="relative">
        <button
          class="px-2.5 py-1.5 rounded text-[0.74rem] border border-border-subtle text-txt-secondary hover:text-txt-primary hover:border-accent flex items-center gap-1.5"
          :title="t('topbar.language')"
          @click="open = !open"
        >
          <span>🌐</span>
          <span>{{ t(`topbar.languageNames.${locale}`) }}</span>
          <span class="text-[0.6rem] text-txt-tertiary">▾</span>
        </button>
        <div
          v-if="open"
          class="absolute right-0 top-full mt-1 w-32 bg-bg-elevated border border-border-medium rounded-lg shadow-lg z-50 overflow-hidden"
        >
          <button
            v-for="o in opts"
            :key="o.value"
            class="w-full text-left px-3 py-2 text-[0.78rem] hover:bg-bg-hover"
            :class="locale === o.value ? 'text-accent bg-accent/5' : 'text-txt-secondary'"
            @click="pick(o.value)"
          >
            {{ o.label }}
          </button>
        </div>
      </div>
    </div>
  </header>

  <!-- click-away for language dropdown -->
  <div v-if="open" class="fixed inset-0 z-40" @click="open = false" />
</template>
