// ByteFlow 工作区 JavaScript
// 处理WebSocket连接、表单提交、进度展示等功能

class ByteFlowWorkspace {
    constructor() {
        this.ws = null;
        this.clientId = this.generateClientId();
        this.currentTaskId = null;
        this.isConnected = false;
        this.isGenerating = false;
        this.agentOutputs = {}; // 存储每个agent的输出
        this.reconnectAttempts = 0; // 重连尝试次数
        this.maxReconnectAttempts = 10; // 最大重连尝试次数
        this.reconnectDelay = 3000; // 重连延迟（毫秒）
        this.heartbeatInterval = null; // 心跳定时器
        this.lastActivityTime = Date.now(); // 最后活动时间
        this.connectionStartTime = null; // 连接开始时间
        
        this.init();
    }
    
    generateClientId() {
        return 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.setupTabSwitching();
        // 页面加载完成后自动填充API密钥
        this.loadApiKeys();
        console.log('🚀 ByteFlow 工作区已初始化');
    }
    
    // 自动读取并填充API密钥
    async loadApiKeys() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                
                // 填充百度API密钥（如果输入框为空）
                const baiduApiKeyInput = document.getElementById('baiduApiKey');
                if (baiduApiKeyInput && !baiduApiKeyInput.value) {
                    baiduApiKeyInput.value = config.baidu_api_key || '';
                }
                
