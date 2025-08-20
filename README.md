# MCP Kubernetes Server

一个基于 [FastMCP](https://github.com/jlowin/fastmcp) 框架构建的 Kubernetes 管理服务器，提供完整的 Kubernetes 集群管理功能。

## 🚀 项目特性

- **完整的 Kubernetes 管理**: 支持 kubectl 的所有核心操作
- **Helm 集成**: 提供 Helm Chart 的安装、升级、卸载功能
- **多种传输方式**: 支持 HTTP 和 STDIO 两种传输协议
- **灵活的配置**: 支持多种 kubeconfig 配置方式
- **安全性**: 自动屏蔽 Secret 敏感数据
- **故障诊断**: 内置 Kubernetes 故障诊断助手
- **健康检查**: 提供服务健康状态监控

## 📁 项目结构

```
MCP/
├── kubernetes_mcp_core.py      # 核心模块：包含所有工具函数实现
├── httpserver.py               # HTTP 传输版本的 MCP 服务器
├── stdio.py                    # STDIO 传输版本的 MCP 服务器
├── simple_mcp_test.py          # 简单的测试客户端
├── pyproject.toml              # 项目配置和依赖管理
├── VERSION                     # 版本信息
└── README.md                   # 项目文档
```

### 核心架构

- **`kubernetes_mcp_core.py`**: 核心模块，包含所有 Kubernetes 和 Helm 操作的实现
- **`httpserver.py`**: HTTP 传输模式的服务器入口
- **`stdio.py`**: STDIO 传输模式的服务器入口（现在支持完整功能）

## 🛠️ 安装与配置

### 环境要求

- Python 3.10+
- kubectl (必需)
- helm (可选，用于 Helm 功能)
- 有效的 Kubernetes 集群访问权限

### 安装依赖

项目使用 `uv` 作为包管理器：

```bash
# 安装依赖
uv sync

# 开发环境依赖
uv sync --dev
```

### Kubernetes 配置

服务器支持多种 kubeconfig 配置方式，按优先级排序：

1. **YAML 环境变量**:
   ```bash
   export KUBECONFIG_YAML="$(cat ~/.kube/config)"
   ```

2. **JSON 环境变量**:
   ```bash
   export KUBECONFIG_JSON='{"apiVersion":"v1","kind":"Config",...}'
   ```

3. **最小配置**:
   ```bash
   export K8S_SERVER="https://your-k8s-api-server"
   export K8S_TOKEN="your-service-account-token"
   export K8S_SKIP_TLS_VERIFY="true"  # 可选
   ```

4. **标准路径**:
   ```bash
   export KUBECONFIG="/path/to/your/kubeconfig"
   # 或使用默认路径 ~/.kube/config
   ```

### 其他配置选项

```bash
# 设置默认上下文
export K8S_CONTEXT="your-context-name"

# 设置默认命名空间
export K8S_NAMESPACE="your-namespace"

# 控制 Secret 数据屏蔽（默认启用）
export MASK_SECRETS="true"
```

## 🚀 运行服务器

### HTTP 传输模式

适用于需要 HTTP API 访问的场景：

```bash
uv run httpserver.py
```

服务器将在 `http://127.0.0.1:6000` 启动。

### STDIO 传输模式

适用于 MCP 客户端（如 Cherry Studio）：

```bash
uv run stdio.py
```

## 🔧 可用工具

### 核心 Kubernetes 操作

- **`ping`**: 验证与 Kubernetes 集群的连接
- **`kubectl_get`**: 获取或列出 Kubernetes 资源
- **`kubectl_describe`**: 描述资源的详细信息
- **`kubectl_apply`**: 应用 YAML 清单
- **`kubectl_delete`**: 删除 Kubernetes 资源
- **`kubectl_logs`**: 获取资源日志
- **`kubectl_context`**: 管理 Kubernetes 上下文
- **`kubectl_scale`**: 扩缩容资源
- **`kubectl_patch`**: 更新资源字段
- **`kubectl_rollout`**: 管理滚动更新
- **`kubectl_exec`**: 在 Pod 中执行命令

### Helm 操作

- **`helm_install`**: 安装 Helm Chart
- **`helm_upgrade`**: 升级 Helm Release
- **`helm_uninstall`**: 卸载 Helm Release
- **`helm_list`**: 列出 Helm Releases

### 辅助功能

- **`health_check`**: 健康检查端点

## 📚 资源和提示符

### 资源

- **`k8s://cluster/info`**: 获取集群信息
- **`k8s://contexts`**: 获取可用上下文

### 提示符

- **`k8s_diagnose`**: Kubernetes 故障诊断助手

## 🧪 测试

使用提供的测试客户端验证服务器功能：

```bash
# 确保 HTTP 服务器正在运行
uv run simple_mcp_test.py
```

## 🏗️ 架构设计

### 模块化架构

项目采用模块化设计，将核心功能与传输层分离：

- **核心模块** (`kubernetes_mcp_core.py`): 包含所有业务逻辑和工具实现
- **传输层** (`httpserver.py`, `stdio.py`): 负责不同的通信协议

### 优势

1. **代码复用**: 两种传输模式共享相同的核心功能
2. **易于维护**: 业务逻辑集中在核心模块中
3. **功能一致**: STDIO 和 HTTP 版本提供完全相同的功能
4. **扩展性**: 可以轻松添加新的传输模式

## 📖 使用示例

### 基本操作示例

```python
from fastmcp import Client
import asyncio

async def example():
    async with Client("http://127.0.0.1:6000/mcp") as client:
        # 检查连接
        result = await client.call_tool("ping")
        print(result)
        
        # 获取所有 Pod
        pods = await client.call_tool("kubectl_get", {
            "resource_type": "pods",
            "all_namespaces": True
        })
        print(pods)
        
        # 获取特定 Deployment 的日志
        logs = await client.call_tool("kubectl_logs", {
            "resource_type": "deployment",
            "name": "my-app",
            "namespace": "default",
            "tail": 100
        })
        print(logs)

asyncio.run(example())
```

### 使用 Helm

```python
# 安装 Chart
await client.call_tool("helm_install", {
    "name": "my-release",
    "chart": "stable/nginx",
    "namespace": "default",
    "values": {
        "replicaCount": 3,
        "service": {
            "type": "LoadBalancer"
        }
    }
})
```

## 🔒 安全特性

- **Secret 数据屏蔽**: 自动屏蔽 Kubernetes Secret 中的敏感数据
- **超时控制**: 所有 kubectl 和 helm 命令都有超时限制
- **错误处理**: 完善的错误处理和日志记录

## 🐛 故障排除

### 常见问题

1. **kubectl 未找到**:
   ```bash
   # 确保 kubectl 已安装并在 PATH 中
   kubectl version --client
   ```

2. **连接失败**:
   ```bash
   # 检查 kubeconfig 配置
   kubectl cluster-info
   ```

3. **权限问题**:
   ```bash
   # 检查当前用户权限
   kubectl auth can-i --list
   ```

### 日志调试

服务器启动时会显示配置信息：

```
启动Kubernetes MCP服务器...
配置信息:
  - kubeconfig路径: /home/user/.kube/config
  - 默认命名空间: default
  - 上下文: my-context
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 🔗 相关链接

- [FastMCP 框架](https://github.com/jlowin/fastmcp)
- [Kubernetes 官方文档](https://kubernetes.io/docs/)
- [Helm 官方文档](https://helm.sh/docs/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
