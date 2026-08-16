"""
RAG 引擎模块
功能：
  1. 加载FAQ知识库 → 分块 → 向量化 → 存入Chroma
  2. 提供检索接口：输入问题，返回最相关的FAQ内容
  3. 提供RAG问答接口：检索+大模型生成

这是整个项目技术含量最高的模块。
面试官问"你的RAG怎么实现的"，答案都在这里。

运行 rag_engine.py 可以初始化向量库
"""

import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import ZhipuAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME,
    ZHIPU_API_KEY, EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR, FAQ_FILE, CHUNK_SIZE, CHUNK_OVERLAP,
    RETRIEVAL_TOP_K
)


class RAGEngine:
    """RAG检索增强生成引擎"""

    def __init__(self):
        self.embeddings = None      # Embedding模型（文字→向量）
        self.vectorstore = None     # Chroma向量库
        self.llm = None             # 大模型
        self._initialized = False

    def initialize(self):
        """
        初始化：加载大模型 + 加载/构建向量库
        第一次运行会从FAQ文件构建向量库（较慢），之后直接加载（快）
        """
        print("🔧 初始化RAG引擎...")

        # 1. 初始化Embedding模型（用智谱，国内免费额度足够）
        # 为什么用智谱：DeepSeek不提供Embedding接口，智谱的embedding-2
        # 中文效果好，注册即送免费额度，本项目花费为0
        self.embeddings = ZhipuAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=ZHIPU_API_KEY,
        )

        # 2. 初始化大模型
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=1000
        )

        # 3. 加载或构建向量库
        if os.path.exists(CHROMA_PERSIST_DIR):
            # 已存在，直接加载
            print("📂 加载现有向量库...")
            self.vectorstore = Chroma(
                persist_directory=CHROMA_PERSIST_DIR,
                embedding_function=self.embeddings
            )
        else:
            # 不存在，从FAQ文件构建
            print("🔨 首次构建向量库（需要1-2分钟）...")
            self._build_vectorstore()

        self._initialized = True
        print("✅ RAG引擎初始化完成！")

    def _build_vectorstore(self):
        """
        构建向量库的完整流程（RAG核心，面试必讲）：
        1. 加载文档
        2. 分块（Chunking）
        3. 向量化（Embedding）
        4. 存入Chroma
        """
        # Step 1: 加载FAQ文件
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            text = f.read()

        # Step 2: 分块
        # 为什么分块？大模型上下文有限 + 小块检索更精准
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,        # 每块300字
            chunk_overlap=CHUNK_OVERLAP,  # 块之间重叠50字（避免切断关键信息）
            separators=["\n###", "\n##", "\n\n", "\n", "。", "；"]  # 按标题优先切
        )
        chunks = text_splitter.split_text(text)
        print(f"   📄 FAQ分块完成：共{len(chunks)}块（每块约{CHUNK_SIZE}字）")

        # Step 3+4: 向量化 + 存入Chroma
        self.vectorstore = Chroma.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            persist_directory=CHROMA_PERSIST_DIR
        )
        self.vectorstore.persist()  # 持久化到磁盘
        print(f"   💾 向量库已保存到 {CHROMA_PERSIST_DIR}")

    def retrieve(self, question: str, top_k: int = RETRIEVAL_TOP_K) -> list:
        """
        检索：输入问题，返回最相关的top_k条FAQ内容
        这一步是RAG的"R"（Retrieval）
        """
        if not self._initialized:
            self.initialize()

        docs = self.vectorstore.similarity_search(question, k=top_k)
        return [doc.page_content for doc in docs]

    def answer_with_rag(self, question: str) -> dict:
        """
        RAG完整问答：检索 → 拼接 → 大模型生成
        返回：{answer, sources} sources是检索到的原文（面试展示用）
        """
        if not self._initialized:
            self.initialize()

        # 1. 检索相关FAQ
        sources = self.retrieve(question)
        context = "\n\n".join(sources)

        # 2. 构造Prompt（把检索到的内容塞给大模型）
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是电商售后客服。基于以下知识库内容回答用户问题。

【知识库内容】
{context}

【回答规则】
1. 只用知识库里的信息，不要编造
2. 如果知识库没有相关内容，说"这个问题我需要转人工帮您确认"
3. 回答分点，清晰易懂"""),
            ("human", "{question}")
        ])

        # 3. 调大模型生成
        chain = prompt | self.llm
        response = chain.invoke({"context": context, "question": question})

        return {
            "answer": response.content,
            "sources": sources  # 返回检索原文，用于评测和展示
        }


# ============================================
# 单独运行：初始化向量库
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("初始化 RAG 向量库")
    print("=" * 60)

    rag = RAGEngine()
    rag.initialize()

    # 测试检索
    print("\n🧪 测试检索：")
    test_questions = [
        "7天无理由退货需要什么条件",
        "哪些商品不能退",
        "退款多久到账"
    ]

    for q in test_questions:
        print(f"\n问：{q}")
        result = rag.answer_with_rag(q)
        print(f"答：{result['answer'][:100]}...")
        print(f"（检索到{len(result['sources'])}条相关FAQ）")

    print("\n✅ RAG引擎就绪！可以运行 agent.py 或 app.py 了")
