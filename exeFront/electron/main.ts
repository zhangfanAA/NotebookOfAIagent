import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import path from 'path'
import { spawn, execSync } from 'child_process'
import fs from 'fs'

let mainWindow: BrowserWindow | null = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: '智能学习助手',
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

// ===== Helpers =====

// 解析 Python 脚本路径（开发模式在 electron/，打包后在 resources/）
function getScriptPath(name: string): string {
  // 开发模式: __dirname = dist-electron/，脚本在 electron/ 目录
  const devPath = path.join(__dirname, '..', 'electron', name)
  if (fs.existsSync(devPath)) return devPath
  // 打包后: 脚本在 resources/ 目录
  const prodPath = path.join(process.resourcesPath || __dirname, name)
  if (fs.existsSync(prodPath)) return prodPath
  // 兜底: 当前目录
  return path.join(__dirname, name)
}

// 查找可用的 Python 可执行文件（优先虚拟环境）
function findPython(): string {
  // 1. 项目根目录的 .venv
  const venvPython = path.join(__dirname, '..', '..', '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(venvPython)) return venvPython
  // 2. EXEFront 同级的 .venv
  const venvPython2 = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(venvPython2)) return venvPython2
  // 3. 环境变量
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH
  // 4. 系统 python
  return 'python'
}

// ===== IPC Handlers =====

// Local OCR via Python subprocess
ipcMain.handle('local-ocr', async (_event, imagePath: string) => {
  return new Promise((resolve, reject) => {
    const scriptPath = getScriptPath('local-ocr.py')
    const python = findPython()

    if (!fs.existsSync(imagePath)) {
      reject(new Error(`文件不存在: ${imagePath}`))
      return
    }

    const proc = spawn(python, [scriptPath, imagePath], {
      timeout: 120000,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code: number | null) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(stdout))
        } catch {
          reject(new Error('OCR 输出解析失败'))
        }
      } else {
        reject(new Error(stderr || `OCR 进程退出码: ${code}`))
      }
    })

    proc.on('error', (err: Error) => {
      reject(new Error(`启动 OCR 进程失败: ${err.message}`))
    })
  })
})

// Local PDF OCR via Python subprocess
ipcMain.handle('local-pdf-ocr', async (event, pdfPath: string) => {
  return new Promise((resolve, reject) => {
    const scriptPath = getScriptPath('local-pdf-parser.py')
    const python = findPython()

    if (!fs.existsSync(pdfPath)) {
      reject(new Error(`文件不存在: ${pdfPath}`))
      return
    }

    const proc = spawn(python, [scriptPath, pdfPath], {
      timeout: 600000,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })

    proc.stderr.on('data', (d: Buffer) => {
      const text = d.toString()
      stderr += text
      // 解析 [PROGRESS] 行并转发给渲染进程
      for (const line of text.split('\n')) {
        if (line.includes('[PROGRESS]')) {
          try {
            const jsonStr = line.substring(line.indexOf('[PROGRESS]') + 10)
            const progress = JSON.parse(jsonStr)
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('ocr-progress', progress)
            }
          } catch {}
        }
      }
    })

    proc.on('close', (code: number | null) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(stdout))
        } catch {
          reject(new Error('PDF OCR 输出解析失败'))
        }
      } else {
        reject(new Error(stderr || `PDF OCR 进程退出码: ${code}`))
      }
    })

    proc.on('error', (err: Error) => {
      reject(new Error(`启动 PDF OCR 进程失败: ${err.message}`))
    })
  })
})

// File dialog for selecting files
ipcMain.handle('select-file', async (_event, options: { filters?: Electron.FileFilter[] }) => {
  if (!mainWindow) return null
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: options.filters || [
      { name: '图片文件', extensions: ['png', 'jpg', 'jpeg', 'bmp', 'tiff'] },
    ],
  })
  if (result.canceled || result.filePaths.length === 0) return null
  return result.filePaths[0]
})

// Save temp file for local OCR processing
ipcMain.handle('save-temp-file', async (_event, fileName: string, data: number[]) => {
  const os = require('os')
  const tempDir = os.tmpdir()
  const tempPath = path.join(tempDir, `exefront_${Date.now()}_${fileName}`)
  fs.writeFileSync(tempPath, Buffer.from(data))
  return tempPath
})

// Delete temp file
ipcMain.handle('delete-temp-file', async (_event, filePath: string) => {
  try {
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
  } catch {}
  return true
})

// Get app version
ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    name: app.getName(),
    platform: process.platform,
    electronVersion: process.versions.electron,
  }
})
