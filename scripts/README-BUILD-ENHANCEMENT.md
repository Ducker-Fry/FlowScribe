# Build Scripts Enhancement Summary

## What's New

构建脚本现在具备完整的依赖检测和自动配置功能：

### 核心功能

1. **自动依赖检测**
   - 检测 Python 3.10+、.NET SDK 8.0+、ffmpeg/ffprobe
   - 检测 Python 包（PyInstaller、PySide6）及版本
   - 语义化版本比较

2. **智能搜索**
   - 在常见安装位置自动搜索依赖
   - Python: `C:\Python*`, `%LOCALAPPDATA%\Programs\Python\*`
   - .NET SDK: `C:\Program Files\dotnet`
   - ffmpeg: `C:\ffmpeg\bin`, Chocolatey 安装位置

3. **PATH 自动管理**
   - 三种添加方式：
     - **用户 PATH**：永久，仅当前用户，无需管理员权限
     - **系统 PATH**：永久，所有用户，需要管理员权限
     - **会话 PATH**：临时，仅当前终端，关闭后失效
   - 交互式选择或自动添加模式

4. **Python 包自动安装**
   - 自动安装缺失的 PyInstaller、PySide6
   - 自动升级版本过低的包
   - 交互式确认或自动安装模式

## 使用方式

### 正常构建（交互式）

```powershell
# 直接运行构建脚本，会自动检测并提示
.\scripts\build_exe.ps1
.\scripts\build_gui_exe.ps1
```

### 手动检测依赖

```powershell
# 检测所有 CLI 依赖
.\scripts\Check-BuildDependencies.ps1 -CheckPython -CheckFfmpeg -CheckPyInstaller

# 检测所有 GUI 依赖
.\scripts\Check-BuildDependencies.ps1 -CheckPython -CheckDotNet -CheckFfmpeg -CheckPyInstaller -CheckPySide6
```

### 自动化模式（CI/CD）

```powershell
# 自动安装包并添加到 PATH，无需交互
.\scripts\Check-BuildDependencies.ps1 `
    -CheckPython -CheckFfmpeg -CheckPyInstaller `
    -AutoInstall -AutoAddToPath
```

## 典型场景

### 场景 1：首次构建

用户运行 `.\scripts\build_gui_exe.ps1`，脚本会：
1. 检测 Python → 找到但不在 PATH → 提示添加到 PATH
2. 检测 .NET SDK → 找到并在 PATH 中 → 通过
3. 检测 ffmpeg → 找到但不在 PATH → 提示添加到 PATH
4. 检测 PyInstaller → 未安装 → 提示安装
5. 检测 PySide6 → 未安装 → 提示安装

用户选择添加到 PATH 和安装包后，构建继续。

### 场景 2：依赖已安装但不在 PATH

```
Checking Python...
✗ Python check failed: Python command failed
Searching for Python installation...
✓ Found Python 3.11.5 at: C:\Users\YourName\AppData\Local\Programs\Python\Python311
Add Python to PATH?
  1. Add to User PATH (current user only)
  2. Add to System PATH (all users, requires admin)
  3. Add to current session only (temporary)
  4. Skip
Choose [1-4]: 1
✓ Added to User PATH: C:\Users\YourName\AppData\Local\Programs\Python\Python311
```

### 场景 3：依赖版本过低

```
Checking PySide6...
⚠ PySide6 version too old: Version 6.5.0 is below minimum 6.7
Upgrade PySide6 now? [Y/n] y
Installing PySide6...
✓ PySide6 installed successfully
```

## 新增文件

- `scripts/Check-BuildDependencies.ps1` - 依赖检测核心模块
- `scripts/test_dependency_check.ps1` - 测试脚本
- `scripts/demo_path_management.ps1` - PATH 管理演示脚本
- `docs/build-dependency-checking.md` - 完整使用文档

## 更新文件

- `scripts/build_exe.ps1` - 添加依赖检测
- `scripts/build_gui_exe.ps1` - 添加依赖检测
- `scripts/build_wasapi_helper.ps1` - 添加依赖检测

## 测试

```powershell
# 运行所有测试
.\scripts\test_dependency_check.ps1

# 演示 PATH 管理
.\scripts\demo_path_management.ps1 -DemoSearch
.\scripts\demo_path_management.ps1 -DemoPathAdd

# 查看当前 PATH
.\scripts\demo_path_management.ps1 -ShowCurrentPath
```

## 详细文档

完整使用说明和故障排除指南：[docs/build-dependency-checking.md](../docs/build-dependency-checking.md)

## 技术细节

### 搜索位置

**Python:**
- `C:\Python*`
- `%LOCALAPPDATA%\Programs\Python\Python*`
- `C:\Program Files\Python*`
- `C:\Program Files (x86)\Python*`

**.NET SDK:**
- `C:\Program Files\dotnet`
- `C:\Program Files (x86)\dotnet`

**ffmpeg:**
- `C:\ffmpeg\bin`
- `C:\Program Files\ffmpeg\bin`
- `C:\Program Files (x86)\ffmpeg\bin`
- `%LOCALAPPDATA%\ffmpeg\bin`
- Chocolatey lib 文件夹

### PATH 管理

**用户 PATH:**
- 注册表：`HKCU:\Environment`
- 作用域：当前用户
- 权限：无需管理员
- 生效：需重启终端

**系统 PATH:**
- 注册表：`HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment`
- 作用域：所有用户
- 权限：需要管理员
- 生效：需重启终端

**会话 PATH:**
- 环境变量：`$env:PATH`
- 作用域：当前终端
- 权限：无需管理员
- 生效：立即生效
- 持久性：关闭终端后失效

## 优势

✅ **用户友好**：自动检测并提示，无需手动查找依赖  
✅ **智能搜索**：在常见位置自动查找已安装的依赖  
✅ **灵活配置**：三种 PATH 添加方式，适应不同需求  
✅ **自动化支持**：支持 CI/CD 无交互模式  
✅ **清晰反馈**：详细的错误信息和安装指引  
✅ **安全可靠**：版本检查确保依赖满足最低要求
