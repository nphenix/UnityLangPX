@echo off
echo UnityLangPX 环境配置脚本
echo ============================

REM 检查conda是否已安装
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo 尝试添加conda到PATH...
    set PATH=%PATH%;d:\ProgramData\miniconda3\Scripts;d:\ProgramData\miniconda3\condabin
    where conda >nul 2>nul
    if %errorlevel% neq 0 (
        echo 错误: 未找到conda，请先安装Anaconda或Miniconda
        pause
        exit /b 1
    )
)

echo 创建conda环境 unitylangpx (Python 3.12)...
conda create -n unitylangpx python=3.12 -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/ -y

echo 激活conda环境...
call conda activate unitylangpx

echo 配置pip国内镜像源...
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn

echo 配置conda国内镜像源...
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
conda config set show_channel_urls yes

echo 配置pre-commit使用国内镜像源...

echo 安装基础依赖...
pip install -r requirements\base.txt
if %errorlevel% neq 0 (
    echo 警告: 基础依赖安装失败，请检查requirements\base.txt是否存在
)

echo 安装开发依赖...
pip install -r requirements\dev.txt
if %errorlevel% neq 0 (
    echo 警告: 开发依赖安装失败，请检查requirements\dev.txt是否存在
)

echo.
echo 环境配置完成！
echo 使用以下命令激活环境:
echo   conda activate unitylangpx
echo.
pause