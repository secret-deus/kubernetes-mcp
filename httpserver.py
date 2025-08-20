#!/usr/bin/env python3
"""
MCP Server for Kubernetes - HTTP版本
基于fastmcp框架重构的Kubernetes管理服务器
"""

from fastmcp import FastMCP
from kubernetes_mcp_core import setup_all_tools, check_dependencies, log_configuration
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP服务器实例
mcp = FastMCP("mcp-server-kubernetes")

if __name__ == "__main__":
    # 检查必要的依赖
    has_helm = check_dependencies()
    if not has_helm:
        exit(1)
    
    # 设置所有工具（包括Helm）
    setup_all_tools(mcp, include_helm=has_helm)
    
    # 启动MCP服务器
    logger.info("启动Kubernetes MCP服务器...")
    log_configuration()
    
    mcp.run(transport="http", host="127.0.0.1", port=6000)