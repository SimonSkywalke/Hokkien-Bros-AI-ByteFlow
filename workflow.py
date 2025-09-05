#!/usr/bin/env python3
"""
workflow.py - 统一的工作流引擎

功能：
1. 合并报告生成和评价工作流
2. 实现实时agent输出显示
3. 统一配置为workflow.yaml
"""

import json
import re
import os
import sys
import time
import asyncio
from typing import Dict, List, Optional, Tuple, NamedTuple, Any
from pathlib import Path

# 添加 agents 目录到路径
current_dir = Path(__file__).parent
agents_dir = current_dir / "agents"
sys.path.insert(0, str(agents_dir))

# 全局AgentFactory实例，避免重复初始化
_global_agent_factory = None

# 添加全局变量用于任务取消检查
# 注意：在实际部署中，这应该从主应用传递过来
_task_cancel_checker = None

def set_task_cancel_checker(checker):
    """设置任务取消检查器"""
    global _task_cancel_checker
    _task_cancel_checker = checker

async def check_task_cancelled(task_id: str) -> bool:
    """检查任务是否被取消"""
    if _task_cancel_checker:
        return await _task_cancel_checker(task_id)
    return False

# 导入 agents 模块
try:
    from agents.agent_factory import AgentFactory
    print("✅ agents 模块导入成功")
except ImportError as e:
    print(f"❌ 无法导入 agents 模块: {e}")
    print("请确认 agents 目录存在且配置正确")
    sys.exit(1)

def get_agent_factory() -> AgentFactory:
    """获取全局AgentFactory实例，避免重复初始化"""
    global _global_agent_factory
    if _global_agent_factory is None:
        # 配置文件路径
        workflow_config = str(current_dir / "workflow.yaml")
        _global_agent_factory = AgentFactory(workflow_config_files=[workflow_config])
    return _global_agent_factory

# ============ 工具函数 ============

def count_words(text: str) -> int:
    """精确计算英文单词数"""
    if not text:
        return 0
    
    # 预处理：统一换行符和空白字符
    text = re.sub(r'\s+', ' ', text.strip())
    
    # 移除HTML标签（如果存在）
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 改进的单词匹配模式 - 同时支持中英文
    # 对于中文，每个字符算作一个词；对于英文，按空格分割单词
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
    
    # 数字也算作词
    numbers = len(re.findall(r'\b\d+(?:\.\d+)?\b', text))
    
    return chinese_chars + english_words + numbers

