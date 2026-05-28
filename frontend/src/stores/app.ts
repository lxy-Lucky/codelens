import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { ChatMsg, CodeChunkHit, RepoInfo, TreeNode, WorkMode } from '../api/types'

const LS_KEY = 'codelens.state.v1'

interface OpenFile {
  path: string
  language: string
  content: string
  highlight?: [number, number] | null
}

interface State {
  repos: RepoInfo[]
  currentRepoId: string | null
  workMode: WorkMode
  tree: TreeNode[]
  mainTab: 'results' | 'code' | 'graph'
  openFile: OpenFile | null
  graphTarget: { symbolKey: string; label: string } | null
  graphHops: number
  searchQuery: string
  searchLanguages: string[]
  searchHits: CodeChunkHit[]
  searchHistory: string[]
  searching: boolean
  selection: { code: string; file: string; range: [number, number] } | null
  chatMessages: ChatMsg[]
  // 仅用于刷新恢复:hydrate 时记下要重新打开的文件路径
  _restoreFilePath: string | null
}

export const useApp = defineStore('app', {
  state: (): State => ({
    repos: [],
    currentRepoId: null,
    workMode: 'search',
    tree: [],
    mainTab: 'results',
    openFile: null,
    graphTarget: null,
    graphHops: 1,
    searchQuery: '',
    searchLanguages: [],
    searchHits: [],
    searchHistory: [],
    searching: false,
    selection: null,
    chatMessages: [],
    _restoreFilePath: null,
  }),
  getters: {
    currentRepo: (s): RepoInfo | null => s.repos.find((r) => r.id === s.currentRepoId) ?? null,
    repoLanguages(): string[] {
      const r = this.currentRepo
      return r ? Object.keys(r.language_stats || {}).sort() : []
    },
  },
  actions: {
    // ─── 持久化 ───
    persist() {
      // 不保存:searchQuery(检索词)、searchHits(检索结果)——刷新后置空
      const snapshot = {
        currentRepoId: this.currentRepoId,
        workMode: this.workMode,
        mainTab: this.mainTab,
        openFilePath: this.openFile?.path ?? null,
        searchLanguages: this.searchLanguages,
        searchHistory: this.searchHistory,
        chatMessages: this.chatMessages,
      }
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(snapshot))
      } catch {
        /* 容量超限等忽略 */
      }
    },
    hydrate() {
      try {
        const raw = localStorage.getItem(LS_KEY)
        if (!raw) return
        const s = JSON.parse(raw)
        this.currentRepoId = s.currentRepoId ?? null
        this.workMode = s.workMode ?? 'search'
        this.mainTab = s.mainTab ?? 'results'
        this.searchLanguages = s.searchLanguages ?? []
        this.searchHistory = s.searchHistory ?? []
        this.chatMessages = s.chatMessages ?? []
        this._restoreFilePath = s.openFilePath ?? null
        // searchQuery / searchHits 不恢复
      } catch {
        /* 损坏的快照忽略 */
      }
    },

    // ─── 初始化(hydrate 之后调用) ───
    async init() {
      this.repos = await api.listRepos()
      const exists = this.repos.some((r) => r.id === this.currentRepoId)
      if (!exists) {
        this.currentRepoId = this.repos.length ? this.repos[0].id : null
        this.tree = []
        this.openFile = null
      }
      const savedTab = this.mainTab
      if (this.currentRepoId) {
        const repo = this.repos.find((r) => r.id === this.currentRepoId)
        if (repo?.status === 'ready') {
          this.tree = await api.fileTree(this.currentRepoId)
          if (this._restoreFilePath) {
            await this.openFileByPath(this._restoreFilePath)
            this.mainTab = savedTab // openFileByPath 会切到 code,这里恢复刷新前的 tab
          }
        }
      }
      this._restoreFilePath = null
    },

    async loadRepos() {
      this.repos = await api.listRepos()
      if (!this.currentRepoId && this.repos.length) await this.selectRepo(this.repos[0].id)
    },

    async selectRepo(id: string) {
      this.currentRepoId = id
      this.openFile = null
      this.searchHits = []
      this.selection = null
      const repo = this.repos.find((r) => r.id === id)
      this.tree = repo && repo.status === 'ready' ? await api.fileTree(id) : []
    },

    async deleteRepo(id: string) {
      await api.deleteRepo(id)
      this.repos = this.repos.filter((r) => r.id !== id)
      if (this.currentRepoId === id) {
        this.currentRepoId = null
        this.tree = []
        this.openFile = null
        if (this.repos.length) await this.selectRepo(this.repos[0].id)
      }
    },

    async openFileByPath(path: string, highlight: [number, number] | null = null) {
      if (!this.currentRepoId) return
      const f = await api.fileContent(this.currentRepoId, path)
      this.openFile = { ...f, highlight }
      this.mainTab = 'code'
    },

    async runSearch(query: string) {
      const q = query.trim()
      if (!this.currentRepoId || !q) return
      this.searchQuery = q
      this.searching = true
      this.mainTab = 'results'
      // 记入历史(去重、最新置顶、上限 20)
      this.searchHistory = [q, ...this.searchHistory.filter((h) => h !== q)].slice(0, 20)
      try {
        const res = await api.search(this.currentRepoId, q, this.searchLanguages)
        this.searchHits = res.hits
      } finally {
        this.searching = false
      }
    },

    toggleLanguage(lang: string) {
      this.searchLanguages = this.searchLanguages.includes(lang)
        ? this.searchLanguages.filter((l) => l !== lang)
        : [...this.searchLanguages, lang]
    },

    closeFile() {
      this.openFile = null
      this.selection = null
      this.mainTab = 'results'
    },

    // 打开某符号的调用图(右键「查看调用图」入口)
    openCallGraph(symbolKey: string, label: string) {
      this.graphTarget = { symbolKey, label }
      this.workMode = 'flow'
      this.mainTab = 'graph'
    },

    async buildGraph(): Promise<{ symbols: number; edges: number }> {
      if (!this.currentRepoId) throw new Error('未选择仓库')
      return api.buildGraph(this.currentRepoId)
    },

    setSelection(sel: State['selection']) {
      this.selection = sel
    },
  },
})
