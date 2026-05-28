<script setup lang="ts">
defineEmits<{ collapse: []; index: [] }>()
</script>

<template>
  <header
    class="h-[52px] shrink-0 flex items-center justify-between px-5 bg-bg-secondary border-b border-border-subtle"
  >
    <div class="flex items-center gap-2.5">
      <button
        class="w-7 h-7 grid place-items-center rounded text-txt-tertiary hover:text-txt-primary hover:bg-bg-tertiary"
        title="折叠/展开侧栏"
        @click="$emit('collapse')"
      >
        ☰
      </button>
      <div class="w-[26px] h-[26px] bg-accent rounded grid place-items-center font-mono text-xs font-semibold text-bg-primary">
        CL
      </div>
      <span class="font-display text-[1.08rem]">CodeLens</span>
      <span class="text-[0.7rem] text-txt-tertiary ml-2 pl-2 border-l border-border-subtle">
        代码库智能检索与分析
      </span>
    </div>
    <div class="flex items-center gap-1.5">
      <button
        class="px-3 py-1.5 rounded text-[0.74rem] bg-accent text-bg-primary font-medium hover:bg-accent-dim"
        @click="$emit('index')"
      >
        ＋ 索引仓库
      </button>
    </div>
  </header>
</template>
