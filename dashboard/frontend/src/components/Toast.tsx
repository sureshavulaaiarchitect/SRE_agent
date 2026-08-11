import { Toast } from '../types'

interface ToastProps {
  toasts: Toast[]
  onRemove: (id: string) => void
}

const TOAST_ICONS: Record<Toast['type'], string> = {
  success: 'OK',
  error: 'ERR',
  warning: 'WARN',
  info: 'INFO',
}

export const ToastContainer = ({ toasts, onRemove }: ToastProps) => {
  if (!toasts.length) return null

  return (
    <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast ${toast.type}`} role="alert">
          <div className="toast-icon">{TOAST_ICONS[toast.type]}</div>
          <span className="toast-msg">{toast.message}</span>
          <button
            className="toast-close"
            onClick={() => onRemove(toast.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
