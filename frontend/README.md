# AutoDS Agent Frontend

基于 React + TypeScript + Vite 的自动化数据科学 Agent 前端控制台 - **对话式交互界面**。

## ✨ 功能特性

- 💬 **对话式交互**：类似聊天界面，自然流畅的用户体验
- 📊 **进度可视化**：顶部进度条实时显示执行阶段（初始化→研究→规划→执行→完成）
- 🗂️ **智能折叠**：主要步骤（Planning、Execution等）可折叠，子步骤自动归类
- ⚙️ **内置设置**：配置面板集成在对话界面中，随时调整参数
- 📁 **侧边文件管理**：可弹出的工作区文件浏览器
- 🎨 **深色主题**：沿用金融级 UI 设计风格
- 🔄 **人机交互**：支持 HITL 模式，在对话框中直接输入
- 📝 **Markdown 渲染**：支持数学公式、代码高亮

## 🎯 界面布局

```
┌─────────────────────────────────────────────────────────┐
│  🤖 AutoDS Agent Console        [Running] [Stop] [📁]   │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐   │
│  │ [Init] ══► [Research] ══► [Plan] ═► [Exec] ═► [✓]│  ← 进度条
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  💬 对话消息区域                                         │
│  ┌────────────────────────────────────────────────┐    │
│  │ 🤖 系统: Starting Agent System                  │    │
│  │ 👤 用户: Analyze customer data...               │    │
│  │ ▶️  Step 1: Data Analysis ✓                     │    │
│  │    └─ 🤖 Selected Agent: AnalystAgent (折叠)    │    │
│  │ ▶️  Step 2: Generate Report 🔄                  │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  [⚙️] [输入框: Describe your task...      ] [📤 发送]   │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动后端服务

在项目根目录：

```bash
cd ../src
python server.py
```

后端将在 `http://localhost:8000` 运行。

### 3. 启动前端开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:3000` 运行。

### 4. 访问应用

打开浏览器访问 `http://localhost:3000`

## 使用说明

### 开始对话

1. 首次打开会看到欢迎界面，展示示例任务
2. 点击示例芯片或直接在底部输入框输入任务目标
3. 按 Enter 或点击发送按钮启动 Agent

### 查看执行进度

- **顶部进度条**：显示当前执行阶段（初始化→研究→规划→执行→完成）
- **对话消息**：主要步骤以卡片形式展示，点击可展开/折叠子步骤
- **状态图标**：
  - ✅ 成功完成
  - ❌ 执行出错
  - ⚠️ 需要注意
  - 🔄 正在执行

### 配置Agent

1. 点击输入框左侧的 **⚙️ 设置** 按钮
2. 在弹出面板中勾选/取消需要的功能：
   - ✅ Enable Web Search Tool - 启用网络搜索
   - ✅ Enable Human-in-the-Loop - 启用人机交互
   - ✅ Enable Simple Task Check - 简单任务快速响应
   - ✅ Enable Deep Research Phase - 深度研究阶段
   - └─ Use Simple Goal for Research - 使用简化目标

### 人机交互（HITL）

当 Agent 需要确认时（如审核计划）：
1. 对话框会高亮显示等待输入的提示
2. 输入框 placeholder 会显示提示信息
3. 直接输入您的响应（如 "approve"、"修改建议" 等）
4. Agent 会根据您的输入继续执行

### 查看工作区文件

1. 点击右上角 **📁 文件** 按钮
2. 侧边栏滑出显示工作区文件列表
3. 可以：
   - 👁️ 预览文件内容
   - ⬇️ 下载文件到本地
   - 🗑️ 删除不需要的文件
   - ⬆️ 上传新文件
   - 🧹 清空整个工作区

### 停止执行

点击右上角 **Stop** 按钮优雅停止 Agent 执行（会在当前步骤完成后停止）。

## 技术栈

- **React 18**：UI 框架
- **TypeScript**：类型安全
- **Vite**：快速开发构建
- **React Markdown**：Markdown 渲染
- **KaTeX**：数学公式渲染
- **Chart.js**：图表可视化（可扩展）

## 项目结构

```
frontend/
├── src/
│   ├── components/              # React 组件
│   │   ├── AgentConsole.tsx     # 主控制台（整合布局）
│   │   ├── ChatInterface.tsx    # 对话式界面（含配置面板）
│   │   ├── ProgressBar.tsx      # 顶部进度条
│   │   ├── FileManager.tsx      # 侧边文件管理器
│   │   └── InputModal.tsx       # （已废弃，功能集成到Chat）
│   ├── styles/                  # 样式文件
│   │   ├── global.css           # 全局样式
│   │   └── console.css          # 控制台+对话样式
│   ├── types/                   # TypeScript 类型
│   │   └── index.ts
│   ├── config/                  # 配置
│   │   └── api.ts               # API 地址
│   ├── App.tsx                  # 主应用组件
│   └── main.tsx                 # 入口文件
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 🎨 设计亮点

### 1. 对话式交互
- 用户目标输入、配置调整、HITL响应都在同一对话流中完成
- 自然流畅，无需在多个面板间切换

### 2. 智能消息分组
- 自动识别关键步骤（Deep Research、Planning、Execution等）
- 子步骤（search、agent selection等）自动归类到父步骤下
- 点击可折叠/展开，保持界面整洁

### 3. 进度可视化
- 5阶段进度条：初始化→研究→规划→执行→完成
- 实时状态更新：pending → active → completed/error
- 连接线动画，清晰展示执行流程

### 4. 响应式布局
- 对话区域占据主要空间
- 文件管理器侧滑弹出，不干扰主界面
- 配置面板浮动显示，需要时调用

## API 端点

前端通过以下 API 与后端通信：

- `POST /api/run` - 启动 Agent
- `POST /api/stop` - 停止 Agent
- `GET /api/status` - 获取状态和日志
- `GET /api/config` - 获取配置
- `POST /api/input` - 提交用户输入
- `POST /api/cancel-input` - 取消输入等待
- `GET /api/files` - 获取文件列表
- `GET /api/workspace` - 获取工作区信息
- `GET /api/download-file` - 下载文件
- `GET /api/file-preview` - 预览文件
- `POST /api/upload-file` - 上传文件
- `DELETE /api/delete-file` - 删除文件
- `POST /api/clear-workspace` - 清空工作区

## 构建生产版本

```bash
npm run build
```

构建产物将在 `dist/` 目录。

## 环境变量

创建 `.env` 文件配置 API 地址：

```env
VITE_API_URL=http://localhost:8000
```
