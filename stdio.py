#!/usr/bin/env python3
"""
MCP Server for Kubernetes - STDIO版本
专为cherry-studio等MCP客户端设计的stdio传输版本
"""

from fastmcp import FastMCP
from kubernetes_mcp_core import setup_all_tools, check_dependencies, log_configuration
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP服务器实例 - 使用stdio传输
mcp = FastMCP("mcp-server-kubernetes")

if __name__ == "__main__":
    # 检查必要的依赖
    has_helm = check_dependencies()
    if not has_helm:
        exit(1)
    
    # 设置所有工具（包括Helm，因为stdio版本现在也支持完整功能）
    setup_all_tools(mcp, include_helm=has_helm)
    
    # 启动MCP服务器 - 使用stdio传输
    logger.info("启动Kubernetes MCP服务器 (STDIO)...")
    log_configuration()
    
    # 使用stdio传输
    mcp.run(transport="stdio")