                // 填充MCP API密钥（如果输入框为空）
                const mcpApiKeyInput = document.getElementById('mcpApiKey');
                if (mcpApiKeyInput && !mcpApiKeyInput.value) {
                    mcpApiKeyInput.value = config.mcp_api_key || '';
                }
            }
        } catch (error) {
            console.log('无法从后端获取配置信息:', error);
        }
    }
    
    setupTabSwitching() {
        // 设置标签页切换功能
        const tabButtons = document.querySelectorAll('.tab-btn');
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');
                this.switchTab(tabId);
            });
        });
        
        // 默认显示报告生成标签页内容
        this.switchTab('report');
    }
    
    switchTab(tabId) {
        // 更新标签按钮状态
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('active');
        
        // 显示对应的内容区域
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabId}-tab`).classList.add('active');
        
        // 特殊处理：报告标签页需要显示工作区
        const reportWorkspace = document.getElementById('reportWorkspace');
        if (reportWorkspace) {
            if (tabId === 'report') {
                reportWorkspace.classList.add('active');
            } else {
                reportWorkspace.classList.remove('active');
            }
        }
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.clientId}`;
        
        this.updateConnectionStatus('connecting', '正在连接...');
        console.log(`🔗 尝试连接到WebSocket: ${wsUrl}`);
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.connectionStartTime = Date.now();
                this.reconnectAttempts = 0; // 重置重连尝试次数
                this.updateConnectionStatus('connected', '已连接');
                console.log('✅ WebSocket 连接成功');
                
                // 发送心跳
                this.startHeartbeat();
                
                // 重新连接后，如果正在生成报告，请求最新的状态
                if (this.isGenerating && this.currentTaskId) {
                    console.log('🔄 重新连接后请求任务状态...');
                    this.requestTaskStatus(this.currentTaskId);
                }
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                    // 更新最后活动时间
                    this.lastActivityTime = Date.now();
                } catch (error) {
                    console.error('❌ 解析 WebSocket 消息失败:', error);
                    console.error('原始消息:', event.data);
                }
            };
            
            this.ws.onclose = (event) => {
                this.isConnected = false;
                this.connectionStartTime = null;
                this.updateConnectionStatus('disconnected', '连接断开');
                console.log('🔌 WebSocket 连接断开', event);
                
                // 清除心跳定时器
                if (this.heartbeatInterval) {
                    clearInterval(this.heartbeatInterval);
                    this.heartbeatInterval = null;
                }
                
                // 记录断开原因
                let closeReason = '未知原因';
                if (event.code === 1000) {
                    closeReason = '正常关闭';
                } else if (event.code === 1001) {
                    closeReason = '端点离开';
                } else if (event.code === 1002) {
                    closeReason = '协议错误';
                } else if (event.code === 1003) {
                    closeReason = '不支持的数据';
                } else if (event.code === 1005) {
                    closeReason = '没有状态码';
                } else if (event.code === 1006) {
                    closeReason = '连接异常关闭';
                } else if (event.code === 1007) {
                    closeReason = '数据格式错误';
                } else if (event.code === 1008) {
                    closeReason = '策略违规';
                } else if (event.code === 1009) {
                    closeReason = '消息过大';
                } else if (event.code === 1010) {
                    closeReason = '缺少扩展';
                } else if (event.code === 1011) {
                    closeReason = '意外情况';
                } else if (event.code === 1015) {
                    closeReason = 'TLS握手失败';
                }
                
                console.log(`🔌 连接断开原因: ${closeReason} (代码: ${event.code})`);
                
                // 尝试重连
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000); // 指数退避，最大30秒
                    console.log(`🔄 尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})，${delay}ms后重连`);
                    setTimeout(() => {
                        if (!this.isConnected) {
                            this.connectWebSocket();
                        }
                    }, delay);
                } else {
                    console.log('❌ 达到最大重连尝试次数，停止重连');
                    this.updateConnectionStatus('disconnected', '连接失败');
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('❌ WebSocket 错误:', error);
                this.updateConnectionStatus('disconnected', '连接错误');
            };
            
        } catch (error) {
            console.error('❌ WebSocket 连接失败:', error);
            this.updateConnectionStatus('disconnected', '连接失败');
            
            // 清除心跳定时器
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
                this.heartbeatInterval = null;
            }
            
            // 尝试重连
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000); // 指数退避，最大30秒
                console.log(`🔄 尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})，${delay}ms后重连`);
                setTimeout(() => {
                    if (!this.isConnected) {
                        this.connectWebSocket();
                    }
                }, delay);
            } else {
                console.log('❌ 达到最大重连尝试次数，停止重连');
                this.updateConnectionStatus('disconnected', '连接失败');
            }
        }
    }
    
    // 添加请求任务状态的方法
    requestTaskStatus(taskId) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'get_status',
                task_id: taskId
            }));
        }
    }
    
    startHeartbeat() {
        // 清除之前的定时器
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
        
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
                // 检查连接持续时间
                if (this.connectionStartTime) {
                    const duration = Date.now() - this.connectionStartTime;
                    console.log(`💓 心跳发送 (连接持续时间: ${Math.floor(duration/1000)}秒)`);
                }
            } else if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                // 连接中，等待连接完成
                console.log('⏳ WebSocket 连接中，等待连接完成...');
            } else {
                // 连接已断开，尝试重连
                console.log('⚠️ WebSocket 连接已断开，尝试重连...');
                this.connectWebSocket();
            }
        }, 25000); // 25秒心跳
    }
    
    updateConnectionStatus(status, message) {
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.className = `connection-status ${status}`;
            statusElement.querySelector('span').textContent = message;
        }
    }
    
    setupEventListeners() {
        // 表单提交事件
        const reportForm = document.getElementById('reportForm');
        if (reportForm) {
            reportForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitReport();
            });
        }
        
        // 窗口关闭事件
        window.addEventListener('beforeunload', () => {
            if (this.ws) {
                this.ws.close();
            }
        });
        
        // 回车快捷键
        const topicTextarea = document.getElementById('reportTopic');
        if (topicTextarea) {
            topicTextarea.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    this.submitReport();
                }
            });
        }
        
        // 百度API测试按钮
        const testBaiduBtn = document.querySelector('[onclick="testBaiduAPI()"]');
        if (testBaiduBtn) {
            // 移除onclick属性并添加事件监听器
            testBaiduBtn.removeAttribute('onclick');
            testBaiduBtn.addEventListener('click', () => {
                if (typeof this.testBaiduAPI === 'function') {
                    this.testBaiduAPI();
                } else {
                    // 如果this.testBaiduAPI不可用，调用全局函数
                    testBaiduAPI();
                }
            });
        }
        
        // MCP测试按钮
        const testMcpBtn = document.querySelector('[onclick="testMcpAPI()"]');
        if (testMcpBtn) {
            // 移除onclick属性并添加事件监听器
            testMcpBtn.removeAttribute('onclick');
            testMcpBtn.addEventListener('click', () => {
                if (typeof this.testMcpAPI === 'function') {
                    this.testMcpAPI();
                } else {
                    // 如果this.testMcpAPI不可用，调用全局函数
                    testMcpAPI();
                }
            });
        }
        
        // 停止任务按钮
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            // 移除可能存在的旧事件监听器
            const newCancelBtn = cancelBtn.cloneNode(true);
            cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
            newCancelBtn.addEventListener('click', () => {
                this.cancelTask();
            });
        }
    }

    async cancelTask() {
        if (!this.currentTaskId) {
            this.showNotification('当前没有正在运行的任务', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/cancel-task/${this.currentTaskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.showNotification(result.message, 'success');
            
            // 重置界面状态
            this.setGeneratingState(false);
            this.currentTaskId = null;
            
        } catch (error) {
            console.error('❌ 取消任务失败:', error);
            this.showNotification(`取消任务失败：${error.message}`, 'error');
        }
    }
    
    async submitReport() {
        if (this.isGenerating) {
            this.showNotification('已有任务正在进行中，请稍候...', 'warning');
            return;
        }
        
        if (!this.isConnected) {
            this.showNotification('WebSocket 未连接，请刷新页面重试', 'error');
            return;
        }
        
        const formData = new FormData(document.getElementById('reportForm'));
        const config = getCurrentConfig();
        
        // 修复API密钥传递逻辑
        let baiduApiKey = null;
        if (config.useBaiduAPI) {
            baiduApiKey = config.baiduApiKey || document.getElementById('baiduApiKey')?.value || null;
        } else if (config.useBailian) {
            baiduApiKey = config.mcpApiKey || document.getElementById('mcpApiKey')?.value || null;
        }
        
        const requestData = {
            topic: formData.get('topic').trim(),
            word_limit: parseInt(formData.get('word_limit')),
            report_type: formData.get('report_type'),
            use_baidu_api: config.useBaiduAPI,
            use_bailian: config.useBailian,
            model_provider: config.modelProvider,
            baidu_api_key: baiduApiKey,
            // 添加客户端ID
            client_id: this.clientId
        };
        
        // 验证输入
        if (!requestData.topic) {
            this.showNotification('请输入报告主题', 'error');
            return;
        }
        
        if (requestData.topic.length < 10) {
            this.showNotification('报告主题过短，请详细描述您的需求', 'error');
            return;
        }
        
        // 验证API密钥
        if (requestData.use_baidu_api && !requestData.baidu_api_key) {
            this.showNotification('请提供百度API密钥', 'error');
            return;
        }
        
        if (requestData.use_bailian && !requestData.baidu_api_key) {
            this.showNotification('请提供MCP API密钥', 'error');
            return;
        }
        
        try {
            this.setGeneratingState(true);
            this.showCurrentTask(requestData.topic);
            this.addChatMessage('system', `开始生成报告：${requestData.topic}`);
            
            // 清空之前的agent输出
            this.agentOutputs = {};
            
            // 发送请求到后端
            const response = await fetch('/api/generate-report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.currentTaskId = result.task_id;
            
            this.addChatMessage('system', `任务已创建，ID: ${this.currentTaskId}`);
            this.showNotification('报告生成任务已开始，请等待进度更新...', 'success');
            
        } catch (error) {
            console.error('❌ 提交报告任务失败:', error);
            this.setGeneratingState(false);
            this.addChatMessage('system', `错误：${error.message}`, 'error');
            this.showNotification(`提交失败：${error.message}`, 'error');
        }
    }
    
    // 添加显示当前任务的函数
    showCurrentTask(topic) {
        const currentTask = document.getElementById('currentTask');
        const taskTopic = document.getElementById('taskTopic');
        
        if (currentTask && taskTopic) {
            taskTopic.textContent = topic;
            currentTask.style.display = 'block';
        }
    }
    
    hideCurrentTask() {
        const currentTask = document.getElementById('currentTask');
        if (currentTask) {
            currentTask.style.display = 'none';
        }
    }
    
    handleWebSocketMessage(data) {
        console.log('📨 收到 WebSocket 消息:', data);
        
        // 确保消息类型存在
        if (!data || !data.type) {
            console.warn('收到无效的 WebSocket 消息:', data);
            return;
        }
        
        switch (data.type) {
            case 'progress_update':
                this.updateProgress(data);
                break;
            case 'completion':
                this.handleCompletion(data);
                break;
            case 'error':
                this.handleError(data);
                break;
            case 'agent_output':
                this.handleAgentOutput(data);
                break;
            case 'cancelled':
                this.handleCancelled(data);
                break;
            case 'pong':
                // 心跳响应，无需处理
                break;
            default:
                console.warn('未知的 WebSocket 消息类型:', data.type, data);
        }
    }

    handleAgentOutput(data) {
        // 处理agent输出消息
        const { agent_name, role_name, step_name, content, word_count } = data;
        
        // 验证必要字段
        if (!role_name || !step_name || content === undefined) {
            console.warn('收到不完整的 agent_output 消息:', data);
            return;
        }
        
        // 存储agent输出
        if (!this.agentOutputs[role_name]) {
            this.agentOutputs[role_name] = [];
        }
        
        this.agentOutputs[role_name].push({
            step_name,
            content,
            word_count,
            timestamp: new Date()
        });
        
        // 在UI中显示agent输出
        this.displayAgentOutput(role_name, step_name, content, word_count);
    }
    
    displayAgentOutput(roleName, stepName, content, wordCount) {
        // 验证输入
        if (!roleName || !stepName || content === undefined) {
            console.warn('displayAgentOutput收到无效参数:', {roleName, stepName, content});
            return;
        }
        
        // 查找或创建AI工作进度区域
        let aiProgressContainer = document.getElementById('ai-progress-container');
        if (!aiProgressContainer) {
            // 创建AI工作进度容器
            const container = document.createElement('div');
            container.id = 'ai-progress-container';
            container.className = 'ai-progress-container';
            container.innerHTML = '<h3><i class="fas fa-robot"></i> AI工作进度</h3>';
            
            // 插入到聊天容器之后
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                // 确保插入位置正确
                const nextSibling = chatContainer.nextSibling;
                if (nextSibling) {
                    chatContainer.parentNode.insertBefore(container, nextSibling);
                } else {
                    chatContainer.parentNode.appendChild(container);
                }
            } else {
                const progressSection = document.querySelector('.progress-section');
                if (progressSection) {
                    // 插入到进度部分的开头
                    if (progressSection.firstChild) {
                        progressSection.insertBefore(container, progressSection.firstChild);
                    } else {
                        progressSection.appendChild(container);
                    }
                } else {
                    document.querySelector('.workspace-main').appendChild(container);
                }
            }
            aiProgressContainer = container;
        }
        
        // 确保AI工作进度区域可见
        aiProgressContainer.style.display = 'block';
        
        // 清理内容，移除思考过程
        console.log('📥 原始Agent输出:', content);
        const cleanedContent = this.cleanAgentOutput(content);
        console.log('📤 清理后Agent输出:', cleanedContent);
        
        // 创建唯一ID以避免重复
        const elementId = `agent-output-${roleName}-${stepName}`;
        let agentOutputDiv = document.getElementById(elementId);
        if (!agentOutputDiv) {
            // 创建agent输出区域
            agentOutputDiv = document.createElement('div');
            agentOutputDiv.id = elementId;
            agentOutputDiv.className = 'agent-output';
            agentOutputDiv.innerHTML = `
                <div class="agent-header">
                    <h4><i class="fas fa-user"></i> ${roleName}</h4>
                </div>
                <div class="agent-content"></div>
            `;
            aiProgressContainer.appendChild(agentOutputDiv);
        }
        
        // 更新内容
        const contentDiv = agentOutputDiv.querySelector('.agent-content');
        if (contentDiv) {
            contentDiv.innerHTML = `
                <div class="output-step">
                    <span class="step-name">${stepName}</span>
                    <span class="word-count">${wordCount} 字符</span>
                </div>
                <div class="output-content">${this.escapeHtml(cleanedContent)}</div>
            `;
            
            // 滚动到最新输出
            if (aiProgressContainer.scrollHeight > aiProgressContainer.clientHeight) {
                aiProgressContainer.scrollTop = aiProgressContainer.scrollHeight;
            }
        }
        
        // 确保容器可见
        aiProgressContainer.style.display = 'block';
        
        // 如果在标签页中，确保标签页可见
        const reportWorkspace = document.getElementById('reportWorkspace');
        if (reportWorkspace) {
            reportWorkspace.classList.add('active');
        }
    }
    
    cleanAgentOutput(content) {
        // 清理agent输出，移除思考过程
        if (!content) return '';
        
        console.log('🔍 开始清理Agent输出');
        console.log('📝 原始输出:', content);
        
        // 移除思考过程相关的内容 - 更严格的清理
        let cleaned = content;
        
        // 移除标签及其内容
        cleaned = cleaned.replace(/<.*?>/g, '');
        
        // 移除以"思考"、"分析"、"推理"等词开头的段落
        const beforeParagraphRemoval = cleaned;
        cleaned = cleaned.replace(/(?:思考|分析|推理|反思|Thought|Reasoning|Analysis)[:：]?\s*.*?(?=\n\s*\n|\Z)/gi, '');
        if (beforeParagraphRemoval !== cleaned) {
            console.log('🧹 移除了以思考词开头的段落');
        }
        
        // 移除"嗯，现在"、"让我"等开头的思考内容
        const beforeThinkingRemoval = cleaned;
        cleaned = cleaned.replace(/^(?:嗯|啊|呃|哦|嘿|好)?[，,]?\s*(?:现在|让我|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|用户要求|必须|确保|注意|记住)/gm, '');
        if (beforeThinkingRemoval !== cleaned) {
            console.log('🧹 移除了以思考词开头的内容');
        }
        
        // 移除包含明显思考过程关键词的行（但保留可能包含实际内容的句子）
        const lines = cleaned.split('\n');
        const filteredLines = [];
        let removedLines = 0;
        for (const line of lines) {
            // 如果行中包含明显的思考过程关键词，且不包含句号等结束符号，则跳过
            if (/(?:思考|分析|推理|反思|Thought|Reasoning|Analysis|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|意味着|可能|挑战|缺失|限制|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住)/i.test(line) && 
                !/[。！？.!?]/.test(line)) {
                // 跳过这行
                removedLines++;
                console.log('🗑️ 移除纯思考行:', line);
                continue;
            }
            // 如果行包含思考关键词但也有实际内容（有结束符号），则清理思考部分但保留内容
            else if (/(?:思考|分析|推理|反思|Thought|Reasoning|Analysis|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|因为|所以|但是|然而|不过|虽然|尽管|即使|如果|假如|假设|当|当...时|同时|此外|另外|而且|并且|或者|还是|要么|不是|没有|不会|不能|不要|不用|不可以|不允许|禁止|严禁|不得|不可|不宜|不建议|不推荐|不提倡|不鼓励|不支持|不接受|不承认|不认可|不赞同|不赞成|不支持|不接受|不承认|不认可|不赞同|不赞成|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住)/i.test(line)) {
                // 清理思考部分但保留实际内容
                const beforeClean = line;
                const cleanedLine = line.replace(/(?:思考|分析|推理|反思|Thought|Reasoning|Analysis|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|因为|所以|但是|然而|不过|虽然|尽管|即使|如果|假如|假设|当|当...时|同时|此外|另外|而且|并且|或者|还是|要么|不是|没有|不会|不能|不要|不用|不可以|不允许|禁止|严禁|不得|不可|不宜|不建议|不推荐|不提倡|不鼓励|不支持|不接受|不承认|不认可|不赞同|不赞成|不支持|不接受|不承认|不认可|不赞同|不赞成|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住).*?[，,。！!？?]/i, '');
                if (beforeClean !== cleanedLine) {
                    console.log('🧹 清理了思考内容:', beforeClean, '->', cleanedLine);
                }
                // 如果清理后的内容足够长，则保留，否则跳过
                if (cleanedLine.trim() && cleanedLine.trim().length > 15) {
                    filteredLines.push(cleanedLine.trim());
                } else {
                    removedLines++;
                    console.log('🗑️ 移除清理后过短的行:', line);
                }
            }
            else {
                // 过滤掉太短的行（可能是清理过程中产生的无意义内容）
                if (line.trim().length > 5 || /[。！？.!?]/.test(line)) {
                    filteredLines.push(line);
                } else if (line.trim().length > 0) {
                    console.log('🗑️ 移除过短的行:', line);
                    removedLines++;
                }
            }
        }
        
        cleaned = filteredLines.join('\n');
        
        // 移除多余的空白行
        const beforeWhitespaceRemoval = cleaned;
        cleaned = cleaned.replace(/\n\s*\n\s*\n/g, '\n\n');
        if (beforeWhitespaceRemoval !== cleaned) {
            console.log('🧹 移除了多余的空白行');
        }
        
        // 移除行首的"嗯"、"啊"、"好"等语气词
        const beforeInterjectionRemoval = cleaned;
        cleaned = cleaned.replace(/^\s*[嗯啊呃哦嘿好]\s*/gm, '');
        if (beforeInterjectionRemoval !== cleaned) {
            console.log('🧹 移除了行首的语气词');
        }
        
        // 移除常见的思考过程短语
        const beforePhraseRemoval = cleaned;
        cleaned = cleaned.replace(/(?:让我|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|因为|所以|但是|然而|不过|虽然|尽管|即使|如果|假如|假设|当|当...时|同时|此外|另外|而且|并且|或者|还是|要么|不是|没有|不会|不能|不要|不用|不可以|不允许|禁止|严禁|不得|不可|不宜|不建议|不推荐|不提倡|不鼓励|不支持|不接受|不承认|不认可|不赞同|不赞成|不支持|不接受|不承认|不认可|不赞同|不赞成|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住|平衡进展和挑战|重复事实|要有洞察力|输出必须是中文|格式|只给出结论|包含任何)/gi, '');
        if (beforePhraseRemoval !== cleaned) {
            console.log('🧹 移除了常见的思考过程短语');
        }
        
        // 移除多余的逗号和句号
        const beforePunctuationRemoval = cleaned;
        cleaned = cleaned.replace(/^[，,。！!？?]+/gm, '').replace(/[，,。！!？?]+$/gm, '');
        if (beforePunctuationRemoval !== cleaned) {
            console.log('🧹 清理了多余的标点符号');
        }
        
        // 如果清理后的内容过短，返回原始内容（可能是误删）
        if (cleaned.trim().length < content.length / 4) {  // 降低阈值到1/4
            console.warn("清理后内容过短，可能误删了有效内容，返回原始内容");
            console.log('📊 原始长度:', content.length, '清理后长度:', cleaned.trim().length);
            return content.trim();
        }
        
        console.log('✅ 清理完成: 移除了', removedLines, '行思考内容');
        console.log('📝 清理后输出:', cleaned.trim());
        return cleaned.trim();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    updateProgress(data) {
        const { task_id, status, progress, message, current_step, timestamp } = data;
        
        // 更新进度条
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const taskStatus = document.getElementById('taskStatus');
        const currentTask = document.getElementById('currentTask');
        
        if (progressFill) {
            progressFill.style.setProperty('--target-width', `${progress}%`);
            progressFill.style.width = `${progress}%`;
        }
        if (progressText) progressText.textContent = `${progress}%`;
        if (taskStatus) taskStatus.textContent = message;
        if (currentTask) currentTask.style.display = 'block';
        
        // 添加进度消息到聊天历史
        this.addChatMessage('system', message);
        
        // 如果进度达到100%，隐藏进度条
        if (progress >= 100) {
            setTimeout(() => {
                if (currentTask) currentTask.style.display = 'none';
            }, 2000);
        }
    }
    
    handleCompletion(data) {
        const { task_id, status, progress, message, result } = data;
        
        // 更新进度条
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const taskStatus = document.getElementById('taskStatus');
        const currentTask = document.getElementById('currentTask');
        
        if (progressFill) progressFill.style.width = '100%';
        if (progressText) progressText.textContent = '100%';
        if (taskStatus) taskStatus.textContent = '完成';
        if (currentTask) currentTask.style.display = 'block';
        
        // 显示完成消息
        this.addChatMessage('system', message, 'success');
        
        // 显示最终报告
        if (result && result.answer) {
            this.displayFinalReport(result);
        }
        
        // 重置生成状态
        this.setGeneratingState(false);
        
        // 清空当前任务ID
        this.currentTaskId = null;
        
        // 显示通知
        this.showNotification('报告生成完成！', 'success');
    }
    
    displayFinalReport(reportData) {
        // 隐藏AI工作进度区域
        const aiProgressContainer = document.getElementById('ai-progress-container');
        if (aiProgressContainer) {
            aiProgressContainer.style.display = 'none';
        }
        
        // 创建或更新最终报告显示区域
        let reportContainer = document.getElementById('final-report');
        if (!reportContainer) {
            // 创建报告容器
            const container = document.createElement('div');
            container.id = 'final-report';
            container.className = 'final-report-container';
            container.innerHTML = '<h3><i class="fas fa-file-alt"></i> 最终报告</h3>';
            // 插入到工作区容器中
            const workspaceContainer = document.querySelector('.workspace-container');
            if (workspaceContainer) {
                // 插入到进度部分之后
                const progressSection = document.querySelector('.progress-section');
                if (progressSection) {
                    progressSection.parentNode.insertBefore(container, progressSection.nextSibling);
                } else {
                    workspaceContainer.appendChild(container);
                }
            } else {
                document.querySelector('.workspace-main').appendChild(container);
            }
            reportContainer = container;
        }
        
        // 显示报告内容
        reportContainer.innerHTML = `
            <h3><i class="fas fa-file-alt"></i> 最终报告</h3>
            <div class="report-header">
                <h4>${this.escapeHtml(reportData.question || '未知主题')}</h4>
                <div class="report-meta">
                    <span>字数: ${reportData.word_count || 0}/${reportData.word_limit || 1000}</span>
                    <span>类型: ${reportData.type || '分析报告'}</span>
                </div>
            </div>
            <div class="report-content">
                ${this.formatReportContent(reportData.answer || '报告内容为空')}
            </div>
            <div class="report-actions">
                <button onclick="copyReportToClipboard()" class="action-btn">
                    <i class="fas fa-copy"></i> 复制报告
                </button>
                <button onclick="downloadReport()" class="action-btn">
                    <i class="fas fa-download"></i> 下载报告
                </button>
            </div>
        `;
        
        // 滚动到报告位置
        reportContainer.scrollIntoView({ behavior: 'smooth' });
    }
    
    formatReportContent(content) {
        // 简单的段落格式化
        if (!content) return '';
        
        // 按段落分割并格式化
        const paragraphs = content.split('\n\n').filter(p => p.trim());
        return paragraphs.map(paragraph => 
            `<p>${this.escapeHtml(paragraph.trim())}</p>`
        ).join('');
    }
    
    addChatMessage(role, content, type = 'info') {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role === 'user' ? 'bot-message' : 'system-message'} ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                ${role === 'user' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-info-circle"></i>'}
            </div>
            <div class="message-content">
                <div class="message-text">${this.escapeHtml(content)}</div>
                <div class="message-time">${timestamp}</div>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        
        // 滚动到最新消息
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    setGeneratingState(isGenerating) {
        this.isGenerating = isGenerating;
        
        const generateBtn = document.getElementById('generateBtn');
        const cancelBtn = document.getElementById('cancelBtn');
        const typingIndicator = document.getElementById('typingIndicator');
        
        if (generateBtn) {
            generateBtn.innerHTML = isGenerating ? 
                '<i class="fas fa-spinner fa-spin"></i> 生成中...' : 
                '<i class="fas fa-magic"></i> <span>开始生成报告</span>';
            generateBtn.disabled = isGenerating;
        }
        
        if (cancelBtn) {
            cancelBtn.style.display = isGenerating ? 'inline-flex' : 'none';
        }
        
        if (typingIndicator) {
            typingIndicator.style.display = isGenerating ? 'flex' : 'none';
        }
        
        // 如果停止生成，隐藏当前任务显示
        if (!isGenerating) {
            this.hideCurrentTask();
        }
    }
    
    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            ${message}
        `;
        
        // 添加到页面
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
    
    async testBaiduAPI() {
        const apiKey = document.getElementById('baiduApiKey').value;
        const query = document.getElementById('testQuery').value;
        
        if (!apiKey) {
            this.showNotification('请输入百度API密钥', 'error');
            return;
        }
        
        if (!query) {
            this.showNotification('请输入测试查询内容', 'error');
            return;
        }
        
        const testResult = document.getElementById('baiduTestResult');
        if (testResult) {
            testResult.className = 'test-result loading';
            testResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在测试连接...';
            testResult.style.display = 'block';
        }
        
        try {
            const response = await fetch('/api/test-baidu', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    query: query
                })
            });
            
            const result = await response.json();
            
            if (testResult) {
                if (result.success) {
                    testResult.className = 'test-result success';
                    testResult.innerHTML = `
                        <i class="fas fa-check-circle"></i> 
                        ${result.message} (获取到 ${result.result_count} 条结果)
                    `;
                    
                    // 显示详细内容
                    this.displayBaiduResponseDetail(result);
                } else {
                    testResult.className = 'test-result error';
                    testResult.innerHTML = `
                        <i class="fas fa-exclamation-circle"></i> 
                        ${result.error}
                    `;
                }
            }
        } catch (error) {
            if (testResult) {
                testResult.className = 'test-result error';
                testResult.innerHTML = `
                    <i class="fas fa-exclamation-circle"></i> 
                    测试失败: ${error.message}
                `;
            }
        }
    }
    
    displayBaiduResponseDetail(result) {
        const responseDetail = document.getElementById('baiduResponseDetail');
        if (!responseDetail) return;
        
        responseDetail.style.display = 'block';
        
        // 显示格式化内容
        const formattedContent = document.getElementById('formatted-content');
        if (formattedContent && result.response_data) {
            formattedContent.innerHTML = this.formatBaiduResponse(result.response_data);
        }
        
        // 显示原始JSON
        const rawJson = document.getElementById('raw-json');
        if (rawJson && result.response_data) {
            rawJson.textContent = JSON.stringify(result.response_data, null, 2);
        }
        
        // 设置标签页切换
        const tabButtons = responseDetail.querySelectorAll('.response-tab-btn');
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');
                this.switchResponseTab(tabId, 'baidu');
            });
        });
    }
    
    formatBaiduResponse(data) {
        if (!data || !data.choices || !data.choices[0]) return '无有效数据';
        
        const choice = data.choices[0];
        const content = choice.message?.content || '无内容';
        
        return `
            <div class="formatted-item">
                <h6>模型响应</h6>
                <p>${this.escapeHtml(content.substring(0, 500))}${content.length > 500 ? '...' : ''}</p>
            </div>
        `;
    }
    
    switchResponseTab(tabId, prefix) {
        // 更新标签按钮状态
        document.querySelectorAll(`#${prefix}ResponseDetail .response-tab-btn`).forEach(btn => {
            btn.classList.remove('active');
        });
        const activeButton = document.querySelector(`#${prefix}ResponseDetail .response-tab-btn[data-tab="${tabId}"]`);
        if (activeButton) {
            activeButton.classList.add('active');
        }
        
        // 显示对应的内容区域
        document.querySelectorAll(`#${prefix}ResponseDetail .response-tab-content`).forEach(content => {
            content.classList.remove('active');
        });
        
        // 根据tabId确定正确的内容区域ID
        let contentId;
        if (tabId === 'mcp-formatted') {
            contentId = 'mcp-formatted-content';
        } else if (tabId === 'mcp-raw') {
            contentId = 'mcp-raw-content';
        } else if (tabId === 'formatted') {
            contentId = 'formatted-content';
        } else if (tabId === 'raw') {
            contentId = 'raw-content';
        }
        
        if (contentId) {
            const contentElement = document.getElementById(contentId);
            if (contentElement) {
                contentElement.classList.add('active');
            }
        }
    }
    
    async testMcpAPI() {
        const apiKey = document.getElementById('mcpApiKey').value;
        const query = document.getElementById('mcpTestQuery').value;
        const maxResults = document.getElementById('mcpMaxResults').value;
        
        if (!apiKey) {
            this.showNotification('请输入MCP API密钥', 'error');
            return;
        }
        
        if (!query) {
            this.showNotification('请输入测试查询内容', 'error');
            return;
        }
        
        const testResult = document.getElementById('mcpTestResult');
        if (testResult) {
            testResult.className = 'test-result loading';
            testResult.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在测试连接...';
            testResult.style.display = 'block';
        }
        
        try {
            const response = await fetch('/api/test-mcp', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    query: query,
                    max_results: parseInt(maxResults)
                })
            });
            
            const result = await response.json();
            
            if (testResult) {
                if (result.success) {
                    testResult.className = 'test-result success';
                    testResult.innerHTML = `
                        <i class="fas fa-check-circle"></i> 
                        ${result.message} (获取到 ${result.result_count} 条结果)
                    `;
                    
                    // 显示详细内容
                    this.displayMcpResponseDetail(result);
                } else {
                    testResult.className = 'test-result error';
                    testResult.innerHTML = `
                        <i class="fas fa-exclamation-circle"></i> 
                        ${result.error}
                    `;
                }
            }
        } catch (error) {
            if (testResult) {
                testResult.className = 'test-result error';
                testResult.innerHTML = `
                    <i class="fas fa-exclamation-circle"></i> 
                    测试失败: ${error.message}
                `;
            }
        }
    }
    
    displayMcpResponseDetail(result) {
        const responseDetail = document.getElementById('mcpResponseDetail');
        if (!responseDetail) return;
        
        responseDetail.style.display = 'block';
        
        // 显示格式化内容
        const formattedContent = document.getElementById('mcp-formatted-content');
        if (formattedContent && result.response_data && result.response_data.search_results) {
            formattedContent.innerHTML = this.formatMcpResponse(result.response_data.search_results);
        } else if (formattedContent && result.response_data) {
            // 如果没有search_results，直接显示响应数据
            formattedContent.innerHTML = this.formatMcpResponse([result.response_data]);
        }
        
        // 显示原始响应
        const rawSse = document.getElementById('mcp-raw-sse');
        if (rawSse && result.raw_response) {
            rawSse.textContent = result.raw_response;
        } else if (rawSse && result.response_data) {
            rawSse.textContent = JSON.stringify(result.response_data, null, 2);
        }
        
        // 设置标签页切换
        const tabButtons = responseDetail.querySelectorAll('.response-tab-btn');
        tabButtons.forEach(button => {
            // 移除旧的事件监听器
            button.removeEventListener('click', this._tabSwitchHandler);
            // 添加新的事件监听器
            this._tabSwitchHandler = (e) => {
                const tabId = e.target.getAttribute('data-tab');
                this.switchResponseTab(tabId, 'mcp');
            };
            button.addEventListener('click', this._tabSwitchHandler);
        });
    }
    
    formatMcpResponse(results) {
        if (!Array.isArray(results) || results.length === 0) {
            // 尝试处理单个对象
            if (typeof results === 'object' && results !== null) {
                results = [results];
            } else {
                return '<p>无搜索结果</p>';
            }
        }
        
        let html = '';
        // 限制显示前10个结果
        const displayResults = Array.isArray(results) ? results.slice(0, 10) : [results];
        
        displayResults.forEach((result, index) => {
            // 尝试从不同的字段获取标题和内容
            const title = result.title || result.name || result.headline || result.query || '无标题';
            const snippet = result.snippet || result.description || result.content || result.summary || '无摘要';
            const source = result.source || result.url || result.link || '未知来源';
            
            html += `
                <div class="formatted-item">
                    <h6>${index + 1}. ${this.escapeHtml(title)}</h6>
                    <p>${this.escapeHtml(snippet)}</p>
                    <p><small>来源: ${this.escapeHtml(source)}</small></p>
                </div>
            `;
        });
        
        return html || '<p>无搜索结果</p>';
    }

}

