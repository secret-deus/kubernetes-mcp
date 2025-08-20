#!/usr/bin/env python3
"""
MCP Server for Kubernetes - 核心模块
包含所有Kubernetes和Helm操作的工具函数实现
"""

import os
import json
import yaml
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass
from fastmcp import FastMCP
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class KubernetesConfig:
    """Kubernetes配置管理"""
    kubeconfig_path: Optional[str] = None
    context: Optional[str] = None
    namespace: str = "default"
    
    def __post_init__(self):
        # 设置kubeconfig路径优先级
        if os.getenv("KUBECONFIG_YAML"):
            self._setup_from_yaml()
        elif os.getenv("KUBECONFIG_JSON"):
            self._setup_from_json()
        elif os.getenv("K8S_SERVER") and os.getenv("K8S_TOKEN"):
            self._setup_from_minimal()
        elif os.getenv("KUBECONFIG_PATH"):
            self.kubeconfig_path = os.getenv("KUBECONFIG_PATH")
        elif os.getenv("KUBECONFIG"):
            self.kubeconfig_path = os.getenv("KUBECONFIG")
        else:
            self.kubeconfig_path = os.path.expanduser("~/.kube/config")
        
        # 设置上下文和命名空间
        self.context = os.getenv("K8S_CONTEXT")
        self.namespace = os.getenv("K8S_NAMESPACE", "default")
    
    def _setup_from_yaml(self):
        """从YAML环境变量设置kubeconfig"""
        yaml_content = os.getenv("KUBECONFIG_YAML")
        if yaml_content:
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
            temp_file.write(yaml_content)
            temp_file.close()
            self.kubeconfig_path = temp_file.name
            os.environ["KUBECONFIG"] = temp_file.name
    
    def _setup_from_json(self):
        """从JSON环境变量设置kubeconfig"""
        json_content = os.getenv("KUBECONFIG_JSON")
        if json_content:
            config_dict = json.loads(json_content)
            yaml_content = yaml.dump(config_dict)
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
            temp_file.write(yaml_content)
            temp_file.close()
            self.kubeconfig_path = temp_file.name
            os.environ["KUBECONFIG"] = temp_file.name
    
    def _setup_from_minimal(self):
        """从最小配置环境变量设置kubeconfig"""
        server = os.getenv("K8S_SERVER")
        token = os.getenv("K8S_TOKEN")
        skip_tls = os.getenv("K8S_SKIP_TLS_VERIFY", "false").lower() == "true"
        
        if server and token:
            config = {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{
                    "name": "env-cluster",
                    "cluster": {
                        "server": server,
                        "insecure-skip-tls-verify": skip_tls
                    }
                }],
                "users": [{
                    "name": "env-user",
                    "user": {
                        "token": token
                    }
                }],
                "contexts": [{
                    "name": "env-context",
                    "context": {
                        "cluster": "env-cluster",
                        "user": "env-user"
                    }
                }],
                "current-context": "env-context"
            }
            
            yaml_content = yaml.dump(config)
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
            temp_file.write(yaml_content)
            temp_file.close()
            self.kubeconfig_path = temp_file.name
            os.environ["KUBECONFIG"] = temp_file.name

# 全局配置实例
k8s_config = KubernetesConfig()

