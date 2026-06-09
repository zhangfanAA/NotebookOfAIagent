import { contextBridge, ipcRenderer } from 'electron'

export interface ElectronAPI {
  isElectron: true
  platform: string
  localOcr: (imagePath: string) => Promise<{ text: string; lines: number }>
  localPdfOcr: (pdfPath: string) => Promise<{
    pages: { content: string; page: number; source: string; file_type: string }[]
    ocr_skipped: boolean
    ocr_skipped_pages: number
    ocr_pages: number
    total_pages: number
  }>
  onOcrProgress: (callback: (progress: { stage: string; current: number; total: number; message: string }) => void) => () => void
  saveTempFile: (fileName: string, data: number[]) => Promise<string>
  deleteTempFile: (filePath: string) => Promise<boolean>
  selectFile: (options?: { filters?: { name: string; extensions: string[] }[] }) => Promise<string | null>
  getAppInfo: () => Promise<{ version: string; name: string; platform: string; electronVersion: string }>
}

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  platform: process.platform,
  localOcr: (imagePath: string) => ipcRenderer.invoke('local-ocr', imagePath),
  localPdfOcr: (pdfPath: string) => ipcRenderer.invoke('local-pdf-ocr', pdfPath),
  onOcrProgress: (callback: (progress: { stage: string; current: number; total: number; message: string }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, progress: { stage: string; current: number; total: number; message: string }) => {
      callback(progress)
    }
    ipcRenderer.on('ocr-progress', handler)
    return () => { ipcRenderer.removeListener('ocr-progress', handler) }
  },
  saveTempFile: (fileName: string, data: number[]) => ipcRenderer.invoke('save-temp-file', fileName, data),
  deleteTempFile: (filePath: string) => ipcRenderer.invoke('delete-temp-file', filePath),
  selectFile: (options?: object) => ipcRenderer.invoke('select-file', options),
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
} satisfies ElectronAPI)
