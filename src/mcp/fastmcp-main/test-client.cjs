const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StreamableHTTPClientTransport } = require("@modelcontextprotocol/sdk/client/streamableHttp.js");

async function testConnection() {
  console.log("开始测试FastMCP服务器连接...");
  
  const client = new Client(
    {
      name: "test-client",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
        logging: {},
        roots: {}
      },
    },
  );

  const transport = new StreamableHTTPClientTransport(
    new URL("http://localhost:4011/mcp"),
    {
      requestInit: {
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "User-Agent": "test-client/1.0.0"
        }
      }
    }
  );

  try {
    console.log("正在连接到服务器...");
    await client.connect(transport);
    console.log("✅ 连接成功!");

    // 测试获取工具列表
    console.log("正在获取工具列表...");
    const tools = await client.listTools();
    console.log("✅ 工具列表获取成功:");
    console.log(JSON.stringify(tools, null, 2));

    // 测试调用工具
    if (tools.tools && tools.tools.length > 0) {
      const firstTool = tools.tools[0];
      console.log(`正在测试工具: ${firstTool.name}`);
      
      try {
        const result = await client.callTool({
          name: firstTool.name,
          arguments: {
            text: "Hello World",
            source_lang: "en",
            target_lang: "zh"
          },
        });
        console.log("✅ 工具调用成功:");
        console.log(JSON.stringify(result, null, 2));
      } catch (toolError) {
        console.log(`⚠️ 工具调用失败: ${toolError.message}`);
      }
    }

  } catch (error) {
    console.error("❌ 连接失败:", error.message);
    console.error("详细错误:", error);
  } finally {
    try {
      await client.close();
      console.log("连接已关闭");
    } catch (closeError) {
      console.error("关闭连接时出错:", closeError.message);
    }
  }
}

testConnection().catch(console.error);