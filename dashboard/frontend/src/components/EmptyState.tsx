import { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  subtitle: string
  icon: ReactNode
}

export const EmptyState = ({ title, subtitle, icon }: EmptyStateProps) => (
  <div className="text-center py-32 glass-card">
    <div className="text-6xl mb-8 opacity-20">{icon}</div>
    <h2 className="text-3xl font-bold text-slate-300 mb-4">{title}</h2>
    <p className="text-xl text-slate-500 max-w-lg mx-auto">{subtitle}</p>
  </div>
)

