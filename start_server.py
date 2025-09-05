#!/usr/bin/env python3
"""
ByteFlow应用启动脚本
"""
import uvicorn
import sys
from pathlib import Path

def main():
    try:
        print("🚀 启动 ByteFlow 智能报告生成系统...")
        print("=" * 60)
        
        # 设置工作目录
        work_dir = Path(__file__).parent
        print(f"📂 工作目录: {work_dir}")
        
        # 启动应用
        uvicorn.run(
            "main:app",
            host="192.168.31.158",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n👋 ByteFlow应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()