def run_kubectl_command(args: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """执行kubectl命令的通用函数"""
    cmd = ["kubectl"] + args
    
    # 添加kubeconfig和context参数
    if k8s_config.kubeconfig_path:
        cmd.extend(["--kubeconfig", k8s_config.kubeconfig_path])
    
    if k8s_config.context:
        cmd.extend(["--context", k8s_config.context])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True,
            timeout=60
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"kubectl命令执行失败: {' '.join(cmd)}")
        logger.error(f"错误输出: {e.stderr}")
        raise Exception(f"kubectl命令执行失败: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise Exception("kubectl命令执行超时")

def run_helm_command(args: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """执行helm命令的通用函数"""
    cmd = ["helm"] + args
    
    # 添加kubeconfig参数
    if k8s_config.kubeconfig_path:
        cmd.extend(["--kubeconfig", k8s_config.kubeconfig_path])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True,
            timeout=120  # Helm操作可能需要更长时间
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"helm命令执行失败: {' '.join(cmd)}")
        logger.error(f"错误输出: {e.stderr}")
        raise Exception(f"helm命令执行失败: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise Exception("helm命令执行超时")

def mask_secrets_data(data: Any) -> Any:
    """递归地屏蔽secrets数据中的敏感信息"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "data" and isinstance(value, dict):
                # 屏蔽data字段中的所有值
                result[key] = {k: "***" for k in value.keys()}
            else:
                result[key] = mask_secrets_data(value)
        return result
    elif isinstance(data, list):
        return [mask_secrets_data(item) for item in data]
    else:
        return data

def setup_kubernetes_tools(mcp: FastMCP):
    """设置所有Kubernetes工具函数"""
    
    @mcp.tool(
        name='ping',
        description='验证与Kubernetes集群的连接是否正常'
    )
    def ping() -> str:
        """验证连接"""
        try:
            result = run_kubectl_command(["cluster-info"])
            return json.dumps({
                "status": "success",
                "message": "连接正常",
                "cluster_info": result.stdout
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"连接失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_get',
        description='获取或列出Kubernetes资源'
    )
    def kubectl_get(
        resource_type: str,
        name: str = "",
        namespace: str = "",
        output: str = "json",
        all_namespaces: bool = False,
        label_selector: str = "",
        field_selector: str = "",
        sort_by: str = ""
    ) -> str:
        """获取Kubernetes资源"""
        try:
            args = ["get", resource_type.lower()]
            
            # 添加资源名称
            if name:
                args.append(name)
            
            # 处理命名空间
            if all_namespaces:
                args.append("--all-namespaces")
            elif namespace:
                args.extend(["-n", namespace])
            elif not namespace and resource_type.lower() not in ["nodes", "node", "namespaces", "namespace", "persistentvolumes", "pv", "storageclasses", "sc"]:
                args.extend(["-n", k8s_config.namespace])
            
            # 添加选择器
            if label_selector:
                args.extend(["-l", label_selector])
            if field_selector:
                args.extend(["--field-selector", field_selector])
            
            # 添加排序
            if sort_by:
                args.extend(["--sort-by", f".{sort_by}"])
            elif resource_type.lower() == "events":
                args.extend(["--sort-by", ".lastTimestamp"])
            
            # 设置输出格式
            if output == "json":
                args.extend(["-o", "json"])
            elif output == "yaml":
                args.extend(["-o", "yaml"])
            elif output == "wide":
                args.extend(["-o", "wide"])
            elif output == "name":
                args.extend(["-o", "name"])
            
            result = run_kubectl_command(args)
            
            # 处理secrets数据屏蔽
            if resource_type.lower() in ["secrets", "secret"] and os.getenv("MASK_SECRETS", "true").lower() != "false":
                if output == "json":
                    try:
                        data = json.loads(result.stdout)
                        masked_data = mask_secrets_data(data)
                        return json.dumps(masked_data, ensure_ascii=False, indent=2)
                    except json.JSONDecodeError:
                        pass
            
            return result.stdout
            
        except Exception as e:
            return json.dumps({
                "error": f"获取资源失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_describe',
        description='描述Kubernetes资源的详细信息'
    )
    def kubectl_describe(
        resource_type: str,
        name: str,
        namespace: str = ""
    ) -> str:
        """描述Kubernetes资源"""
        try:
            args = ["describe", resource_type.lower(), name]
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            elif resource_type.lower() not in ["nodes", "node", "namespaces", "namespace", "persistentvolumes", "pv"]:
                args.extend(["-n", k8s_config.namespace])
            
            result = run_kubectl_command(args)
            return result.stdout
            
        except Exception as e:
            return json.dumps({
                "error": f"描述资源失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_apply',
        description='应用Kubernetes YAML清单'
    )
    def kubectl_apply(
        manifest: str = "",
        filename: str = "",
        namespace: str = "",
        dry_run: bool = False,
        force: bool = False
    ) -> str:
        """应用Kubernetes清单"""
        try:
            args = ["apply"]
            
            if manifest:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                    temp_file.write(manifest)
                    temp_filename = temp_file.name
                
                args.extend(["-f", temp_filename])
                
                try:
                    # 添加其他参数
                    if namespace:
                        args.extend(["-n", namespace])
                    
                    if dry_run:
                        args.append("--dry-run=client")
                    
                    if force:
                        args.append("--force")
                    
                    result = run_kubectl_command(args)
                    return json.dumps({
                        "status": "success",
                        "message": "应用成功",
                        "output": result.stdout
                    }, ensure_ascii=False, indent=2)
                finally:
                    # 清理临时文件
                    os.unlink(temp_filename)
            
            elif filename:
                args.extend(["-f", filename])
                
                if namespace:
                    args.extend(["-n", namespace])
                
                if dry_run:
                    args.append("--dry-run=client")
                
                if force:
                    args.append("--force")
                
                result = run_kubectl_command(args)
                return json.dumps({
                    "status": "success",
                    "message": "应用成功",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            
            else:
                return json.dumps({
                    "error": "必须提供manifest或filename参数",
                    "status": "error"
                }, ensure_ascii=False, indent=2)
                
        except Exception as e:
            return json.dumps({
                "error": f"应用清单失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_delete',
        description='删除Kubernetes资源'
    )
    def kubectl_delete(
        resource_type: str = "",
        name: str = "",
        namespace: str = "",
        label_selector: str = "",
        manifest: str = "",
        filename: str = "",
        all_namespaces: bool = False,
        force: bool = False,
        grace_period_seconds: int = -1
    ) -> str:
        """删除Kubernetes资源"""
        try:
            args = ["delete"]
            
            if manifest:
                # 使用清单删除
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                    temp_file.write(manifest)
                    temp_filename = temp_file.name
                
                args.extend(["-f", temp_filename])
                
                try:
                    if namespace:
                        args.extend(["-n", namespace])
                    
                    if force:
                        args.append("--force")
                    
                    if grace_period_seconds >= 0:
                        args.extend(["--grace-period", str(grace_period_seconds)])
                    
                    result = run_kubectl_command(args)
                    return json.dumps({
                        "status": "success",
                        "message": "删除成功",
                        "output": result.stdout
                    }, ensure_ascii=False, indent=2)
                finally:
                    os.unlink(temp_filename)
            
            elif filename:
                args.extend(["-f", filename])
                
                if namespace:
                    args.extend(["-n", namespace])
                
                if force:
                    args.append("--force")
                
                if grace_period_seconds >= 0:
                    args.extend(["--grace-period", str(grace_period_seconds)])
                
                result = run_kubectl_command(args)
                return json.dumps({
                    "status": "success",
                    "message": "删除成功",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            
            elif resource_type:
                args.append(resource_type.lower())
                
                if name:
                    args.append(name)
                
                if all_namespaces:
                    args.append("--all-namespaces")
                elif namespace:
                    args.extend(["-n", namespace])
                elif resource_type.lower() not in ["nodes", "node", "namespaces", "namespace"]:
                    args.extend(["-n", k8s_config.namespace])
                
                if label_selector:
                    args.extend(["-l", label_selector])
                
                if force:
                    args.append("--force")
                
                if grace_period_seconds >= 0:
                    args.extend(["--grace-period", str(grace_period_seconds)])
                
                result = run_kubectl_command(args)
                return json.dumps({
                    "status": "success",
                    "message": "删除成功",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            
            else:
                return json.dumps({
                    "error": "必须提供resource_type、manifest或filename参数",
                    "status": "error"
                }, ensure_ascii=False, indent=2)
                
        except Exception as e:
            return json.dumps({
                "error": f"删除资源失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_logs',
        description='获取Kubernetes资源的日志'
    )
    def kubectl_logs(
        resource_type: str,
        name: str,
        namespace: str,
        container: str = "",
        tail: int = -1,
        since: str = "",
        since_time: str = "",
        timestamps: bool = False,
        previous: bool = False,
        follow: bool = False,
        label_selector: str = ""
    ) -> str:
        """获取Kubernetes资源日志"""
        try:
            args = ["logs"]
            
            # 构建资源标识
            if resource_type.lower() in ["pod", "pods"]:
                args.append(name)
            else:
                args.append(f"{resource_type.lower()}/{name}")
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.extend(["-n", k8s_config.namespace])
            
            # 添加容器名称
            if container:
                args.extend(["-c", container])
            
            # 添加其他参数
            if tail > 0:
                args.extend(["--tail", str(tail)])
            
            if since:
                args.extend(["--since", since])
            
            if since_time:
                args.extend(["--since-time", since_time])
            
            if timestamps:
                args.append("--timestamps")
            
            if previous:
                args.append("--previous")
            
            if follow:
                args.append("--follow")
            
            if label_selector:
                args.extend(["-l", label_selector])
            
            result = run_kubectl_command(args)
            return result.stdout
            
        except Exception as e:
            return json.dumps({
                "error": f"获取日志失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_context',
        description='管理Kubernetes上下文'
    )
    def kubectl_context(
        operation: str = "list",
        name: str = "",
        show_current: bool = True
    ) -> str:
        """管理Kubernetes上下文"""
        try:
            if operation == "list":
                args = ["config", "get-contexts"]
                if show_current:
                    args.append("--output=name")
            elif operation == "get":
                args = ["config", "current-context"]
            elif operation == "set" and name:
                args = ["config", "use-context", name]
            else:
                return json.dumps({
                    "error": "无效的操作或缺少参数",
                    "status": "error"
                }, ensure_ascii=False, indent=2)
            
            result = run_kubectl_command(args)
            
            if operation == "set":
                return json.dumps({
                    "status": "success",
                    "message": f"上下文已切换到: {name}",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            else:
                return result.stdout
                
        except Exception as e:
            return json.dumps({
                "error": f"上下文操作失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_scale',
        description='扩缩容Kubernetes资源'
    )
    def kubectl_scale(
        name: str,
        replicas: int,
        resource_type: str = "deployment",
        namespace: str = ""
    ) -> str:
        """扩缩容Kubernetes资源"""
        try:
            args = ["scale", f"{resource_type.lower()}/{name}", f"--replicas={replicas}"]
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.extend(["-n", k8s_config.namespace])
            
            result = run_kubectl_command(args)
            return json.dumps({
                "status": "success",
                "message": f"成功将{resource_type} {name}扩缩容到{replicas}个副本",
                "output": result.stdout
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"扩缩容失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_patch',
        description='更新Kubernetes资源的字段'
    )
    def kubectl_patch(
        resource_type: str,
        name: str,
        patch_data: dict,
        namespace: str = "",
        patch_type: str = "strategic",
        dry_run: bool = False
    ) -> str:
        """更新Kubernetes资源字段"""
        try:
            args = ["patch", resource_type.lower(), name]
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.extend(["-n", k8s_config.namespace])
            
            # 添加补丁类型
            if patch_type == "merge":
                args.extend(["--type", "merge"])
            elif patch_type == "json":
                args.extend(["--type", "json"])
            
            # 添加补丁数据
            patch_json = json.dumps(patch_data)
            args.extend(["-p", patch_json])
            
            if dry_run:
                args.append("--dry-run=client")
            
            result = run_kubectl_command(args)
            return json.dumps({
                "status": "success",
                "message": f"成功更新{resource_type} {name}",
                "output": result.stdout
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"更新资源失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_rollout',
        description='管理Kubernetes资源的滚动更新'
    )
    def kubectl_rollout(
        sub_command: str,
        resource_type: str,
        name: str,
        namespace: str = "",
        revision: int = -1,
        timeout: str = ""
    ) -> str:
        """管理滚动更新"""
        try:
            args = ["rollout", sub_command, f"{resource_type.lower()}/{name}"]
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.extend(["-n", k8s_config.namespace])
            
            # 添加版本号（用于undo操作）
            if sub_command == "undo" and revision > 0:
                args.extend(["--to-revision", str(revision)])
            
            # 添加超时时间
            if timeout:
                args.extend(["--timeout", timeout])
            
            result = run_kubectl_command(args)
            return json.dumps({
                "status": "success",
                "message": f"滚动更新操作成功: {sub_command}",
                "output": result.stdout
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"滚动更新操作失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='kubectl_exec',
        description='在Pod中执行命令'
    )
    def kubectl_exec(
        name: str,
        command: Union[str, List[str]],
        namespace: str = "",
        container: str = "",
        stdin: bool = False,
        tty: bool = False
    ) -> str:
        """在Pod中执行命令"""
        try:
            args = ["exec"]
            
            if stdin:
                args.append("-i")
            if tty:
                args.append("-t")
            
            args.append(name)
            
            # 添加命名空间
            if namespace:
                args.extend(["-n", namespace])
            else:
                args.extend(["-n", k8s_config.namespace])
            
            # 添加容器名称
            if container:
                args.extend(["-c", container])
            
            # 添加命令分隔符
            args.append("--")
            
            # 添加要执行的命令
            if isinstance(command, str):
                args.extend(command.split())
            else:
                args.extend(command)
            
            result = run_kubectl_command(args)
            return json.dumps({
                "status": "success",
                "output": result.stdout,
                "stderr": result.stderr if result.stderr else ""
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"执行命令失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='health_check',
        description='健康检查端点'
    )
    def health_check() -> str:
        """健康检查"""
        try:
            # 简单的连接测试
            result = run_kubectl_command(["version", "--client"])
            return json.dumps({
                "status": "healthy",
                "message": "MCP服务器运行正常",
                "kubectl_version": result.stdout.strip()
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "unhealthy",
                "message": f"健康检查失败: {str(e)}"
            }, ensure_ascii=False, indent=2)

def setup_helm_tools(mcp: FastMCP):
    """设置所有Helm工具函数"""
    
    @mcp.tool(
        name='helm_install',
        description='安装Helm Chart'
    )
    def helm_install(
        name: str,
        chart: str,
        repo: str = "",
        namespace: str = "",
        values: dict = None,
        create_namespace: bool = True
    ) -> str:
        """安装Helm Chart"""
        try:
            # 如果提供了仓库，先添加仓库
            if repo:
                repo_name = chart.split("/")[0] if "/" in chart else "temp-repo"
                try:
                    run_helm_command(["repo", "add", repo_name, repo])
                    run_helm_command(["repo", "update"])
                except Exception as e:
                    logger.warning(f"添加Helm仓库失败，继续安装: {e}")
            
            args = ["install", name, chart]
            
            # 添加命名空间
            target_namespace = namespace or k8s_config.namespace
            args.extend(["--namespace", target_namespace])
            
            if create_namespace:
                args.append("--create-namespace")
            
            # 处理values
            values_file = None
            if values:
                values_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                yaml.dump(values, values_file)
                values_file.close()
                args.extend(["-f", values_file.name])
            
            try:
                result = run_helm_command(args)
                return json.dumps({
                    "status": "success",
                    "message": f"成功安装Helm Chart: {name}",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            finally:
                if values_file:
                    os.unlink(values_file.name)
                    
        except Exception as e:
            return json.dumps({
                "error": f"安装Helm Chart失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='helm_upgrade',
        description='升级Helm Release'
    )
    def helm_upgrade(
        name: str,
        chart: str,
        repo: str = "",
        namespace: str = "",
        values: dict = None
    ) -> str:
        """升级Helm Release"""
        try:
            # 如果提供了仓库，先添加仓库
            if repo:
                repo_name = chart.split("/")[0] if "/" in chart else "temp-repo"
                try:
                    run_helm_command(["repo", "add", repo_name, repo])
                    run_helm_command(["repo", "update"])
                except Exception as e:
                    logger.warning(f"添加Helm仓库失败，继续升级: {e}")
            
            args = ["upgrade", name, chart]
            
            # 添加命名空间
            target_namespace = namespace or k8s_config.namespace
            args.extend(["--namespace", target_namespace])
            
            # 处理values
            values_file = None
            if values:
                values_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                yaml.dump(values, values_file)
                values_file.close()
                args.extend(["-f", values_file.name])
            
            try:
                result = run_helm_command(args)
                return json.dumps({
                    "status": "success",
                    "message": f"成功升级Helm Release: {name}",
                    "output": result.stdout
                }, ensure_ascii=False, indent=2)
            finally:
                if values_file:
                    os.unlink(values_file.name)
                    
        except Exception as e:
            return json.dumps({
                "error": f"升级Helm Release失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='helm_uninstall',
        description='卸载Helm Release'
    )
    def helm_uninstall(
        name: str,
        namespace: str = ""
    ) -> str:
        """卸载Helm Release"""
        try:
            args = ["uninstall", name]
            
            # 添加命名空间
            target_namespace = namespace or k8s_config.namespace
            args.extend(["--namespace", target_namespace])
            
            result = run_helm_command(args)
            return json.dumps({
                "status": "success",
                "message": f"成功卸载Helm Release: {name}",
                "output": result.stdout
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"卸载Helm Release失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

    @mcp.tool(
        name='helm_list',
        description='列出Helm Releases'
    )
    def helm_list(
        namespace: str = "",
        all_namespaces: bool = False
    ) -> str:
        """列出Helm Releases"""
        try:
            args = ["list", "--output", "json"]
            
            if all_namespaces:
                args.append("--all-namespaces")
            elif namespace:
                args.extend(["--namespace", namespace])
            else:
                args.extend(["--namespace", k8s_config.namespace])
            
            result = run_helm_command(args)
            return result.stdout
            
        except Exception as e:
            return json.dumps({
                "error": f"列出Helm Releases失败: {str(e)}",
                "status": "error"
            }, ensure_ascii=False, indent=2)

def setup_resources_and_prompts(mcp: FastMCP):
    """设置资源和提示符"""
    
    @mcp.resource(
        uri="k8s://cluster/info",
        name="cluster_info",
        description="获取Kubernetes集群信息"
    )
    def get_cluster_info() -> str:
        """获取集群信息"""
        try:
            result = run_kubectl_command(["cluster-info"])
            return result.stdout
        except Exception as e:
            return f"获取集群信息失败: {str(e)}"

    @mcp.resource(
        uri="k8s://contexts",
        name="contexts",
        description="获取可用的Kubernetes上下文"
    )
    def get_contexts() -> str:
        """获取上下文列表"""
        try:
            result = run_kubectl_command(["config", "get-contexts", "-o", "name"])
            return result.stdout
        except Exception as e:
            return f"获取上下文失败: {str(e)}"

    @mcp.prompt(
        name='k8s_diagnose',
        description='Kubernetes故障诊断助手'
    )
    def k8s_diagnose(keyword: str, namespace: str = "") -> str:
        """Kubernetes故障诊断提示符"""
        target_namespace = namespace or k8s_config.namespace
        
        return f"""
# Kubernetes故障诊断流程

## 目标
诊断与关键字 "{keyword}" 相关的Kubernetes问题

## 诊断步骤

### 1. 基础信息收集
- 检查集群状态: `kubectl cluster-info`
- 检查节点状态: `kubectl get nodes`
- 检查命名空间 "{target_namespace}" 中的资源

### 2. 资源状态检查
- 检查Pods: `kubectl get pods -n {target_namespace} | grep {keyword}`
- 检查Services: `kubectl get services -n {target_namespace} | grep {keyword}`
- 检查Deployments: `kubectl get deployments -n {target_namespace} | grep {keyword}`

### 3. 详细诊断
- 描述相关资源: `kubectl describe pod <pod-name> -n {target_namespace}`
- 检查日志: `kubectl logs <pod-name> -n {target_namespace}`
- 检查事件: `kubectl get events -n {target_namespace} --sort-by='.lastTimestamp'`

### 4. 网络诊断
- 检查Service端点: `kubectl get endpoints -n {target_namespace}`
- 检查网络策略: `kubectl get networkpolicies -n {target_namespace}`

### 5. 资源使用情况
- 检查资源使用: `kubectl top pods -n {target_namespace}`
- 检查资源限制: 查看Pod的resources配置

## 常见问题排查
1. **Pod无法启动**: 检查镜像、资源限制、存储卷
2. **服务无法访问**: 检查Service配置、端点、网络策略
3. **性能问题**: 检查资源使用率、限制配置
4. **配置问题**: 检查ConfigMap、Secret配置

请按照以上步骤系统性地诊断问题。
"""

def check_dependencies():
    """检查必要的依赖"""
    try:
        subprocess.run(["kubectl", "version", "--client"], 
                      capture_output=True, check=True)
        logger.info("kubectl检查通过")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("kubectl未安装或不在PATH中")
        return False
    
    try:
        subprocess.run(["helm", "version"], 
                      capture_output=True, check=True)
        logger.info("Helm已安装")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Helm未安装，Helm相关功能将不可用")
        return False

def setup_all_tools(mcp: FastMCP, include_helm: bool = True):
    """设置所有工具、资源和提示符"""
    setup_kubernetes_tools(mcp)
    if include_helm:
        setup_helm_tools(mcp)
    setup_resources_and_prompts(mcp)

def log_configuration():
    """记录配置信息"""
    logger.info("Kubernetes MCP服务器配置信息:")
    logger.info(f"  - kubeconfig路径: {k8s_config.kubeconfig_path}")
    logger.info(f"  - 默认命名空间: {k8s_config.namespace}")
    logger.info(f"  - 上下文: {k8s_config.context or '默认'}")
