# ByteFlow 智能报告生成系统

ByteFlow 是一个基于多AI代理的智能报告生成系统，能够协调多个AI专家角色协同工作，自动生成结构化、高质量的分析报告。系统集成了Ollama、通义千问和智谱AI等多种大语言模型，并支持百度搜索API和智谱MCP搜索功能，以获取实时数据和增强模型能力。

## 功能特点

- 多AI代理协作：集成Ollama、通义千问和智谱AI，实现智能协同
- 智谱MCP搜索：利用智谱AI的Model Context Protocol获取精准数据
- 智能报告生成：自动生成结构化、高质量的分析报告
- 实时进度展示：通过WebSocket实时展示报告生成进度
- 多数据源支持：支持百度搜索API获取实时数据
- 可视化界面：提供友好的Web界面进行操作和监控

## 系统架构

ByteFlow采用模块化架构设计，主要包含以下组件：

1. **Agent模块**：负责与不同AI服务提供商的接口通信
2. **工作流引擎**：管理报告生成的整个流程
3. **Web前端**：提供用户交互界面
4. **API服务**：基于FastAPI构建的后端服务

## 技术栈

- 后端：Python 3.8+, FastAPI
- 前端：HTML5, CSS3, JavaScript (无框架)
- AI服务：Ollama, 通义千问, 智谱AI
- 数据源：百度搜索API, 智谱MCP
- 通信：WebSocket, RESTful API

## 项目结构

```
ByteFlow/
├── agents/                 # AI代理模块
│   ├── __init__.py         # 模块初始化文件
│   ├── agent_factory.py    # Agent工厂类
│   ├── base_agent.py       # Agent基类
│   ├── ollama_agent.py     # Ollama代理实现
│   ├── qwen_agent.py       # 通义千问代理实现
│   ├── zhipu_agent.py      # 智谱AI代理实现
│   ├── config_manager.py   # 配置管理器
│   └── .env                # 环境变量配置文件
├── app/                    # 前端应用
│   ├── index.html          # 主页
│   ├── workspace.html      # 工作区页面
│   ├── styles.css          # 主页样式
│   ├── workspace.css       # 工作区样式
│   ├── script.js           # 主页脚本
│   └── workspace.js        # 工作区脚本
├── main.py                 # FastAPI主应用
├── start_server.py         # 服务启动脚本
├── workflow.py             # 统一工作流引擎
├── workflow.yaml           # 工作流配置文件
└── README.md               # 项目说明文档
```

## 安装与配置

### 环境要求

- Python 3.8 或更高版本
- uvicorn (用于运行FastAPI应用)
- fastapi
- python-dotenv (可选，用于加载.env文件)
- requests (用于API调用)

### 安装依赖

```bash
pip install fastapi uvicorn python-dotenv requests
```

### 配置环境变量

在 `agents/.env` 文件中配置相关服务的API密钥和地址：

```env
# Ollama服务配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=deepseek-r1:32b

# 通义千问服务配置
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_DEFAULT_MODEL=qwen-plus-latest
DASHSCOPE_API_KEY=your_qwen_api_key

# 智谱MCP服务配置
ZHIPU_API_KEY=your_zhipu_api_key

# 百度千帆配置
BAIDU_API_KEY=your_baidu_api_key
```

## 运行项目

### 启动服务

有两种方式启动ByteFlow服务：

1. 使用启动脚本：
```bash
python start_server.py
```

2. 直接使用uvicorn：
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，可以通过浏览器访问：
- 主页：http://localhost:8000
- 工作区：http://localhost:8000/workspace

### 使用说明

1. 访问工作区页面 (http://localhost:8000/workspace)
2. 配置数据源选项：
   - 选择是否使用百度搜索API
   - 选择是否使用智谱MCP
3. 选择模型提供商 (Ollama或通义千问)
4. 输入报告主题和相关参数
5. 点击"开始生成报告"按钮
6. 在右侧进度区域实时查看报告生成进度
7. 报告生成完成后，可以下载或复制结果

## 工作流配置

系统通过 `workflow.yaml` 文件定义报告生成的工作流，包含以下角色：

- 结论提出者 (conclusion_generator)
- 政策分析师 (policy_analyst)
- 市场研究员 (market_researcher)
- 案例专家 (case_specialist)
- 技术解释者 (technical_interpreter)
- 社会观察员 (societal_observer)

每个角色都有详细的配置，包括系统提示词、温度参数、最大令牌数等。

## API接口

系统提供以下主要API接口：

- `GET /` - 返回主页
- `GET /workspace` - 返回工作区页面
- `GET /ws/{client_id}` - WebSocket连接端点
- `POST /api/report` - 报告生成接口

## 开发指南

### 添加新的AI代理

1. 创建新的代理类继承自 `BaseAgent`
2. 在 `AgentFactory` 中注册新的代理类型
3. 在 `workflow.yaml` 中添加相应的角色配置

### 扩展工作流

1. 修改 `workflow.yaml` 添加新的角色配置
2. 在前端页面中添加相应的展示逻辑
3. 在 `workflow.py` 中实现新的处理逻辑

## 贡献

欢迎提交Issue和Pull Request来改进ByteFlow项目。

## 许可证

本项目采用MIT许可证。

**[Hokkien-Bros-AI-ByteFlow](https://github.com/SimonSkywalke/Hokkien-Bros-AI-ByteFlow)**

## 致谢

感谢 [@z5013](https://github.com/z5013) 对本项目早期开发的重要贡献。尽管由于原始项目设计涉及隐私原因，我们新建了此开源仓库，但 @z5013 在功能设计、代码实现等方面提供了关键支持。我们非常感激其付出的努力和专业精神。