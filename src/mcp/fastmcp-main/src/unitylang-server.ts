import { FastMCP } from "./FastMCP.js";
import { spawn } from "child_process";
import * as path from "path";
import { promises as fs } from "fs";
import { fileURLToPath } from "url";

// ES模块兼容的路径处理
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 定义Python工具的接口
interface PythonTool {
  name: string;
  description: string;
  parameters: any;
}

// 定义Python工具执行结果的接口
interface PythonToolResult {
  success: boolean;
  data?: any;
  error?: string;
}

// 创建FastMCP服务器实例
const server = new FastMCP({
  name: "unitylangpx-mcp-server",
  version: "1.0.0",
  instructions: "UnityLangPX翻译服务器，提供文本翻译、文件翻译、批量翻译和状态查询功能",
  // 添加ping配置以支持客户端连接检测
  ping: {
    enabled: false,  // 暂时禁用ping避免日志刷屏
    intervalMs: 30000,
    logLevel: "info"
  },
  // 添加健康检查端点
  health: {
    enabled: true,
    path: "/health",
    message: "UnityLangPX MCP Server is running",
    status: 200
  },
  // 添加utils配置以提供更好的错误处理
  utils: {
    formatInvalidParamsErrorMessage: (issues) => {
      return issues.map(issue => {
        const path = issue.path?.join(".") || "root";
        return `${path}: ${issue.message}`;
      }).join(", ");
    }
  }
});

// Python脚本路径 - 使用更健壮的路径解析
const pythonScriptPath = (() => {
  const currentDir = process.cwd();
  
  // 定义可能的脚本路径（优先查找根目录）
  const possiblePaths = [
    // 首先查找项目根目录
    path.resolve(currentDir, "..", "..", "..", "scripts", "python_tool_bridge.py"), // 从fastmcp-main到UnityLangPX根目录
    path.resolve(currentDir, "..", "..", "scripts", "python_tool_bridge.py"), // 从fastmcp-main到mcp父目录
    path.resolve(currentDir, "..", "scripts", "python_tool_bridge.py"), // 从fastmcp-main到mcp目录
    path.resolve(currentDir, "scripts", "python_tool_bridge.py"), // 在当前目录
    
    // 使用__dirname的路径
    path.resolve(__dirname, "..", "..", "..", "scripts", "python_tool_bridge.py"), // 从dist到UnityLangPX根目录
    path.resolve(__dirname, "..", "..", "scripts", "python_tool_bridge.py"), // 从dist到mcp目录
    
    // 直接使用绝对路径（如果当前在UnityLangPX目录下）
    path.resolve(currentDir, "scripts", "python_tool_bridge.py"),
  ];
  
  // 查找存在的路径
  for (const testPath of possiblePaths) {
    try {
      require('fs').accessSync(testPath);
      console.log(`找到Python脚本: ${testPath}`);
      return testPath;
    } catch (e) {
      // 路径不存在，继续尝试
    }
  }
  
  // 如果都不存在，创建一个测试路径并给出警告
  const defaultPath = path.resolve(currentDir, "..", "..", "..", "scripts", "python_tool_bridge.py");
  console.warn(`未找到Python脚本，使用推测路径: ${defaultPath}`);
  return defaultPath;
})();

// 执行Python工具的函数
async function executePythonTool(toolName: string, args: any): Promise<PythonToolResult> {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", [
      pythonScriptPath,
      toolName,
      JSON.stringify(args)
    ], {
      cwd: (() => {
        const scriptDir = path.dirname(pythonScriptPath);
        console.log(`Python进程工作目录: ${scriptDir}`);
        return scriptDir;
      })(),
      stdio: ['pipe', 'pipe', 'pipe'],
      // 设置环境变量确保UTF-8编码
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        LC_ALL: 'C.UTF-8',
        LANG: 'C.UTF-8'
      }
    });

    let stdout = "";
    let stderr = "";

    if (pythonProcess.stdout) {
      pythonProcess.stdout.on("data", (data: Buffer) => {
        // 确保使用UTF-8解码，处理可能的编码错误
        stdout += data.toString('utf-8');
      });
    }

    if (pythonProcess.stderr) {
      pythonProcess.stderr.on("data", (data: Buffer) => {
        // 确保使用UTF-8解码，处理可能的编码错误
        stderr += data.toString('utf-8');
      });
    }

    pythonProcess.on("close", (code: number | null) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (error) {
          // 添加原始输出的调试信息，但确保不包含编码问题
          const debugOutput = stdout ? stdout.substring(0, 200) + (stdout.length > 200 ? '...' : '') : 'empty';
          resolve({
            success: false,
            error: `解析Python输出失败: ${error instanceof Error ? error.message : String(error)}\n输出预览: ${debugOutput}`
          });
        }
      } else {
        resolve({
          success: false,
          error: `Python脚本执行失败，退出码: ${code}, 错误: ${stderr}`
        });
      }
    });

    pythonProcess.on("error", (error: Error) => {
      reject(error);
    });
  });
}