def clean_response(response: str) -> str:
    """清理响应，移除标签、思考过程等"""
    if not response:
        return ""
    
    # 打印原始响应用于调试
    print(f"📝 原始响应: {response[:200]}..." if len(response) > 200 else f"📝 原始响应: {response}")
    
    # 移除标签及其内容
    cleaned = re.sub(r'<.*?>', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除其他可能的XML标签
    cleaned = re.sub(r'</?(?:reasoning|analysis|thought|internal|think|反思|思考|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|字数控制|需求分析|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释).*?>', '', cleaned, flags=re.IGNORECASE)
    
    # 移除思考过程相关的内容 - 更严格的模式
    # 移除"思考"、"分析"、"推理"等关键词后的内容直到下一个标题或段落
    cleaned = re.sub(r'(?:思考|分析|推理|反思|Thought|Reasoning|Analysis)[:：]?\s*.*?(?=\n\s*\n|\Z)', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    
    # 移除以"思考过程"、"分析过程"等开头的段落
    cleaned = re.sub(r'(?:思考过程|分析过程|推理过程|Thought Process|Reasoning Process|Analysis Process)[:：]?\s*.*?(?=\n\s*\n|\Z)', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    
    # 移除"嗯，现在"、"让我"等开头的思考内容
    cleaned = re.sub(r'^(?:嗯|啊|呃|哦|嘿|好)?[，,]?\s*(?:现在|让我|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|用户要求|必须|确保|注意|记住)', '', cleaned, flags=re.MULTILINE)
    
    # 移除包含明显思考过程关键词的行（更严格的模式）
    lines = cleaned.split('\n')
    filtered_lines = []
    for line in lines:
        # 检查是否包含思考过程关键词
        thinking_keywords = r'(?:思考|分析|推理|反思|Thought|Reasoning|Analysis|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|意味着|可能|挑战|缺失|限制|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住)'
        
        # 如果行中包含明显的思考过程关键词，且不包含句号等结束符号，则跳过
        if re.search(thinking_keywords, line, re.IGNORECASE) and not re.search(r'[。！？.!?]', line):
            # 跳过这行
            print(f'🗑️ 移除纯思考行: {line}')
            continue
        # 如果行包含思考关键词但也有实际内容（有结束符号），则清理思考部分但保留内容
        elif re.search(thinking_keywords, line, re.IGNORECASE):
            # 清理思考部分但保留实际内容
            before_clean = line
            # 更积极地移除思考内容
            cleaned_line = re.sub(r'(?:思考|分析|推理|反思|Thought|Reasoning|Analysis|用户|让我|需要|现在我得|我需要|我应该|首先|其次|最后|综上|意味着|可能|挑战|缺失|限制|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住).*?[，,。！!？?]', '', line, flags=re.IGNORECASE)
            # 如果清理后内容太短，直接跳过整行
            if len(cleaned_line.strip()) < 15:
                print(f'🗑️ 移除清理后过短的行: {before_clean}')
                continue
            elif before_clean != cleaned_line:
                print(f'🧹 清理了思考内容: {before_clean} -> {cleaned_line}')
                filtered_lines.append(cleaned_line.strip())
            else:
                filtered_lines.append(line)
        else:
            filtered_lines.append(line)
    
    cleaned = '\n'.join(filtered_lines)
    
    # 移除行首的"嗯"、"啊"、"好"等语气词
    cleaned = re.sub(r'^\s*[嗯啊呃哦嘿好]\s*', '', cleaned, flags=re.MULTILINE)
    
    # 移除常见的思考过程短语（更全面的列表）
    thinking_phrases = r'(?:让我|我需要|我应该|首先|其次|最后|综上|这意味着|这可能|但可以从|这些都是|这些都|这些|这个|那个|这样|那样|因为|所以|但是|然而|不过|虽然|尽管|即使|如果|假如|假设|当|当...时|同时|此外|另外|而且|并且|或者|还是|要么|不是|没有|不会|不能|不要|不用|不可以|不允许|禁止|严禁|不得|不可|不宜|不建议|不推荐|不提倡|不鼓励|不支持|不接受|不承认|不认可|不赞同|不赞成|不支持|不接受|不承认|不认可|不赞同|不赞成|这部分应该|应该包含|需要考虑|要考虑|应该在|应该描述|应该强调|应该讨论|应该解释|需要解释|需要描述|需要强调|需要讨论|必须考虑|必须包含|必须强调|必须讨论|必须解释|用户要求|必须|确保|注意|记住|平衡进展和挑战|重复事实|要有洞察力|输出必须是中文|格式|只给出结论|包含任何)'
    cleaned = re.sub(thinking_phrases, '', cleaned, flags=re.IGNORECASE)
    
    # 移除多余的空白行
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    
    # 标准化换行符
    cleaned = re.sub(r'\r\n|\r', '\n', cleaned)
    
    # 移除行首行尾空白
    lines = [line.strip() for line in cleaned.split('\n')]
    
    # 合并多个连续空行为单个空行
    result_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                result_lines.append('')
            prev_empty = True
        else:
            result_lines.append(line)
            prev_empty = False
    
    # 移除开头和结尾的空行
    while result_lines and not result_lines[0]:
        result_lines.pop(0)
    while result_lines and not result_lines[-1]:
        result_lines.pop()
    
    # 移除多余的标点符号
    result_lines = [re.sub(r'^[，,。！!？?]+', '', line) for line in result_lines]
    result_lines = [re.sub(r'[，,。！!？?]+$', '', line) for line in result_lines]
    
    # 过滤掉太短的行（可能是清理过程中产生的无意义内容）
    result_lines = [line for line in result_lines if len(line) > 5 or re.search(r'[。！？.!?]', line)]
    
    # 如果清理后的内容过短，返回原始内容（可能是误删）
    cleaned_result = '\n'.join(result_lines)
    if len(cleaned_result) < len(response) / 4:  # 降低阈值到1/4
        print("⚠️ 清理后内容过短，可能误删了有效内容，返回原始内容")
        print(f"📊 原始长度: {len(response)}, 清理后长度: {len(cleaned_result)}")
        return response.strip()
    
    print(f"✅ 清理完成: 原始长度: {len(response)}, 清理后长度: {len(cleaned_result)}")
    print(f"📝 清理后响应: {cleaned_result[:200]}..." if len(cleaned_result) > 200 else f"📝 清理后响应: {cleaned_result}")
    return cleaned_result

def remove_markdown(text: str) -> str:
    """移除所有Markdown格式"""
    if not text:
        return ""
    
    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 移除标题标记
    text = re.sub(r'^#{1,6}\s*(.*)$', r'\1', text, flags=re.MULTILINE)
    
    # 移除粗体和斜体
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'___(.+?)___', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # 移除删除线
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    
    # 移除链接
    text = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
    
    # 移除列表标记
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # 移除引用标记
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # 移除分隔线
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # 标准化空白字符
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    text = text.strip()
    return text

# ============ 实时进度回调接口 ============

class ProgressCallback:
    """进度回调接口，用于实时显示agent输出"""
    
    def __init__(self, client_id: str = None, task_id: str = None):
        self.client_id = client_id
        self.task_id = task_id
        # 我们需要一个方式来访问WebSocket管理器
        # 这将在初始化时设置
        self.ws_manager = None
        # 添加任务取消检查器
        self._cancel_checker = None
    
    def set_task_cancel_checker(self, checker):
        """设置任务取消检查器"""
        self._cancel_checker = checker
    
    async def check_task_cancelled(self) -> bool:
        """检查任务是否被取消"""
        if self._cancel_checker and self.task_id:
            return await self._cancel_checker(self.task_id)
        return False
    
    def set_ws_manager(self, ws_manager):
        """设置WebSocket管理器"""
        self.ws_manager = ws_manager
    
    async def on_agent_start(self, agent_name: str, role_name: str, step_name: str):
        """当agent开始执行时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"🚀 [{role_name}] {step_name} - 开始执行..."
        await self._send_progress("running", 0, message, step_name)
        print(message)
    
    async def on_agent_retry(self, agent_name: str, role_name: str, step_name: str, attempt: int, max_retries: int):
        """当agent重试时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"   🔁 [{role_name}] {step_name} - 尝试 {attempt}/{max_retries}"
        await self._send_progress("running", 0, message, step_name)
        print(message)
    
    async def on_agent_success(self, agent_name: str, role_name: str, step_name: str, content: str, word_count: int):
        """当agent成功完成时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 清理内容，移除思考过程
        cleaned_content = clean_response(content)
        
        message = f"   ✅ [{role_name}] {step_name} - 成功获得 {word_count} 个字符的响应"
        await self._send_progress("running", 0, message, step_name)
        
        # 发送清理后的agent输出到客户端
        await self._send_agent_output(agent_name, role_name, step_name, cleaned_content, word_count)
        print(message)
    
    async def on_agent_error(self, agent_name: str, role_name: str, step_name: str, error: str):
        """当agent出错时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"   ❌ [{role_name}] {step_name} - 错误: {error}"
        await self._send_progress("running", 0, message, step_name)
        print(message)
    
    async def on_report_section_complete(self, section_name: str, word_count: int):
        """当报告章节完成时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"✅ {section_name} 完成: {word_count} 个单词"
        await self._send_progress("running", 0, message, section_name)
        print(message)
    
    async def on_evaluation_start(self, report_id: str):
        """当评价开始时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"🔍 严厉评价师 开始评价报告 {report_id}..."
        await self._send_progress("running", 0, message, "报告评价")
        print(message)
    
    async def on_improvement_start(self, report_id: str, attempt: int, max_attempts: int):
        """当改进开始时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"🔧 精确改进师 开始改进报告 {report_id}... 第 {attempt}/{max_attempts} 次改进尝试..."
        await self._send_progress("running", 0, message, "报告改进")
        print(message)
    
    async def on_improvement_success(self, report_id: str, word_count: int, target_word_limit: int):
        """当改进成功时调用"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        message = f"🎯 精确改进师 成功！字数完全匹配: {word_count} 个单词"
        await self._send_progress("running", 0, message, "报告改进")
        print(message)
    
    async def _send_progress(self, status: str, progress: int, message: str, current_step: str):
        """发送进度更新到WebSocket客户端"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        if self.ws_manager and self.client_id:
            update = {
                "type": "progress_update",
                "task_id": self.task_id,
                "status": status,
                "progress": progress,
                "message": message,
                "current_step": current_step,
                "timestamp": time.time()
            }
            await self.ws_manager.send_personal_message(update, self.client_id)
    
    async def _send_agent_output(self, agent_name: str, role_name: str, step_name: str, content: str, word_count: int):
        """发送agent输出到WebSocket客户端"""
        # 检查任务是否被取消
        if await self.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        if self.ws_manager and self.client_id:
            output = {
                "type": "agent_output",
                "agent_name": agent_name,
                "role_name": role_name,
                "step_name": step_name,
                "content": content,  # 发送清理后的内容
                "word_count": word_count,
                "timestamp": time.time()
            }
            try:
                # 尝试发送消息，如果失败则打印详细错误信息
                success = await self.ws_manager.send_personal_message(output, self.client_id)
                if success:
                    print(f"📤 AGENT OUTPUT [{role_name}] {step_name}: {content[:100]}...")
                else:
                    print(f"❌ 无法发送AGENT OUTPUT [{role_name}] {step_name} 到客户端 {self.client_id}")
                    # 尝试重新连接或使用备用方法
                    if self.client_id in active_connections:
                        try:
                            await active_connections[self.client_id].send_text(json.dumps(output, ensure_ascii=False))
                            print(f"✅ 通过备用方法发送消息成功")
                        except Exception as e:
                            print(f"❌ 备用方法发送消息也失败: {e}")
            except Exception as e:
                print(f"❌ 发送WebSocket消息失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 尝试备用方法
                if self.client_id in active_connections:
                    try:
                        await active_connections[self.client_id].send_text(json.dumps(output, ensure_ascii=False))
                        print(f"✅ 通过备用方法发送消息成功")
                    except Exception as e:
                        print(f"❌ 备用方法发送消息也失败: {e}")
# ============ 基于 Agent 的角色类 ============

class AgentRole:
    """基于 Agent 的角色基类"""
    
    def __init__(self, agent, data: Dict, question: str, conclusion: str, role_name: str, progress_callback: ProgressCallback = None):
        self.agent = agent
        self.data = data
        self.question = question
        self.conclusion = conclusion
        self.role_name = role_name
        self.progress_callback = progress_callback or ProgressCallback()

    async def _call_agent_with_retry(self, template_data: Dict, step_name: str) -> str:
        """带重试机制的 Agent 调用辅助函数，增强错误处理"""
        # 检查任务是否被取消
        if await self.progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        max_retries = 3
        last_exception = None
        
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, step_name)
        
        for attempt in range(1, max_retries + 1):
            try:
                # 检查任务是否被取消
                if await self.progress_callback.check_task_cancelled():
                    raise asyncio.CancelledError("任务已被用户取消")
                
                await self.progress_callback.on_agent_retry(self.agent.__class__.__name__, self.role_name, step_name, attempt, max_retries)
                
                # 更新 agent 的模板数据
                self.agent.update_template_data(template_data)
                
                # 发起对话
                response = self.agent.chat("请根据提供的数据生成内容")
                
                # 检查任务是否被取消
                if await self.progress_callback.check_task_cancelled():
                    raise asyncio.CancelledError("任务已被用户取消")
                
                if response.success and response.content:
                    content = response.content.strip()
                    # 在返回前先清理内容
                    content = clean_response(content)
                    
                    # 减少对内容长度的限制，允许更灵活的响应
                    if len(content) < 5:
                        raise ValueError(f"返回内容过短: {content}")
                    
                    word_count = len(content)
                    await self.progress_callback.on_agent_success(self.agent.__class__.__name__, self.role_name, step_name, content, word_count)
                    return content
                else:
                    error_msg = getattr(response, 'error_message', '未知错误')
                    raise Exception(f"Agent调用失败: {error_msg}")
                    
            except KeyboardInterrupt:
                print(f"\n   ⏹️ [{self.role_name}] {step_name} - 被用户中断")
                raise
            except asyncio.CancelledError:
                print(f"\n   ⏹️ [{self.role_name}] {step_name} - 被用户取消")
                raise
                
            except Exception as e:
                # 检查任务是否被取消
                if await self.progress_callback.check_task_cancelled():
                    raise asyncio.CancelledError("任务已被用户取消")
                
                await self.progress_callback.on_agent_error(self.agent.__class__.__name__, self.role_name, step_name, str(e)[:100])
                print(f"   ❌ [{self.role_name}] {step_name} - 尝试 {attempt} 失败: {str(e)[:100]}...")
                last_exception = e
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    print(f"   ⏳ 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败了
        raise last_exception

    def write(self, context: str) -> str:
        raise NotImplementedError

class ConclusionGenerator(AgentRole):
    async def write(self, context: str = "") -> str:
        print(f"🎯 [{self.role_name}] 正在生成核心结论...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "生成核心结论")
        
        # 准备模板数据
        background = self.data.get("background", [])
        bg = "\n".join([b.get("fact", "No fact provided") for b in background]) if background else "No background data available"
        
        statistics = self.data.get("statistics", [])
        stats = "\n".join([f"{s.get('metric', 'Unknown metric')}: {s.get('value', 'N/A')}" for s in statistics]) if statistics else "No statistics available"
        
        challenges_list = self.data.get("challenges", [])
        challenges = "\n".join([c.get("limitation", "No limitation specified") for c in challenges_list]) if challenges_list else "No challenges identified"
        
        experts_list = self.data.get("expert_opinions", [])
        experts = "\n".join([f"{e.get('expert', 'Unknown expert')} ({e.get('credentials', 'N/A')}): {e.get('viewpoint', 'No viewpoint provided')}" for e in experts_list]) if experts_list else "No expert opinions available"
        
        template_data = {
            "question": self.question,
            "background": bg,
            "statistics": stats,
            "challenges": challenges,
            "expert_opinions": experts
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "生成核心结论")
            conclusion = clean_response(response).strip()
            
            if conclusion and len(conclusion) >= 10:  # 降低长度要求
                # 不再截断内容，保持完整性
                conclusion = remove_markdown(conclusion)
                print(f"✅ 核心结论已生成: {conclusion[:100]}..." if len(conclusion) > 100 else f"✅ 核心结论已生成: {conclusion}")
                return conclusion
            else:
                print(f"⚠️ 生成的结论过短或格式不正确: '{conclusion[:50]}...'")
                raise ValueError("Conclusion is too short or improperly formatted")
                
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成结论时出错: {str(e)}")
            default_conclusion = "人工智能技术正在快速发展，在提高效率方面展现出巨大潜力，但在情感交流和道德判断方面仍存在局限性，需要人机协作来实现最佳效果。"
            print(f"ℹ️ 使用默认结论: {default_conclusion}")
            return default_conclusion

# 继续创建其他角色类...

class PolicyAnalyst(AgentRole):
    async def write(self, context: str) -> str:
        print(f"📝 [{self.role_name}] 正在撰写政策与监管框架部分...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "撰写政策与监管框架")
        
        facts = "\n".join([b.get("fact", "") for b in self.data.get("background", [])])
        
        template_data = {
            "question": self.question,
            "conclusion": self.conclusion,
            "context": context,
            "background_facts": facts
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "撰写政策与监管框架")
            content = clean_response(response)
            content = remove_markdown(content)
            word_count = count_words(content)
            await self.progress_callback.on_report_section_complete("政策部分", word_count)
            print(f"✅ 政策部分完成: {word_count} 个词")
            return content
        except KeyboardInterrupt:
            print(f"⏹️ [{self.role_name}] 被用户中断")
            raise
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成政策部分时出错: {str(e)}")
            return "政策框架分析因技术问题暂时不可用。"

class MarketResearcher(AgentRole):
    async def write(self, context: str) -> str:
        print(f"📊 [{self.role_name}] 正在撰写市场趋势与采纳情况...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "撰写市场趋势与采纳情况")
        
        stats = "\n".join([f"{s.get('metric', 'Unknown metric')}: {s.get('value', 'N/A')} ({s.get('source', 'N/A')})" for s in self.data.get("statistics", [])])
        
        template_data = {
            "question": self.question,
            "conclusion": self.conclusion,
            "context": context,
            "statistics": stats
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "撰写市场趋势与采纳情况")
            content = clean_response(response)
            content = remove_markdown(content)
            word_count = count_words(content)
            await self.progress_callback.on_report_section_complete("市场部分", word_count)
            print(f"✅ 市场部分完成: {word_count} 个词")
            return content
        except KeyboardInterrupt:
            print(f"⏹️ [{self.role_name}] 被用户中断")
            raise
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成市场部分时出错: {str(e)}")
            return "市场分析因技术问题暂时不可用。"

class CaseSpecialist(AgentRole):
    async def write(self, context: str) -> str:
        print(f"🏥 [{self.role_name}] 正在撰写实际案例研究...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "撰写实际案例研究")
        
        cases = [f"{c.get('location', 'Unknown location')}: {c.get('implementation', 'N/A')} → {c.get('outcome', 'N/A')} ({c.get('source', 'N/A')})" for c in self.data.get("case_studies", [])]
        
        template_data = {
            "question": self.question,
            "conclusion": self.conclusion,
            "context": context,
            "case_studies": ' | '.join(cases)
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "撰写实际案例研究")
            content = clean_response(response)
            content = remove_markdown(content)
            word_count = count_words(content)
            await self.progress_callback.on_report_section_complete("案例部分", word_count)
            print(f"✅ 案例部分完成: {word_count} 个词")
            return content
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成案例部分时出错: {str(e)}")
            return "Case studies analysis is currently unavailable due to technical issues."

class TechnicalInterpreter(AgentRole):
    async def write(self, context: str) -> str:
        print(f"🔬 [{self.role_name}] 正在解释技术原理与权衡...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "解释技术原理与权衡")
        
        methods = set()
        for c in self.data.get("case_studies", []):
            impl = c.get("implementation", "")
            if "SHAP" in impl: methods.add("SHAP")
            if "LIME" in impl: methods.add("LIME")
            if "counterfactual" in impl.lower(): methods.add("counterfactual explanations")
        methods_str = ", ".join(methods) or "SHAP, LIME, counterfactuals"
        
        acc_loss = next(
            (s.get('value', 'N/A') for s in self.data.get("statistics", []) if "accuracy loss" in s.get('metric', '').lower()),
            "8.7%"
        )
        
        template_data = {
            "question": self.question,
            "conclusion": self.conclusion,
            "context": context,
            "methods": methods_str,
            "accuracy_metrics": acc_loss
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "解释技术原理与权衡")
            content = clean_response(response)
            content = remove_markdown(content)
            word_count = count_words(content)
            await self.progress_callback.on_report_section_complete("技术部分", word_count)
            print(f"✅ 技术部分完成: {word_count} 个词")
            return content
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成技术部分时出错: {str(e)}")
            return "Technical explanation is currently unavailable due to technical issues."

class SocietalObserver(AgentRole):
    async def write(self, context: str) -> str:
        print(f"🌍 [{self.role_name}] 正在分析社会与文化维度...")
        await self.progress_callback.on_agent_start(self.agent.__class__.__name__, self.role_name, "分析社会与文化维度")
        
        challenge = next(
            (c.get("limitation", "No limitation specified") for c in self.data.get("challenges", []) if "cultural" in c.get("limitation", "").lower()),
            "Resistance in education and healthcare sectors"
        )
        
        template_data = {
            "question": self.question,
            "conclusion": self.conclusion,
            "context": context,
            "social_challenges": challenge
        }
        
        try:
            response = await self._call_agent_with_retry(template_data, "分析社会与文化维度")
            content = clean_response(response)
            content = remove_markdown(content)
            word_count = count_words(content)
            await self.progress_callback.on_report_section_complete("社会部分", word_count)
            print(f"✅ 社会部分完成: {word_count} 个词")
            return content
        except Exception as e:
            print(f"❌ [{self.role_name}] 生成社会部分时出错: {str(e)}")
            return "Social analysis is currently unavailable due to technical issues."

# ============ 评价器类 ============

class ReportEvaluator:
    """严厉的报告评价器"""
    
    def __init__(self, agent, progress_callback: ProgressCallback = None):
        self.agent = agent
        self.role_name = "严厉评价师"
        self.progress_callback = progress_callback or ProgressCallback()

    async def evaluate_report(self, report_data: Dict) -> Dict:
        """
        对报告进行严厉的多维度评价
        
        Args:
            report_data: 报告数据，包含id, question, word_limit, answer等（word_count可选）
            
        Returns:
            评价结果字典
        """
        report_id = report_data["id"]
        question = report_data["question"]
        word_limit = report_data["word_limit"]
        answer = report_data["answer"]
        
        await self.progress_callback.on_evaluation_start(report_id)
        
        # 如果有word_count字段则使用，否则计算实际字数
        reported_word_count = report_data.get("word_count", None)
        actual_word_count = count_words(answer)
        
        print(f"🔍 [{self.role_name}] 开始评价报告 {report_id}...")
        if reported_word_count is not None:
            print(f"   目标字数: {word_limit} | 声明字数: {reported_word_count} | 实际字数: {actual_word_count}")
        else:
            print(f"   目标字数: {word_limit} | 实际字数: {actual_word_count}")
        
        # 计算字数差异和匹配度
        word_diff = abs(actual_word_count - word_limit)
        word_match_rate = max(0, 100 - (word_diff / word_limit * 100))
        
        # 准备评价模板数据
        template_data = {
            "report_id": report_id,
            "question": question,
            "target_word_limit": word_limit,
            "reported_word_count": reported_word_count if reported_word_count is not None else actual_word_count,
            "actual_word_count": actual_word_count,
            "word_difference": word_diff,
            "word_match_rate": round(word_match_rate, 1),
            "report_content": answer
        }
        
        try:
            # 更新 agent 的模板数据
            self.agent.update_template_data(template_data)
            
            # 发起评价请求
            response = self.agent.chat("请对报告进行严厉评价")
            
            if response.success:
                evaluation = clean_response(response.content)
                
                print(f"✅ [{self.role_name}] 评价完成")
                print(f"   实际字数: {actual_word_count} (匹配度: {word_match_rate:.1f}%)")
                
                return {
                    "report_id": report_id,
                    "evaluation": evaluation,
                    "metrics": {
                        "target_word_limit": word_limit,
                        "reported_word_count": reported_word_count,
                        "actual_word_count": actual_word_count,
                        "word_difference": word_diff,
                        "word_match_rate": word_match_rate
                    }
                }
            else:
                print(f"❌ [{self.role_name}] 评价失败: {response.error_message}")
                return None
                
        except Exception as e:
            print(f"❌ [{self.role_name}] 评价过程出错: {str(e)}")
            return None

class ReportImprover:
    """报告改进器"""
    
    def __init__(self, agent, progress_callback: ProgressCallback = None):
        self.agent = agent
        self.role_name = "精确改进师"
        self.progress_callback = progress_callback or ProgressCallback()

    async def improve_report(self, report_data: Dict, evaluation_result: Dict) -> Dict:
        """
        基于评价结果改进报告
        
        Args:
            report_data: 原始报告数据
            evaluation_result: 评价结果
            
        Returns:
            改进后的报告数据
        """
        report_id = report_data["id"]
        question = report_data["question"]
        word_limit = report_data["word_limit"]
        original_answer = report_data["answer"]
        evaluation = evaluation_result["evaluation"]
        
        max_attempts = 3
        best_result = original_answer
        best_word_diff = abs(count_words(original_answer) - word_limit)
        
        for attempt in range(1, max_attempts + 1):
            await self.progress_callback.on_improvement_start(report_id, attempt, max_attempts)
            
            try:
                # 准备改进模板数据
                metrics = evaluation_result["metrics"]
                template_data = {
                    "report_id": report_id,
                    "question": question,
                    "target_word_limit": word_limit,
                    "original_report": original_answer,
                    "evaluation_feedback": evaluation,
                    "current_metrics": metrics,
                    # 将嵌套字典的键展开为独立参数
                    "current_actual_word_count": metrics["actual_word_count"],
                    "current_word_difference": metrics["word_difference"],
                    "current_word_match_rate": metrics["word_match_rate"]
                }
                
                print(f"🔄 [{self.role_name}] 第 {attempt}/{max_attempts} 次改进尝试...")
                
                # 更新 agent 的模板数据
                self.agent.update_template_data(template_data)
                
                # 发起改进请求
                response = self.agent.chat("请根据评价改进报告")
                
                if response.success:
                    improved_answer = clean_response(response.content)
                    improved_answer = remove_markdown(improved_answer)
                    improved_word_count = count_words(improved_answer)
                    word_diff = abs(improved_word_count - word_limit)
                    
                    print(f"   📊 改进结果: {improved_word_count} 个单词 (目标: {word_limit})")
                    
                    # 检查是否完全匹配
                    if improved_word_count == word_limit:
                        await self.progress_callback.on_improvement_success(report_id, improved_word_count, word_limit)
                        print(f"🎯 [{self.role_name}] 成功！字数完全匹配: {improved_word_count} 个单词")
                        return {
                            "id": report_id,
                            "question": question,
                            "type": report_data.get("type", ""),
                            "word_limit": word_limit,
                            "answer": improved_answer,
                            "word_count": improved_word_count,
                            "improved": True
                        }
                    elif word_diff < best_word_diff:
                        # 如果比之前的尝试更好，更新最佳结果
                        best_result = improved_answer
                        best_word_diff = word_diff
                        
                # 等待一段时间再进行下一次尝试
                if attempt < max_attempts:
                    time.sleep(2)
                        
            except Exception as e:
                print(f"❌ [{self.role_name}] 改进过程出错: {str(e)}")
                if attempt < max_attempts:
                    time.sleep(2)
        
        # 如果所有尝试都失败了，返回最佳结果
        final_word_count = count_words(best_result)
        print(f"⚠️ [{self.role_name}] 无法完全匹配字数，返回最佳结果: {final_word_count} 个单词 (目标: {word_limit})")
        return {
            "id": report_id,
            "question": question,
            "type": report_data.get("type", ""),
            "word_limit": word_limit,
            "answer": best_result,
            "word_count": final_word_count,
            "improved": False
        }

# ============ 主要工作流函数 ============

async def generate_single_report(task_data: Dict, progress_callback: ProgressCallback = None) -> Dict:
    """
    生成单个报告的工作流
    
    Args:
        task_data: 任务数据，包含id, question, type, word_limit, data等字段
        progress_callback: 进度回调对象，用于实时显示进度
        
    Returns:
        生成的报告数据
    """
    if progress_callback is None:
        progress_callback = ProgressCallback()
    
    task_id = task_data["id"]
    question = task_data["question"]
    report_type = task_data["type"]
    word_limit = task_data["word_limit"]
    data = task_data["data"]
    
    print(f"📝 开始生成报告 {task_id}: {question}")
    
    try:
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 获取Agent工厂
        factory = get_agent_factory()
        
        # 1. 生成核心结论
        print("🎯 步骤 1/7: 生成核心结论...")
        conclusion_agent = factory.create_role_agent("ollama", "conclusion_generator")
        conclusion_generator = ConclusionGenerator(conclusion_agent, data, question, "", "结论提出者", progress_callback)
        conclusion = await conclusion_generator.write()
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 2. 政策与监管框架
        print("📝 步骤 2/7: 撰写政策与监管框架...")
        policy_agent = factory.create_role_agent("ollama", "policy_analyst")
        policy_analyst = PolicyAnalyst(policy_agent, data, question, conclusion, "政策分析师", progress_callback)
        policy_section = await policy_analyst.write("")
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 3. 市场趋势与采纳情况
        print("📊 步骤 3/7: 分析市场趋势与采纳情况...")
        market_agent = factory.create_role_agent("ollama", "market_researcher")
        market_researcher = MarketResearcher(market_agent, data, question, conclusion, "市场研究员", progress_callback)
        market_section = await market_researcher.write(policy_section)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 4. 实际案例研究
        print("🏥 步骤 4/7: 研究实际案例...")
        case_agent = factory.create_role_agent("ollama", "case_specialist")
        case_specialist = CaseSpecialist(case_agent, data, question, conclusion, "案例专家", progress_callback)
        case_section = await case_specialist.write(market_section)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 5. 技术原理与权衡
        print("🔬 步骤 5/7: 解释技术原理与权衡...")
        tech_agent = factory.create_role_agent("ollama", "technical_interpreter")
        tech_interpreter = TechnicalInterpreter(tech_agent, data, question, conclusion, "技术解释者", progress_callback)
        tech_section = await tech_interpreter.write(case_section)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 6. 社会与文化维度
        print("🌍 步骤 6/7: 分析社会与文化维度...")
        social_agent = factory.create_role_agent("ollama", "societal_observer")
        social_observer = SocietalObserver(social_agent, data, question, conclusion, "社会观察员", progress_callback)
        social_section = await social_observer.write(tech_section)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 7. 组装完整报告
        print("📋 步骤 7/7: 组装完整报告...")
        full_report = f"{conclusion}\n\n{policy_section}\n\n{market_section}\n\n{case_section}\n\n{tech_section}\n\n{social_section}"
        full_report = clean_response(full_report)
        full_report = remove_markdown(full_report)
        actual_word_count = count_words(full_report)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        print(f"✅ 报告生成完成！实际字数: {actual_word_count} (目标: {word_limit})")
        
        return {
            "id": task_id,
            "question": question,
            "type": report_type,
            "word_limit": word_limit,
            "answer": full_report,
            "word_count": actual_word_count
        }
        
    except asyncio.CancelledError:
        print(f"⏹️ 报告生成任务 {task_id} 已被用户取消")
        raise
    except Exception as e:
        print(f"❌ 报告生成失败: {str(e)}")
        raise

async def evaluate_and_improve_report(report_data: Dict, progress_callback: ProgressCallback = None) -> Dict:
    """
    评价并改进报告的工作流
    
    Args:
        report_data: 报告数据
        progress_callback: 进度回调对象，用于实时显示进度
        
    Returns:
        评价和改进后的报告数据
    """
    if progress_callback is None:
        progress_callback = ProgressCallback()
    
    try:
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 获取Agent工厂
        factory = get_agent_factory()
        
        # 1. 评价报告
        print("🔍 开始评价报告...")
        evaluator_agent = factory.create_role_agent("ollama", "report_evaluator")
        evaluator = ReportEvaluator(evaluator_agent, progress_callback)
        evaluation_result = await evaluator.evaluate_report(report_data)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        if not evaluation_result:
            print("❌ 报告评价失败")
            return report_data
        
        # 2. 改进报告
        print("🔧 开始改进报告...")
        improver_agent = factory.create_role_agent("ollama", "report_improver")
        improver = ReportImprover(improver_agent, progress_callback)
        improved_report = await improver.improve_report(report_data, evaluation_result)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        return improved_report
        
    except asyncio.CancelledError:
        print(f"⏹️ 报告评价和改进任务 {report_data.get('id', 'unknown')} 已被用户取消")
        raise
    except Exception as e:
        print(f"❌ 报告评价和改进失败: {str(e)}")
        raise

async def generate_report_with_progress(task_data: Dict, client_id: str = None, task_id: str = None, cancel_checker=None) -> Dict:
    """
    带进度显示的完整报告生成工作流（生成+评价+改进）
    
    Args:
        task_data: 任务数据
        client_id: 客户端ID，用于WebSocket通信
        task_id: 任务ID
        cancel_checker: 任务取消检查器函数
    Returns:
        最终报告数据
    """
    # 创建进度回调对象
    progress_callback = ProgressCallback(client_id, task_id)
    
    # 设置任务取消检查器
    if cancel_checker:
        progress_callback.set_task_cancel_checker(cancel_checker)
    
    try:
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 1. 生成报告
        print("🚀 开始生成报告...")
        initial_report = await generate_single_report(task_data, progress_callback)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        # 2. 评价并改进报告
        print("🔍 开始评价和改进报告...")
        final_report = await evaluate_and_improve_report(initial_report, progress_callback)
        
        # 检查任务是否被取消
        if await progress_callback.check_task_cancelled():
            raise asyncio.CancelledError("任务已被用户取消")
        
        return final_report
        
    except asyncio.CancelledError:
        print(f"⏹️ 工作流任务 {task_id} 已被用户取消")
        raise
    except Exception as e:
        print(f"❌ 工作流执行失败: {str(e)}")
        raise

# 主函数（用于测试）
if __name__ == "__main__":
    print("🚀 ByteFlow 统一工作流引擎")
    print("请通过FastAPI后端调用此模块的功能")