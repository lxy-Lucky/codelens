# CodeLens

本地 AI 代码库智能检索与分析工具。**完全自托管**,源码不出本机;支持中 / 日 / 英三语界面与跨语言检索。

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **语义检索** | 自然语言定位代码;**向量 + BM25 RRF 融合** + bge-reranker 精排 + 符号名加权;按语言过滤;命中可跳转编辑器并自动高亮匹配行 |
| 📊 **代码分析** | 文件级依赖图(`DEPENDS_ON`):Java FQN / JS-TS-Vue 相对路径解析,展示当前文件的 imports 与 importedBy |
| 🗺️ **逻辑地图** | 函数调用链(tree-sitter 提取 + Mermaid 渲染);右键「查看调用图」入口;节点点击跳源码;±N 跳子图;缩放控件 |
| 📖 **文档生成** | 对当前文件流式生成 Markdown 文档(marked + DOMPurify),可复制 / 导出 .md |

**多语言**:界面 中 / 日 / 英 可切换;LLM 输出语言跟随界面;BM25 用 ASCII 子词 + CJK bigram(中日韩统一,无需分词器);bge-m3 / bge-reranker-v2-m3 多语言嵌入;源文件**自动检测编码**(utf-8 / cp932 / gb2312 / cp1252)。

**支持的源文件**:`.java` `.js` `.jsx` `.ts` `.tsx` `.vue` `.xml`(MyBatis mapper 会与接口方法连边)。

## 技术栈

| 层 | 选型 |
|----|------|
| LLM | 任意 Ollama 模型(默认 `qwen3.5:9b`,通过 .env / config 切换) |
| Embedding | `BAAI/bge-m3`(fp16 GPU 或 CPU) |
| Reranker | `BAAI/bge-reranker-v2-m3`(默认 CPU,搜索时小批量 1~2 秒) |
| 向量库 | **Qdrant**(单 collection,repo_id + language 双 payload 索引) |
| 图库 | **Neo4j**(File / Symbol 节点,REL 边带 `type` & `confidence`) |
| 后端 | Python 3.12 + FastAPI(全 SSE 流式) |
| 前端 | Vue3 + Vite + TS + Tailwind + Pinia + Axios + Monaco + Mermaid + Marked + vue-i18n |

## 目录结构

```
codelens/
├─ backend/                  FastAPI 后端
│  ├─ app/
│  │  ├─ api/                repos / search / chat / files / graph / docs
│  │  ├─ services/           索引、检索、图、文档、客户端封装
│  │  │  ├─ indexer.py       预取流水线:解析(ts 线程) + 嵌入(embed 线程)重叠
│  │  │  ├─ chunker.py       tree-sitter 按函数/类切块,合并紧邻注释(中日英 Javadoc 进嵌入)
│  │  │  ├─ tokenize.py      ASCII 子词 + CJK bigram(zh/ja/ko 统一)
│  │  │  ├─ fileio.py        编码自动检测(cp932/gb2312…)
│  │  │  ├─ graph_builder.py 调用图(CALLS)、降噪(同文件优先/全库唯一才连/停用词)
│  │  │  ├─ graph_enrich.py  API 路由桥接、MyBatis、文件级依赖
│  │  │  └─ ts.py            tree-sitter 线程本地 parser + 单线程 executor
│  │  ├─ models/schemas.py
│  │  └─ main.py
│  └─ pyproject.toml
├─ frontend/                 Vue3 前端
│  ├─ src/
│  │  ├─ components/         Sidebar / MainPane / ChatPanel / CodeViewer
│  │  │                      GraphView / AnalysisView / DocsView / IndexRepoModal
│  │  ├─ stores/app.ts       Pinia 全局状态 + localStorage 持久化
│  │  ├─ api/                axios client + SSE 流式
│  │  └─ i18n/               中 / 日 / 英 翻译
│  └─ package.json
├─ docker-compose.yml        Qdrant + Neo4j
└─ index.html                原始 UI 设计原型(参考用)
```

