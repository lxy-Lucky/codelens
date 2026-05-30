import axios from 'axios'
import type { CodeChunkHit, FileDeps, FsListResp, RepoInfo, Subgraph, TreeNode } from './types'

const http = axios.create({ baseURL: '' })

export const api = {
  listRepos: () => http.get<RepoInfo[]>('/api/repos').then((r) => r.data),
  createRepo: (path: string, name?: string, excludes?: string[]) =>
    http
      .post<RepoInfo>('/api/repos', { path, name, ...(excludes ? { excludes } : {}) })
      .then((r) => r.data),
  deleteRepo: (id: string) => http.delete(`/api/repos/${id}`).then((r) => r.data),
  fsList: (path: string) =>
    http.get<FsListResp>('/api/fs/list', { params: { path } }).then((r) => r.data),
  fileTree: (id: string) => http.get<TreeNode[]>(`/api/files/${id}/tree`).then((r) => r.data),
  fileContent: (id: string, path: string) =>
    http
      .get<{ path: string; language: string; content: string }>(`/api/files/${id}/content`, {
        params: { path },
      })
      .then((r) => r.data),
  search: (repo_id: string, query: string, languages: string[] = []) =>
    http
      .post<{ query: string; hits: CodeChunkHit[] }>('/api/search', { repo_id, query, languages })
      .then((r) => r.data),
  buildGraph: (id: string) =>
    http
      .post<{ symbols: number; edges: number; routes: number; api_edges: number; mybatis_edges: number }>(
        `/api/graph/${id}/build`,
      )
      .then((r) => r.data),
  subgraph: (id: string, symbol_key: string, hops = 1) =>
    http
      .get<Subgraph>(`/api/graph/${id}/subgraph`, { params: { symbol_key, hops } })
      .then((r) => r.data),
  deps: (id: string, path: string) =>
    http.get<FileDeps>(`/api/graph/${id}/deps`, { params: { path } }).then((r) => r.data),
}

/** SSE over POST (fetch + ReadableStream). 解析 `data: {...}` 行,逐条回调。 */
export async function streamSSE(
  url: string,
  body: unknown,
  onEvent: (data: any) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!resp.body) return
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      try {
        onEvent(JSON.parse(line.slice(5).trim()))
      } catch {
        /* 忽略解析失败的分片 */
      }
    }
  }
}

/** GET 形式的 SSE(索引进度)。 */
export async function streamGetSSE(
  url: string,
  onEvent: (data: any) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(url, { signal })
  if (!resp.body) return
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      try {
        onEvent(JSON.parse(line.slice(5).trim()))
      } catch {
        /* ignore */
      }
    }
  }
}
