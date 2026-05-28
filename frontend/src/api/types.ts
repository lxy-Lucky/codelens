export interface RepoInfo {
  id: string
  name: string
  path: string
  status: 'pending' | 'indexing' | 'ready' | 'error'
  language_stats: Record<string, number>
  file_count: number
  chunk_count: number
  error?: string | null
}

export interface TreeNode {
  name: string
  path: string
  type: 'dir' | 'file'
  language?: string | null
  children?: TreeNode[] | null
}

export interface CodeChunkHit {
  chunk_id: string
  file_path: string
  symbol?: string | null
  kind?: string | null
  start_line: number
  end_line: number
  score: number
  snippet: string
  language?: string | null
}

export interface ChatRef {
  file: string
  start_line: number
  end_line: number
  symbol?: string | null
  kind?: string | null
}

export type WorkMode = 'search' | 'analysis' | 'flow' | 'docs'

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  refs?: ChatRef[]
}
