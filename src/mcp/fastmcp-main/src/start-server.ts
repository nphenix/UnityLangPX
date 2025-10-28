import { exec } from "child_process";

// 编译TypeScript并启动服务器
console.log("正在编译TypeScript...");

exec("npx tsc", (error, _stdout, stderr) => {
  if (error) {
    console.error("编译失败:", error);
    process.exit(1);
  }
  
  if (stderr) {
    console.error("编译警告:", stderr);
  }
  
  console.log("编译完成，启动服务器...");
  
  // 启动编译后的服务器
  exec("node dist/unitylang-server.js", (error, _stdout, stderr) => {
    if (error) {
      console.error("启动服务器失败:", error);
      process.exit(1);
    }
    
    if (stderr) {
      console.error("服务器警告:", stderr);
    }
  });
});