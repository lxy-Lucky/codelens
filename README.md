# CodeLens

本地 AI 代码库智能检索与分析工具。完全自托管,代码不出本机。

## 功能

- **语义检索** — 自然语言定位代码(混合检索:向量 + 关键字,reranker 重排)
- **代码分析** — 模块/文件依赖关系(Neo4j 图)
- **逻辑地图** — 函数调用链(tree-sitter 提取 + Mermaid 可视化)
- **文档生成** — 对函数/类/模块自动生成文档

支持语言:Java、JS/TS、JSX/TSX、Vue、XML(后续:JSP)。

## 技术栈

| 层 | 选型 |
|----|------|
| LLM | Qwen3 14B via **Ollama**(OpenAI 兼容接口) |
| Embedding | bge-m3 |
| Reranker | bge-reranker-v2-m3 |
| 向量库 | **Qdrant** |
| 图库 | **Neo4j** |
| 后端 | Python 3.12 + FastAPI |
| 前端 | Vue3 + Vite + TS + TailwindCSS + Pinia + Axios + Monaco + Mermaid + Marked |

## 目录结构

```
codelens/
├─ backend/        FastAPI 后端
├─ frontend/       Vue3 前端
├─ docker-compose.yml   Qdrant + Neo4j(本地起服务用)
└─ index.html      原始设计原型(仅作参考)
```

## 前置依赖(运行前需就绪)

1. **Ollama** 拉起 Qwen3 14B:`ollama pull qwen3:14b` 然后 `ollama serve`
2. **Qdrant**:`docker compose up -d qdrant`(默认 localhost:6333)
3. **Neo4j**:`docker compose up -d neo4j`(默认 localhost:7687)

## 启动

```bash
# 后端
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```