// 获取Python工具列表
async function getPythonTools(): Promise<PythonTool[]> {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", [
      pythonScriptPath,
      "list-tools",
      "{}"
    ], {
      cwd: (() => {
        const scriptDir = path.dirname(pythonScriptPath);
        return scriptDir;
      })(),
      stdio: ['pipe', 'pipe', 'pipe'],
      // 设置环境变量确保UTF-8编码
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        LC_ALL: 'C.UTF-8',
        LANG: 'C.UTF-8'
      }
    });

    let stdout = "";
    let stderr = "";

    if (pythonProcess.stdout) {
      pythonProcess.stdout.on("data", (data: Buffer) => {
        // 确保使用UTF-8解码，处理可能的编码错误
        stdout += data.toString('utf-8');
      });
    }

    if (pythonProcess.stderr) {
      pythonProcess.stderr.on("data", (data: Buffer) => {
        // 确保使用UTF-8解码，处理可能的编码错误
        stderr += data.toString('utf-8');
      });
    }

    pythonProcess.on("close", (code: number | null) => {
      if (code === 0) {
        try {
          const tools = JSON.parse(stdout);
          resolve(tools);
        } catch (error) {
          // 添加原始输出的调试信息，但确保不包含编码问题
          const debugOutput = stdout ? stdout.substring(0, 200) + (stdout.length > 200 ? '...' : '') : 'empty';
          reject(new Error(`解析Python工具列表失败: ${error instanceof Error ? error.message : String(error)}\n输出预览: ${debugOutput}`));
        }
      } else {
        reject(new Error(`获取Python工具列表失败，退出码: ${code}, 错误: ${stderr}`));
      }
    });

    pythonProcess.on("error", (error: Error) => {
      reject(error);
    });
  });
}

// 初始化服务器并添加工具
async function initializeServer() {
  try {
    // 获取Python工具列表
    const pythonToolsResult = await getPythonTools();
    
    // 安全地获取工具列表，确保pythonToolsResult存在且有data属性
    let pythonTools: any[] = [];
    if (pythonToolsResult && typeof pythonToolsResult === 'object') {
      if (Array.isArray(pythonToolsResult)) {
        pythonTools = pythonToolsResult;
      } else if ((pythonToolsResult as any).data && Array.isArray((pythonToolsResult as any).data)) {
        pythonTools = (pythonToolsResult as any).data;
      }
    }
    
    console.log(`获取到 ${pythonTools.length} 个Python工具`);

    // 为每个Python工具创建FastMCP工具
    for (const pythonTool of pythonTools) {
      // 确保pythonTool对象存在且具有必需的属性
      if (!pythonTool || typeof pythonTool !== 'object') {
        console.warn('跳过无效的工具对象:', pythonTool);
        continue;
      }
      
      const toolName = pythonTool.name || 'unnamed_tool';
      const toolDescription = pythonTool.description || '无描述';
      const toolParameters = pythonTool.parameters || {};
      
      
      // 确保参数schema是有效的StandardSchemaV1，处理版本兼容性问题
      let validatedParameters: any;
      try {
        // 如果参数已经是对象，直接使用
        if (toolParameters && typeof toolParameters === 'object') {
          const standard = (toolParameters as any)['~standard'] || {};
          
          // 确保有shape对象
          let shape = standard.shape || {};
          
          // 验证并修复shape中的每个属性，确保typeName存在
          for (const [key, prop] of Object.entries(shape)) {
            if (!prop || typeof prop !== 'object') {
              shape[key] = {
                typeName: "string",
                isOptional: true
              };
            } else {
              // 确保每个属性都有完整的定义
              if (shape[key] && typeof shape[key] === 'object') {
                if (shape[key].typeName === undefined) {
                  shape[key].typeName = "string";
                }
                if (shape[key].isOptional === undefined) {
                  shape[key].isOptional = true;
                }
              }
            }
          }
          
          // 创建完整的StandardSchemaV1对象
          validatedParameters = {
            "~standard": {
              version: 1,
              vendor: "zod",
              shape: shape,
              validate: (value: unknown) => {
                try {
                  return { value };
                } catch (error) {
                  return {
                    issues: [{
                      code: 'custom' as const,
                      message: error instanceof Error ? error.message : String(error)
                    }]
                  };
                }
              }
            }
          };
        } else {
          // 创建默认的StandardSchemaV1实现
          validatedParameters = {
            "~standard": {
              version: 1,
              vendor: "zod",
              shape: {},
              validate: (value: unknown) => {
                try {
                  return { value };
                } catch (error) {
                  return {
                    issues: [{
                      code: 'custom' as const,
                      message: error instanceof Error ? error.message : String(error)
                    }]
                  };
                }
              }
            }
          };
        }
      } catch (paramError) {
        console.warn(`工具 ${toolName} 的参数schema无效:`, paramError);
        validatedParameters = {
          "~standard": {
            version: 1,
            vendor: "zod",
            shape: {},
            validate: (value: unknown) => {
              try {
                return { value };
              } catch (error) {
                return {
                  issues: [{
                    code: 'custom' as const,
                    message: error instanceof Error ? error.message : String(error)
                  }]
                };
              }
            }
          }
        };
      }
      
      server.addTool({
        name: toolName,
        description: toolDescription,
        parameters: validatedParameters,
        execute: async (args: any, context: any) => {
          context.log.info(`执行Python工具: ${toolName}`, args);
          
          try {
            const result = await executePythonTool(toolName, args);
            
            if (result && result.success) {
              context.log.info(`工具 ${toolName} 执行成功`);
              return {
                content: [{
                  type: "text",
                  text: typeof result.data === 'string' ? result.data : JSON.stringify(result.data, (_key, value) => {
                    // 确保中文字符正确显示
                    if (typeof value === 'string') {
                      return value;
                    }
                    return value;
                  }, 2)
                }]
              };
            } else {
              const errorMsg = result ? result.error : '未知错误';
              context.log.error(`工具 ${toolName} 执行失败: ${errorMsg}`);
              return {
                content: [{
                  type: "text",
                  text: `工具执行失败: ${errorMsg}`
                }],
                isError: true
              };
            }
          } catch (error: any) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            context.log.error(`工具 ${toolName} 执行异常: ${errorMessage}`);
            return {
              content: [{
                type: "text",
                text: `工具执行异常: ${errorMessage}`
              }],
              isError: true
            };
          }
        }
      });
    }

    // 添加健康检查工具
    server.addTool({
      name: "health_check",
      description: "检查UnityLangPX MCP服务器状态",
      parameters: {
        "~standard": {
          version: 1 as const,
          vendor: "zod",
          shape: {
            detailed: {
              typeName: "boolean",
              isOptional: true,
              defaultValue: false
            }
          },
          validate: (value: unknown) => {
            try {
              // 简单验证，接受任何对象
              if (typeof value === 'object' && value !== null) {
                return { value };
              } else {
                return {
                  issues: [{
                    code: 'custom' as const,
                    message: '参数必须是对象'
                  }]
                };
              }
            } catch (error) {
              return {
                issues: [{
                  code: 'custom' as const,
                  message: error instanceof Error ? error.message : String(error)
                }]
              };
            }
          }
        }
      },
      execute: async (args: any, context: any) => {
        context.log.info("执行健康检查", args);
        
        try {
          const result = await executePythonTool("get_translation_status", {
            query_type: args.detailed ? "full" : "health",
            verbose: args.detailed
          });
        
          if (result.success) {
            return {
              content: [{
                type: "text",
                text: `UnityLangPX服务器状态: ${JSON.stringify(result.data, (_key, value) => {
                  // 确保中文字符正确显示
                  if (typeof value === 'string') {
                    return value;
                  }
                  return value;
                }, 2)}`
              }]
            };
          } else {
            return {
              content: [{
                type: "text",
                text: `健康检查失败: ${result.error}`
              }],
              isError: true
            };
          }
        } catch (error: any) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          context.log.error(`健康检查异常: ${errorMessage}`);
          return {
            content: [{
              type: "text",
              text: `健康检查异常: ${errorMessage}`
            }],
            isError: true
          };
        }
      }
    });

    console.log("FastMCP服务器初始化完成");
  } catch (error: any) {
    console.error("初始化FastMCP服务器失败:", error);
    throw error;
  }
}

