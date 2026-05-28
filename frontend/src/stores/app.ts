import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { CodeChunkHit, RepoInfo, TreeNode, WorkMode } from '../api/types'

interface State {
  repos: RepoInfo[]
  currentRepoId: string | null
  workMode: WorkMode
  tree: TreeNode[]
  mainTab: 'results' | 'code'
  openFile: { path: string; language: string; content: string } | null
  searchHits: CodeChunkHit[]
  searching: boolean
  // Monaco 选区(注入问答上下文)
  selection: { code: string; file: string; range: [number, number] } | null
}

export const useApp = defineStore('app', {
  state: (): State => ({
    repos: [],
    currentRepoId: null,
    workMode: 'search',
    tree: [],
    mainTab: 'results',
    openFile: null,
    searchHits: [],
    searching: false,
    selection: null,
  }),
  getters: {
    currentRepo: (s): RepoInfo | null => s.repos.find((r) => r.id === s.currentRepoId) ?? null,
  },
  actions: {
    async loadRepos() {
      this.repos = await api.listRepos()
      if (!this.currentRepoId && this.repos.length) {
        await this.selectRepo(this.repos[0].id)
      }
    },
    async selectRepo(id: string) {
      this.currentRepoId = id
      this.openFile = null
      this.searchHits = []
      this.selection = null
      const repo = this.repos.find((r) => r.id === id)
      if (repo && repo.status === 'ready') {
        this.tree = await api.fileTree(id)
      } else {
        this.tree = []
      }
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
    async openFileByPath(path: string) {
      if (!this.currentRepoId) return
      this.openFile = await api.fileContent(this.currentRepoId, path)
      this.mainTab = 'code'
    },
    async runSearch(query: string) {
      if (!this.currentRepoId || !query.trim()) return
      this.searching = true
      this.mainTab = 'results'
      try {
        const res = await api.search(this.currentRepoId, query)
        this.searchHits = res.hits
      } finally {
        this.searching = false
      }
    },
    setSelection(sel: State['selection']) {
      this.selection = sel
    },
  },
})
