interface ImportMetaEnv {
  readonly VITE_API_MODE?: string
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
