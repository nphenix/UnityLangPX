#!/usr/bin/env python3
"""
配置迁移脚本

将现有的分散配置文件迁移到新的统一配置系统。
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def load_existing_config() -> Dict[str, Any]:
    """加载现有配置"""
    config = {}
    
    # 1. 加载默认TOML配置
    default_config_path = project_root / "config" / "default.toml"
    if default_config_path.exists():
        try:
            import toml
            with open(default_config_path, 'r', encoding='utf-8') as f:
                config.update(toml.load(f))
            print(f"已加载默认配置: {default_config_path}")
        except Exception as e:
            print(f"加载默认配置失败: {e}")
    
    # 2. 加载桌面配置（如果存在）
    desktop_config_path = project_root / "config" / "desktop_config.json"
    if desktop_config_path.exists():
        try:
            with open(desktop_config_path, 'r', encoding='utf-8') as f:
                desktop_config = json.load(f)
            
            # 映射桌面配置到新结构
            if 'translation' in desktop_config:
                config.setdefault('translation', {}).update(desktop_config['translation'])
            
            if 'model' in desktop_config:
                config.setdefault('model', {}).update(desktop_config['model'])
                if 'ollama' in desktop_config['model']:
                    config.setdefault('model_ollama', {}).update(desktop_config['model']['ollama'])
                if 'openai' in desktop_config['model']:
                    config.setdefault('model_openai', {}).update(desktop_config['model']['openai'])
            
            print(f"已加载桌面配置: {desktop_config_path}")
        except Exception as e:
            print(f"加载桌面配置失败: {e}")
    
    # 3. 加载MCP配置（如果存在）
    mcp_config_paths = [
        project_root / "config" / "dify_mcp_config.json",
        project_root / "config" / "dify_mcp_docker_fix.json",
        project_root / "config" / "dify_mcp_dynamic_config.json"
    ]
    
    for mcp_path in mcp_config_paths:
        if mcp_path.exists():
            try:
                with open(mcp_path, 'r', encoding='utf-8') as f:
                    mcp_config = json.load(f)
                
                # 映射MCP配置到新结构
                if 'server' in mcp_config:
                    config.setdefault('mcp', {}).update(mcp_config['server'])
                
                if 'tools' in mcp_config:
                    config.setdefault('mcp_tools', {}).update(mcp_config['tools'])
                
                if 'security' in mcp_config:
                    config.setdefault('mcp_security', {}).update(mcp_config['security'])
                
                if 'cache' in mcp_config:
                    config.setdefault('mcp_cache', {}).update(mcp_config['cache'])
                
                print(f"已加载MCP配置: {mcp_path}")
            except Exception as e:
                print(f"加载MCP配置失败 {mcp_path}: {e}")
    
    return config

def migrate_config_to_unified(existing_config: Dict[str, Any]) -> Dict[str, Any]:
    """将现有配置迁移到统一配置格式"""
    unified_config = {}
    
    # 项目基础配置
    unified_config['project'] = {
        'name': existing_config.get('project', {}).get('name', 'UnityLangPX'),
        'version': existing_config.get('project', {}).get('version', '1.0.0'),
        'description': existing_config.get('project', {}).get('description', '基于大模型技术的多平台翻译解决方案')
    }
    
    # 模型配置
    unified_config['model'] = {
        'provider': existing_config.get('model', {}).get('provider', 'ollama'),
        'default_provider': existing_config.get('model', {}).get('default_provider', 'ollama')
    }
    
    # Ollama配置
    unified_config['model_ollama'] = existing_config.get('model_ollama', {
        'host': 'http://localhost:11434',
        'model': 'SimonPu/Hunyuan-MT-Chimera-7B:Q8',
        'timeout': 60
    })
    
    # OpenAI配置
    unified_config['model_openai'] = existing_config.get('model_openai', {
        'base_url': 'https://api.openai.com/v1',
        'api_key': '',
        'model': 'gpt-3.5-turbo',
        'max_tokens': 4000,
        'timeout': 60
    })
    
    # 翻译配置
    unified_config['translation'] = existing_config.get('translation', {
        'temperature': 0.1,
        'max_tokens': 4000,
        'chunk_size': 1000,
        'overlap': 100,
        'source_language': 'en',
        'target_language': 'zh'
    })
    
    # CLI配置
    unified_config['cli'] = existing_config.get('cli', {
        'input_dir': 'input',
        'output_dir': 'output',
        'preserve_structure': True,
        'parallel_workers': 4
    })
    
    # 缓存配置
    unified_config['cache'] = existing_config.get('cache', {
        'enable_cache': True,
        'cache_dir': '.translation_cache',
        'max_cache_size_mb': 500,
        'cache_ttl_days': 30
    })
    
    # 日志配置
    unified_config['logging'] = existing_config.get('logging', {
        'level': 'INFO',
        'file': 'translation.log',
        'max_size_mb': 10,
        'backup_count': 5
    })
    
    # 性能配置
    unified_config['performance'] = existing_config.get('performance', {
        'monitor_performance': True,
        'memory_limit_mb': 1024,
        'enable_profiling': False
    })
    
    # MCP服务器配置
    unified_config['mcp'] = existing_config.get('mcp', {
        'enabled': True,
        'host': '0.0.0.0',
        'port': 4010,
        'max_connections': 10,
        'request_timeout': 120,
        'log_level': 'INFO',
        'enable_http_server': True,
        'http_port': 4011,
        'static_dir': 'static'
    })
    
    # MCP工具配置
    unified_config['mcp_tools'] = existing_config.get('mcp_tools', {
        'translate_text_enabled': True,
        'translate_file_enabled': True,
        'batch_translation_enabled': True,
        'max_file_size_mb': 10,
        'max_batch_size': 50,
        'allowed_extensions': ['.md', '.txt']
    })
    
    # MCP安全配置
    unified_config['mcp_security'] = existing_config.get('mcp_security', {
        'enable_auth': False,
        'api_key': '',
        'allowed_ips': ['127.0.0.1', '::1'],
        'rate_limit': 100,
        'enable_cors': True
    })
    
    # MCP缓存配置
    unified_config['mcp_cache'] = existing_config.get('mcp_cache', {
        'enabled': True,
        'cache_dir': 'data/mcp_cache',
        'max_cache_size_mb': 100,
        'ttl_seconds': 3600
    })
    
    # 术语库配置
    unified_config['terminology'] = existing_config.get('terminology', {
        'enhancement_enabled': True,
        'enable_hybrid_mode': True,
        'fallback_to_traditional': True,
        'max_cache_size': 1000,
        'cache_dir': 'data/terminology_cache',
        'quality_threshold': 0.8
    })
    
    return unified_config

def backup_existing_configs():
    """备份现有配置文件"""
    backup_dir = project_root / "config_backup"
    backup_dir.mkdir(exist_ok=True)
    
    config_dir = project_root / "config"
    if config_dir.exists():
        for file_path in config_dir.glob("*"):
            if file_path.is_file():
                backup_path = backup_dir / file_path.name
                shutil.copy2(file_path, backup_path)
                print(f"已备份配置文件: {file_path} -> {backup_path}")
    
    print(f"配置文件已备份到: {backup_dir}")

def save_unified_config(unified_config: Dict[str, Any], output_path: Optional[Path] = None):
    """保存统一配置"""
    if output_path is None:
        output_path = project_root / "config" / "unified_config.toml"
    
    try:
        import toml
        with open(output_path, 'w', encoding='utf-8') as f:
            toml.dump(unified_config, f)
        print(f"统一配置已保存到: {output_path}")
    except Exception as e:
        print(f"保存统一配置失败: {e}")

def validate_migrated_config(unified_config: Dict[str, Any]) -> bool:
    """验证迁移后的配置"""
    try:
        from src.config import UnifiedConfig
        
        # 尝试创建配置对象
        config = UnifiedConfig(**unified_config)
        
        # 验证配置
        config.validate()
        
        print("配置验证通过")
        return True
    except Exception as e:
        print(f"配置验证失败: {e}")
        return False

def main():
    """主迁移函数"""
    print("开始配置迁移...\n")
    
    # 1. 备份现有配置
    print("1. 备份现有配置文件...")
    backup_existing_configs()
    
    # 2. 加载现有配置
    print("\n2. 加载现有配置...")
    existing_config = load_existing_config()
    
    # 3. 迁移到统一配置
    print("\n3. 迁移到统一配置格式...")
    unified_config = migrate_config_to_unified(existing_config)
    
    # 4. 验证迁移后的配置
    print("\n4. 验证迁移后的配置...")
    if not validate_migrated_config(unified_config):
        print("配置验证失败，迁移中止")
        return 1
    
    # 5. 保存统一配置
    print("\n5. 保存统一配置...")
    save_unified_config(unified_config)
    
    # 6. 生成迁移报告
    print("\n6. 迁移完成！")
    print("迁移摘要:")
    print(f"- 已备份原有配置文件到 config_backup/ 目录")
    print(f"- 已生成统一配置文件: config/unified_config.toml")
    print(f"- 配置验证通过，可以开始使用新的统一配置系统")
    
    print("\n后续步骤:")
    print("1. 检查生成的统一配置文件是否符合预期")
    print("2. 更新代码以使用新的统一配置系统")
    print("3. 测试各组件是否正常工作")
    print("4. 确认无误后可以删除备份的配置文件")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())