## 前置依赖

1. **Ollama**(LLM 推理):
   ```bash
   ollama pull qwen3.5:9b      # 或你想用的任意模型
   ollama serve
   ```
2. **Qdrant + Neo4j**(向量与图):
   ```bash
   docker compose up -d
   ```
   - Qdrant:`localhost:6333`
   - Neo4j:`localhost:7687`,账号 `neo4j` / `codelens123`

## 配置(`backend/.env`)

```ini
# Ollama / LLM
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3.5:9b
LLM_NUM_CTX=16384            # 16K 够用;调大会显著吃显存

# Embedding / Reranker
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
EMBEDDING_DEVICE=cuda        # cuda 索引快(fp16+流水线);16GB 显存吃紧时改 cpu
RERANKER_DEVICE=cpu          # 默认 CPU 省显存,搜索时小批量 1~2 秒可接受

# Qdrant / Neo4j
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=codelens123

# 数据目录(sqlite 状态库)
DATA_DIR=./data

# 检索召回参数
RETRIEVAL_TOP_K=50
RERANK_TOP_N=8
```

### 16GB 显卡的建议

LLM(9B@16K)≈ 10GB + bge-m3 fp16 ≈ 1.5GB → 约 11~12GB,留 4GB 余量。再大模型 / 上下文需要把 `EMBEDDING_DEVICE` 改回 `cpu`,或缩 `LLM_NUM_CTX`。

## 启动

```bash
# 后端
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## 使用流程

1. 顶栏右上「**＋ 索引仓库**」→ 填本地路径 → 开始(SSE 实时进度)
2. **语义检索**:中间检索框输入问题,可勾选语言过滤;点结果跳转代码 tab,行被自动选中
3. **逻辑地图 / 代码分析**:第一次先到「**图谱**」tab 点「构建图谱」(同时建调用图 + 依赖图);之后:
   - 在检索结果 / 代码编辑器**右键**任意函数 →「🗺️ 查看调用图」
   - 切到「**依赖**」tab 看当前文件的 imports / importedBy
4. **文档生成**:打开任意文件 →「**文档**」tab → 生成 → 流式 Markdown
5. **AI 对话**(右侧):在编辑器**选中一段代码**后提问会以此为上下文;不选则全库;支持「重新执行」历史检索;界面切语言后 LLM 回答语言自动跟随
6. 状态自动持久化(刷新页面后恢复仓库 / 标签 / 打开的文件 / 对话记录)

## 已知边界

- **调用图是语法级近似**:tree-sitter 不做类型解析,无法区分同名同参数个数但**仅类型不同**的重载(如 `isEmpty(Object)` vs `isEmpty(String)`),也无法区分 JDK 内置与仓库同名方法。已通过「同文件优先 / 全库唯一才连 / 跨文件多义跳过 / 停用词」大幅降噪,但不能消除。
- **API 路由桥接**:前端 axios/fetch 与后端 `@*Mapping` 按归一化 URL 连边;若调用方在匿名箭头函数里,enclosing symbol 取不到该边会跳过。
- 前端 `import` 解析支持相对路径与 Java FQN,**裸包 / `@/` 别名跳过**。
- 修改了切块逻辑或编码解码后,**已索引内容不会自动重做**(增量按文件 hash);需要时删除仓库重建。

## 排错速查

| 现象 | 通常原因 / 处理 |
|------|------|
| 索引报 `CUDA out of memory` | LLM 与 embedding 在 16GB 卡上挤;`EMBEDDING_DEVICE=cpu` 或缩 `LLM_NUM_CTX` |
| 索引进度卡住不动 | 看 uvicorn 控制台 `[index]` 日志定位 解析 / 嵌入 / 入库 哪一步 |
| 「构建图谱」报错 | Neo4j 未起,或密码不对 |
| 注释乱码 | 文件是 cp932/gb2312,已自动检测,重建索引即可生效 |