// 全局函数确保前端功能正常
function copyReportToClipboard() {
    const reportContent = document.querySelector('#final-report .report-content');
    if (reportContent) {
        const text = reportContent.innerText;
        navigator.clipboard.writeText(text).then(() => {
            // 显示通知
            if (window.workspace && typeof window.workspace.showNotification === 'function') {
                window.workspace.showNotification('报告已复制到剪贴板！', 'success');
            } else {
                alert('报告已复制到剪贴板！');
            }
        }).catch(err => {
            console.error('复制失败:', err);
            if (window.workspace && typeof window.workspace.showNotification === 'function') {
                window.workspace.showNotification('复制失败，请手动复制', 'error');
            } else {
                alert('复制失败，请手动复制');
            }
        });
    }
}

function downloadReport() {
    const reportHeader = document.querySelector('#final-report .report-header h4');
    const reportContent = document.querySelector('#final-report .report-content');
    
    if (reportHeader && reportContent) {
        const title = reportHeader.innerText;
        const content = reportContent.innerText;
        
        const blob = new Blob([`# ${title}\n\n${content}`], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title}.md`;
        document.body.appendChild(a);
        a.click();
        
        // 清理
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
    }
}

// 获取当前配置
function getCurrentConfig() {
    return {
        useBaiduAPI: document.getElementById('useBaiduAPI')?.checked || false,
        useBailian: document.getElementById('useBailian')?.checked || false,
        modelProvider: document.getElementById('modelProvider')?.value || 'ollama',
        baiduApiKey: document.getElementById('baiduApiKey')?.value || '',
        mcpApiKey: document.getElementById('mcpApiKey')?.value || ''
    };
}

// 切换密码显示/隐藏
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

// 保存百度配置
function saveBaiduConfig() {
    const apiKey = document.getElementById('baiduApiKey').value;
    if (apiKey) {
        localStorage.setItem('baiduApiKey', apiKey);
        if (window.workspace && typeof window.workspace.showNotification === 'function') {
            window.workspace.showNotification('百度API密钥已保存到本地存储', 'success');
        } else {
            alert('百度API密钥已保存到本地存储');
        }
    }
}

// 保存MCP配置
function saveMcpConfig() {
    const apiKey = document.getElementById('mcpApiKey').value;
    if (apiKey) {
        localStorage.setItem('mcpApiKey', apiKey);
        if (window.workspace && typeof window.workspace.showNotification === 'function') {
            window.workspace.showNotification('MCP API密钥已保存到本地存储', 'success');
        } else {
            alert('MCP API密钥已保存到本地存储');
        }
    }
}

// 清除百度测试结果
function clearBaiduResult() {
    const testResult = document.getElementById('baiduTestResult');
    const responseDetail = document.getElementById('baiduResponseDetail');
    
    if (testResult) testResult.style.display = 'none';
    if (responseDetail) responseDetail.style.display = 'none';
}

// 清除MCP测试结果
function clearMcpResult() {
    const testResult = document.getElementById('mcpTestResult');
    const responseDetail = document.getElementById('mcpResponseDetail');
    
    if (testResult) testResult.style.display = 'none';
    if (responseDetail) responseDetail.style.display = 'none';
}

// 清空历史记录
function clearHistory() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="message bot-message">
                    <div class="message-avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="message-content">
                        <div class="message-text">
                            欢迎使用 ByteFlow 智能报告生成系统！<br>
                            请在左侧输入您的报告主题，我将协调多个AI专家为您生成高质量的报告。
                        </div>
                        <div class="message-time">${new Date().toLocaleTimeString()}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // 清空agent输出
    const agentOutputs = document.getElementById('agent-outputs');
    if (agentOutputs) {
        agentOutputs.innerHTML = '<h3><i class="fas fa-robot"></i> Agent 实时输出</h3>';
    }
    
    // 清空最终报告
    const finalReport = document.getElementById('final-report');
    if (finalReport) {
        finalReport.innerHTML = '';
    }
    
    // 显示通知
    if (window.workspace && typeof window.workspace.showNotification === 'function') {
        window.workspace.showNotification('历史记录已清空', 'success');
    }
}

// 自动读取并填充保存的API密钥
function loadSavedApiKeys() {
    // 从localStorage读取保存的API密钥
    const savedBaiduApiKey = localStorage.getItem('baiduApiKey');
    const savedMcpApiKey = localStorage.getItem('mcpApiKey');
    
    // 填充百度API密钥（如果输入框为空）
    const baiduApiKeyInput = document.getElementById('baiduApiKey');
    if (baiduApiKeyInput && !baiduApiKeyInput.value && savedBaiduApiKey) {
        baiduApiKeyInput.value = savedBaiduApiKey;
    }
    
    // 填充MCP API密钥（如果输入框为空）
    const mcpApiKeyInput = document.getElementById('mcpApiKey');
    if (mcpApiKeyInput && !mcpApiKeyInput.value && savedMcpApiKey) {
        mcpApiKeyInput.value = savedMcpApiKey;
    }
}

// 初始化工作区
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化以确保DOM完全加载
    setTimeout(() => {
        window.workspace = new ByteFlowWorkspace();
        
        // 页面加载完成后自动填充API密钥
        loadSavedApiKeys();
        
        // 确保按钮事件监听器正确设置
        setTimeout(() => {
            if (window.workspace && typeof window.workspace.setupEventListeners === 'function') {
                // 重新设置事件监听器
                window.workspace.setupEventListeners();
            }
        }, 100);
    }, 100);
});