// 启动服务器
async function startServer() {
  try {
    // 检查Python脚本是否存在
    try {
      await fs.access(pythonScriptPath);
      console.log(`Python桥接脚本存在: ${pythonScriptPath}`);
    } catch (error: any) {
      console.error(`Python桥接脚本不存在: ${pythonScriptPath}`);
      throw error;
    }

    // 初始化服务器
    await initializeServer();

    // 启动服务器
    await server.start({
      transportType: "httpStream",
      httpStream: {
        port: 4020,  // 改为 4020 端口以避免冲突
        host: "0.0.0.0",
        endpoint: "/mcp",
        stateless: true,
        // 禁用JSON响应以支持SSE流
        enableJsonResponse: false
      }
    });

    console.log("UnityLangPX FastMCP服务器已启动");
    console.log("HTTP流地址: http://0.0.0.0:4020/mcp");
    console.log("Docker访问地址: http://host.docker.internal:4020/mcp");
  } catch (error: any) {
    console.error("启动FastMCP服务器失败:", error);
    if (typeof process !== 'undefined') {
      process.exit(1);
    }
  }
}

// 处理进程退出
if (typeof process !== 'undefined') {
  process.on("SIGINT", () => {
    console.log("\n收到SIGINT信号，正在关闭服务器...");
    server.stop().then(() => {
      console.log("服务器已关闭");
      process.exit(0);
    });
  });

  process.on("SIGTERM", () => {
    console.log("\n收到SIGTERM信号，正在关闭服务器...");
    server.stop().then(() => {
      console.log("服务器已关闭");
      process.exit(0);
    });
  });
}

// 启动服务器
startServer().catch((error: any) => {
  console.error("启动服务器时发生错误:", error);
  if (typeof process !== 'undefined') {
    process.exit(1);
  }
});